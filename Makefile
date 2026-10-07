# ПБТ · ПолтаваБудТехніка — публічний сайт. Python 3.10+, stdlib-сервер; тести: pytest + playwright (chromium) + axe.
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

shots:          ## знімки екранів у artifacts/shots (сервер має працювати)
	$(PY) tools/shots.py http://127.0.0.1:$(PORT)

bundle:         ## одно-файлова версія (артефакт / перегляд без сервера): dist/pbt-site.html
	$(PY) tools/inline.py

gate: test bundle ## релізний гейт: тести + збірка; дерево після гейта чисте
	@git status --porcelain | grep -q . && { echo "дерево брудне після гейта"; exit 1; } || echo "GATE PASS"

clean:
	rm -rf artifacts dist tests/__pycache__ server/__pycache__ tools/__pycache__

ops-install:    ## systemd --user: сервіс + сторож здоров'я + бекап (лише за наказом власника — ops/README.md)
	bash ops/install.sh

help:
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | sed 's/:.*##/ —/'
.PHONY: run test test-api test-site media stock shots bundle gate clean ops-install help
