#!/bin/bash
# Bot ve API'yi aynı anda başlat
python -m bot.telegram_bot &
uvicorn api.main:app --host 0.0.0.0 --port 8000
