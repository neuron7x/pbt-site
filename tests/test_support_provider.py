"""Контракт OpenAI перевіряється без зовнішніх запитів."""

import base64
import io
import json

import pytest

import server.support_provider as support_provider


def _response(message='Уточніть тип ґрунту.', fact_ids=()):
    payload = json.dumps({'reply': message, 'fact_ids': list(fact_ids)})
    return {
        'status': 'completed',
        'output': [
            {'type': 'reasoning', 'summary': []},
            {'type': 'message', 'role': 'assistant', 'content': [{'type': 'output_text', 'text': payload}]},
        ],
    }


@pytest.fixture
def transport(monkeypatch):
    queue = []
    requests = []

    class FakeSocket:
        def __init__(self, packet):
            self.packet = packet

        def makefile(self, *args, **kwargs):
            return io.BytesIO(self.packet)

        def settimeout(self, value):
            assert 0 < value <= 12

    class FakeHTTPSConnection:
        def __init__(self, host, timeout):
            self.sock = None
            self.record = {'host': host, 'timeout': timeout, 'closed': False}
            requests.append(self.record)

        def request(self, method, path, body, headers):
            self.record.update(method=method, path=path, body=body, headers=headers)

        def getresponse(self):
            data, status, length = queue.pop(0)
            if isinstance(data, Exception):
                raise data
            if not isinstance(data, bytes):
                data = json.dumps(data).encode('utf-8')
            packet = (f'HTTP/1.1 {status} Test\r\nContent-Type: application/json\r\n'
                      f'Content-Length: {len(data) if length is None else length}\r\n\r\n').encode() + data
            self.sock = FakeSocket(packet)
            reply = support_provider.http.client.HTTPResponse(self.sock)
            reply.begin()
            return reply

        def close(self):
            self.record['closed'] = True

    monkeypatch.setattr(support_provider.http.client, 'HTTPSConnection', FakeHTTPSConnection)

    def respond(data, status=200, length=None):
        queue.append((data, status, length))

    return respond, requests


def _provider():
    return support_provider.OpenAIProvider('unit-test-key', 'test-vision-model', 'gpt-transcribe')


def test_cloud_provider_requires_explicit_readiness():
    settings = {'PBT_SUPPORT_OPENAI_KEY': 'unit-test-key', 'PBT_SUPPORT_MODEL': 'test-vision-model'}
    assert support_provider.OpenAIProvider.from_env(settings.get) is None

    settings['PBT_SUPPORT_MODEL_ENABLED'] = '1'
    provider = support_provider.OpenAIProvider.from_env(settings.get)
    assert isinstance(provider, support_provider.OpenAIProvider)
    assert provider._transcribe_model == 'gpt-transcribe'

    settings['PBT_SUPPORT_MODEL'] = '\r\n'
    assert support_provider.OpenAIProvider.from_env(settings.get) is None
    settings['PBT_SUPPORT_MODEL'] = 'test-vision-model'
    settings['PBT_SUPPORT_TRANSCRIBE_MODEL'] = 'model\r\ninvalid'
    assert support_provider.OpenAIProvider.from_env(settings.get) is None
    settings['PBT_SUPPORT_TRANSCRIBE_MODEL'] = 'transcription-snapshot'
    settings['PBT_SUPPORT_OPENAI_KEY'] = 'invalid key'
    assert support_provider.OpenAIProvider.from_env(settings.get) is None


def test_responses_uses_only_public_fields_and_local_schema(transport):
    respond, requests = transport
    respond(_response(fact_ids=['exc']))
    history = ['turn to omit'] + [f'Репліка {i}' for i in range(6)]
    facts = [{'id': 'exc', 'text': 'Гусеничні екскаватори', 'label': 'Каталог', 'private': 'outside projection'}]
    reply, transcript = _provider().answer('Котлован у Полтаві', history, None, facts)
    assert reply == {'reply': 'Уточніть тип ґрунту.', 'fact_ids': ['exc']}
    assert transcript is None

    assert len(requests) == 1
    request = requests[0]
    assert (request['host'], request['method'], request['path'], request['closed']) == (
        'api.openai.com', 'POST', '/v1/responses', True,
    )
    assert request['headers'] == {
        'Authorization': 'Bearer unit-test-key', 'Content-Type': 'application/json', 'Accept': 'application/json',
    }
    payload = json.loads(request['body'])
    assert payload['store'] is False and payload['model'] == 'test-vision-model'
    assert 'tools' not in payload and 'previous_response_id' not in payload
    assert 'Гусеничні екскаватори' in payload['instructions']
    assert 'outside projection' not in payload['instructions'] and 'Каталог' not in payload['instructions']
    assert all(turn['role'] == 'user' for turn in payload['input'])
    assert [turn['content'][0]['text'] for turn in payload['input']] == history[1:] + ['Котлован у Полтаві']
    assert payload['text']['format']['strict'] is True
    assert payload['text']['format']['schema']['additionalProperties'] is False
    assert payload['text']['format']['schema']['required'] == ['reply', 'fact_ids']


