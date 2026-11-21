"""Actual HTTP checks for bounded range parsing and representation negotiation."""
import gzip
import http.client
import json
from pathlib import Path
import socket
import tempfile

import pytest

from test_leads import LEAD, srv  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]


def request(server, path='/', *, headers=(), method='GET', body=None):
    connection = http.client.HTTPConnection('127.0.0.1', server.port, timeout=5)
    try:
        connection.putrequest(method, path, skip_accept_encoding=True)
        for name, value in headers:
            connection.putheader(name, value)
        connection.endheaders(body)
        response = connection.getresponse()
        return response.status, {key.lower(): value for key, value in response.getheaders()}, response.read()
    finally:
        connection.close()


@pytest.fixture
def media():
    # A disposable synthetic byte sequence, never substituted for real media.
    content = bytes(range(256)) * 4
    with tempfile.NamedTemporaryFile(dir=ROOT / 'web/media', prefix='range-fixture-', suffix='.bin') as file:
        file.write(content)
        file.flush()
        yield '/media/' + Path(file.name).name, content


@pytest.mark.parametrize('kind,status', [
    ('huge_start', 416), ('huge_end', 206), ('huge_suffix', 206),
    ('leading_zeroes', 206), ('reversed_huge', 200),
])
def test_range_numbers_larger_than_python_integer_limit_are_bounded(srv, media, kind, status):
    server = srv()
    path, content = media
    huge = '9' * 5000
    ranges = {'huge_start': 'bytes=' + huge + '-',
              'huge_end': 'bytes=0-' + huge,
              'huge_suffix': 'bytes=-' + huge,
              'leading_zeroes': 'bytes=' + '0' * 5000 + '10-20',
              'reversed_huge': 'bytes=' + huge + '-' + '8' * 5000}
    code, headers, actual = request(server, path, headers=[('Range', ranges[kind])])
    assert code == status
    expected = b'' if status == 416 else content[10:21] if kind == 'leading_zeroes' else content
    assert actual == expected
    assert int(headers['content-length']) == len(expected)
    if status == 416:
        assert headers['content-range'] == f'bytes */{len(content)}'
    assert request(server, '/api/health')[0] == 200


@pytest.mark.parametrize('value,start,end', [('bytes=0-9', 0, 9), ('Bytes=10-', 10, 1023),
                                          ('bytes=-12', 1012, 1023), ('bytes=00-0000', 0, 0)])
def test_normal_range_and_head_preserve_exact_bytes(srv, media, value, start, end):
    server = srv()
    path, content = media
    code, headers, actual = request(server, path, headers=[('Range', value)])
    assert (code, actual) == (206, content[start:end + 1])
    assert headers['content-range'] == f'bytes {start}-{end}/{len(content)}'
    head, head_headers, no_body = request(server, path, headers=[('Range', value)], method='HEAD')
    assert head == code and no_body == b''
    assert head_headers['content-length'] == headers['content-length']


def test_repeated_range_fields_are_not_silently_reduced_to_the_first(srv, media):
    server = srv()
    path, content = media
    code, _, actual = request(server, path, headers=[('Range', 'bytes=0-9'), ('Range', 'bytes=20-29')])
    assert (code, actual) == (200, content)


@pytest.mark.parametrize('encoding', ['gzip;q=0', 'gzip;q=0.000, br', 'xgzip',
                                    'gzip2', 'gzip;q=nan', 'gzip;q=-1',
                                    'gzip;q=1.001', 'gzip;q=1;q=0',
                                    'gzip;q=0, *;q=1'])
def test_forbidden_or_malformed_gzip_never_compresses(srv, encoding):
    server = srv()
    code, headers, actual = request(server, '/css/site.css', headers=[('Accept-Encoding', encoding)])
    assert code == 200
    assert 'content-encoding' not in headers
    assert actual == (ROOT / 'web/css/site.css').read_bytes()
    assert headers.get('vary') == 'Accept-Encoding'


@pytest.mark.parametrize('encoding', ['gzip', 'GZIP', 'gzip;q=0.5', 'br, gzip;q=1',
                                    '*;q=0.5', 'x-gzip'])
