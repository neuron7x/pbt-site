#!/usr/bin/env bash
# ПБТ · ПолтаваБудТехніка — локальний запуск: сайт + API заявок (python3 stdlib)
cd "$(dirname "$0")" && exec python3 server/app.py
