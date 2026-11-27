"""Наказ А4, крок 3: два шляхи реквізитів — один результат.

Реквізити на сторінку приходять двома шляхами з одного джерела config/business.json:
  1) збірка — tools/contacts_build.py вписує їх у web/index.html (видно без скрипта, пошуковику, до першого кадру);
  2) браузер — applyBusiness у web/js/site.js підставляє їх із /api/config (жива зміна на сервері без перезбирання).
Другий шлях потрібен, тому не прибраний. Ця рука доводить, що обидва дають те саме: інакше номер «стрибав» би після завантаження.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# слот → як зняти його значення з DOM; ті самі місця, що їх вписує tools/contacts_build.py
SNAPSHOT = """() => {
  const all = (sel, f) => [...document.querySelectorAll(sel)].map(f);
  const text = e => e.textContent;
  return {
    tel: all('a[href^="tel:"]', a => a.getAttribute('href')),
    mailto: all('a[href^="mailto:"]', a => a.getAttribute('href')),
    phone: all('[data-phone]', text), email: all('[data-email]', text), address: all('[data-address]', text),
    legal: all('[data-legal]', text), edrpou: all('[data-edrpou]', text), director: all('[data-director]', text),
    bankName: all('[data-bank-name]', text), bankIban: all('[data-bank-iban]', text),
    channels: all('#channels a', a => [a.querySelector('span').textContent, a.querySelector('b').textContent, a.getAttribute('href')]),
    hiddenRows: all('[data-director-row],[data-bank-name-row],[data-bank-iban-row],[data-email]', e => e.hidden),
    hiddenActions: all('[data-phone-action]', e => e.hidden),
  };
}"""


def _snapshot(browser, server, scripted):
    context = browser.new_context(java_script_enabled=scripted, reduced_motion='reduce')
    page = context.new_page()
    try:
        if scripted:
            with page.expect_response(lambda r: r.url.endswith('/api/config')) as config:
                page.goto(server['base'] + '/')
            assert config.value.ok
            page.wait_for_load_state('networkidle')
        else:
            page.goto(server['base'] + '/')
        return page.evaluate(SNAPSHOT)
    finally:
        context.close()


def test_build_time_markup_and_browser_substitution_give_the_same_contacts(browser, server):
    built, applied = _snapshot(browser, server, scripted=False), _snapshot(browser, server, scripted=True)
    assert len(built['tel']) >= 10 and len(built['phone']) >= 4 and len(built['channels']) >= 2, built      # знімок не порожній
    # скрипт малює каталог і форму на місці двох запасних блоків «…недоступний. Зателефонуйте», тому посилань tel: стає менше;
    # значення мусять лишитись ті самі, а всі інші слоти — збігтися поелементно
    fallbacks = ('tel', 'hiddenActions')
    assert len(applied['tel']) >= 8 and set(applied['tel']) == set(built['tel']) and len(set(built['tel'])) == 1
    assert set(applied['hiddenActions']) == set(built['hiddenActions']) == {False}
    assert {k: v for k, v in applied.items() if k not in fallbacks} == {k: v for k, v in built.items() if k not in fallbacks}


def test_both_paths_read_the_same_source(browser, server):
    business = json.loads((ROOT / 'config/business.json').read_text(encoding='utf-8'))
    applied = _snapshot(browser, server, scripted=True)
    phone = business['contacts']['phone']
    assert set(applied['tel']) == {f'tel:{phone}'} and set(applied['mailto']) == {'mailto:' + business['contacts']['email']}
    assert re.fullmatch(r'0\d{2} \d{3} \d{2} \d{2}', applied['phone'][0]) and applied['phone'][0].replace(' ', '')[1:] == phone[4:]
    assert set(applied['address']) == {business['address']} and applied['edrpou'] == ['ЄДРПОУ ' + business['edrpou']]