def test_acceptable_gzip_preserves_bytes_and_conditional_head(srv, encoding):
    server = srv()
    headers = [('Accept-Encoding', encoding)]
    code, fields, actual = request(server, '/css/site.css', headers=headers)
    assert code == 200 and fields.get('content-encoding') == 'gzip'
    assert gzip.decompress(actual) == (ROOT / 'web/css/site.css').read_bytes()
    assert fields['vary'] == 'Accept-Encoding'
    status, head, no_body = request(server, '/css/site.css', headers=headers, method='HEAD')
    assert status == 200 and no_body == b''
    for name in ('content-encoding', 'content-length', 'etag', 'vary'):
        assert head.get(name) == fields[name]
    status, cached, no_body = request(server, '/css/site.css', method='HEAD',
                                    headers=headers + [('If-None-Match', fields['etag'])])
    assert status == 304 and no_body == b''
    assert cached['etag'] == fields['etag'] and cached['vary'] == 'Accept-Encoding'


def test_explicit_gzip_refusal_in_a_later_field_is_honored(srv):
    server = srv()
    code, fields, actual = request(server, '/css/site.css', headers=[
        ('Accept-Encoding', 'gzip'), ('Accept-Encoding', 'gzip;q=0')])
    assert code == 200 and 'content-encoding' not in fields
    assert actual == (ROOT / 'web/css/site.css').read_bytes()


def test_identity_response_varies_with_accept_encoding(srv):
    server = srv()
    code, fields, actual = request(server, '/css/site.css')
    assert code == 200 and fields.get('vary') == 'Accept-Encoding'
    assert 'content-encoding' not in fields
    assert actual == (ROOT / 'web/css/site.css').read_bytes()


@pytest.mark.parametrize('path,low_disk,status', [
    ('/api/config', False, 200), ('/api/config?cache=1', False, 200),
    ('/api/health', False, 200), ('/api/health', True, 503),
])
def test_api_head_reuses_get_status_and_headers_without_any_body(srv, path, low_disk, status):
    server = srv(HEALTH_MIN_FREE_MB='1000000000000' if low_disk else '0')
    code, fields, get_body = request(server, path)
    assert code == status and get_body
    # http.client intentionally hides HEAD response bytes; inspect the wire too.
    with socket.create_connection(('127.0.0.1', server.port), timeout=5) as connection:
        connection.sendall(f'HEAD {path} HTTP/1.0\r\nHost: 127.0.0.1:{server.port}\r\n\r\n'.encode())
        raw = b''
        while chunk := connection.recv(65536):
            raw += chunk
    head, _, body = raw.partition(b'\r\n\r\n')
    lines = head.decode('latin-1').split('\r\n')
    assert int(lines[0].split()[1]) == status
    assert body == b''
    headers = {key.lower(): value.strip() for key, value in
               (line.split(':', 1) for line in lines[1:])}
    for name in ('content-type', 'content-length', 'cache-control', 'content-security-policy'):
        assert headers[name] == fields[name]
    assert int(headers['content-length']) == len(get_body)


def post_from_proxy(server, value, key):
    body = json.dumps(LEAD).encode()
    code, _, raw = request(server, '/api/lead', method='POST', body=body, headers=[
        ('Origin', server.base), ('Content-Type', 'application/json'),
        ('Content-Length', str(len(body))), ('Idempotency-Key', key),
        ('X-Forwarded-For', value),
    ])
    return code, json.loads(raw)


@pytest.mark.parametrize('first,second', [('999.1.1.1', '999.1.1.2'),
                                       ('deadbeef', 'cafebabe'),
                                       ('2001:::1', '2001:::2'),
                                       ('01.2.3.4', '02.2.3.4')])
def test_invalid_forwarded_addresses_share_the_peer_quota(srv, first, second):
    server = srv(TRUST_PROXY='1', RATE_LEAD_10MIN='1')
    assert post_from_proxy(server, first, 'invalid-forwarded-first')[0] == 201
    code, result = post_from_proxy(server, second, 'invalid-forwarded-next')
    assert code == 429 and result['error'] == 'rate'
    assert server.rows('SELECT count(*) FROM leads') == [(1,)]


def test_valid_forwarded_addresses_keep_independent_quota(srv):
    server = srv(TRUST_PROXY='1', RATE_LEAD_10MIN='1')
    assert post_from_proxy(server, '198.51.100.1', 'valid-forwarded-first')[0] == 201
    assert post_from_proxy(server, '198.51.100.2', 'valid-forwarded-next')[0] == 201
    assert post_from_proxy(server, '198.51.100.1', 'valid-forwarded-again')[0] == 429
