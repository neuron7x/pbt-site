# ПЛЕЙНБУД — публічний сайт. Python 3.10+, stdlib-сервер; тести: pytest + playwright (chromium) + axe.
PY ?= python3
PORT ?= 4180

run:            ## сайт + API заявок: http://127.0.0.1:$(PORT)/
	PORT=$(PORT) $(PY) server/app.py

test:           ## API + безпека + браузер (3 в'юпорти) + WCAG 2.2 AA (axe)
	$(PY) -m pytest -q -p no:cacheprovider

test-api:       ## лише API/безпека
	$(PY) -m pytest -q -p no:cacheprovider tests/test_api.py tests/test_leads.py tests/test_hardening.py

test-site:      ## лише браузерні тести
	$(PY) -m pytest -q -p no:cacheprovider tests/test_site.py

media:          ## відео героя/робіт/доказу з канонічних кліпів клієнта (references/*.mp4 → web/media/video), детерміновано, ffmpeg
	$(PY) tools/media.py

stock:          ## секція «Масштаб»: кліпи Wikimedia Commons (config/stock.json → web/media/cine + web/js/cine.js), ліцензія й sha256 — fail-closed
	$(PY) tools/stock.py

shots:          ## верифіковані скриншоти + SHA-256 JSON у artifacts/shots (сервер має працювати)
	$(PY) tools/shots.py http://127.0.0.1:$(PORT)

media-audit:    ## fail-closed розміри і sha256 локальних медіа; звіт artifacts/media-budget.json
	$(PY) tools/media_budget.py

bundle:         ## одно-файлова версія (артефакт / перегляд без сервера): dist/pbt-site.html
	$(PY) tools/inline.py

mutation:       ## critical fault catalog on a disposable copy; survivor fails
	$(PY) tools/mutation_run.py --out artifacts/mutation/mutation-ledger.json

assurance:      ## ledger and specification well-formed; accepts nothing
	$(PY) tools/assurance_check.py

accept:         ## engineering acceptance from real artifact ZIPs: make accept EVIDENCE=dir
	$(PY) tools/assurance_check.py --require engineering --evidence-dir $(EVIDENCE)

js:             ## статичний аналіз JS: ESLint (recommended + Mozilla no-unsanitized), TypeScript checkJs strict, property-тести ядер
	cd tools/js && npm ci --ignore-scripts --no-audit --no-fund && npm audit signatures && npm run check
	node --test tests/quote_engine.test.cjs tests/blueprint_geometry.test.cjs tests/dom_factory.test.cjs tests/motion_physics.test.cjs tests/frame_clock.test.cjs

sky:            ## палітра «небо над Полтавою і вода»: блок у site.css мусить відповідати моделі tools/sky.py (fail-closed)
	$(PY) tools/sky.py --check

crane:          ## кран-глибиномір: канат, гак і кадри вантажу в site.css мусять відповідати tools/crane.py (fail-closed)
	$(PY) tools/crane.py --check

data:           ## web/js/data.js мусить дорівнювати виходу tools/data_build.py із config/business.json, data/catalog.json, content/site.json (fail-closed)
	$(PY) tools/data_build.py --check

gate: js sky crane data test bundle media-audit ## релізний гейт: тести + збірка + бюджет медіа; дерево чисте
	@status="$$(git status --porcelain)"; test -z "$$status" || { echo "дерево брудне після гейта"; printf '%s\n' "$$status"; exit 1; }; echo "GATE PASS"

clean:
	rm -rf artifacts dist tests/__pycache__ server/__pycache__ tools/__pycache__

ops-install:    ## systemd --user: сервіс + сторож здоров'я + бекап (лише за наказом власника — ops/README.md)
	bash ops/install.sh

help:
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | sed 's/:.*##/ —/'

.PHONY: js sky crane data mutation assurance accept run test test-api test-site media stock shots media-audit bundle gate clean ops-install help