def test_vision_keeps_media_as_inline_data_and_never_takes_a_url(transport):
    respond, requests = transport
    respond(_response())
    image = b'\xff\xd8\xffmock'
    _provider().answer('Погляньте на під’їзд', [], ('image/jpeg', image), [])
    contents = json.loads(requests[0]['body'])['input'][0]['content']
    assert contents == [
        {'type': 'input_text', 'text': 'Погляньте на під’їзд'},
        {'type': 'input_image', 'detail': 'low', 'image_url': 'data:image/jpeg;base64,' + base64.b64encode(image).decode()},
    ]
    with pytest.raises(support_provider.ProviderError, match='^support_provider_unavailable$'):
        _provider().answer('Фото', [], ('image/svg+xml', b'<svg/>'), [])
    assert len(requests) == 1


def test_audio_is_transcribed_then_included_as_untrusted_user_content(transport):
    respond, requests = transport
    respond({'text': '  Трал до Черкас. Телефон +380991112233.  '})
    respond(_response('Звідки забрати вантаж?'))
    audio = b'RIFF\x00\x00\x00\x00WAVE'
    reply, transcript = _provider().answer('', [], ('audio/x-wav', audio), [])
    assert reply == {'reply': 'Звідки забрати вантаж?', 'fact_ids': []}
    assert transcript == 'Трал до Черкас. Телефон [контакт вилучено].'
    assert [request['path'] for request in requests] == ['/v1/audio/transcriptions', '/v1/responses']
    assert 0 < requests[1]['timeout'] <= requests[0]['timeout'] <= 12
    transcribe = requests[0]
    boundary = transcribe['headers']['Content-Type'].split('boundary=')[1].encode('ascii')
    assert transcribe['body'].startswith(b'--' + boundary + b'\r\n')
    assert transcribe['body'].endswith(audio + b'\r\n--' + boundary + b'--\r\n')
    assert b'name="model"\r\n\r\ngpt-transcribe\r\n' in transcribe['body']
    assert b'name="file"; filename="recording.wav"\r\nContent-Type: audio/wav' in transcribe['body']
    response_payload = json.loads(requests[1]['body'])
    assert response_payload['input'][0]['role'] == 'user'
    assert response_payload['input'][0]['content'][-1] == {
        'type': 'input_text', 'text': 'Автоматична транскрипція запису клієнта:\nТрал до Черкас. Телефон [контакт вилучено].',
    }
    assert 'Трал до Черкас' not in response_payload['instructions']


@pytest.mark.parametrize(('data', 'status', 'length'), [
    (b'sensitive redirect response', 302, None),
    (b'sensitive outage body', 503, None),
    (b'x' * (64 * 1024 + 1), 200, None),
    (_response(), 200, 4096),
    (b'invalid sensitive JSON', 200, None),
    (TimeoutError('sensitive transport detail'), 200, None),
    ({'status': 'incomplete', 'output': []}, 200, None),
    ({'status': 'completed', 'output': [{'type': 'function_call', 'name': 'send_lead'}]}, 200, None),
    (_response(fact_ids=['not-supplied']), 200, None),
    ({'status': 'completed', 'output': [{'type': 'message', 'role': 'assistant', 'content': [
        {'type': 'output_text', 'text': '{"reply":"duplicate","reply":"leak","fact_ids":[]}'},
    ]}]}, 200, None),
    ({'status': 'completed', 'output': [{'type': 'message', 'role': 'assistant', 'content': [
        {'type': 'refusal', 'refusal': 'sensitive disclosure'},
    ]}]}, 200, None),
])
def test_provider_faults_are_bounded_and_do_not_disclose_response(transport, data, status, length):
    respond, requests = transport
    respond(data, status, length)
    with pytest.raises(support_provider.ProviderError, match='^support_provider_unavailable$') as fault:
        _provider().answer('Тест', [], None, [])
    assert fault.value.__cause__ is None
    assert len(requests) == 1 and requests[0]['closed'] is True
