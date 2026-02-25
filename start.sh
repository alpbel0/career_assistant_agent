#!/bin/bash
# CV'yi ChromaDB'ye index'le (her container başlangıcında)
echo "📚 CV index'leniyor..."
python -m tools.index_cv
echo "✅ CV index hazır."

# Bot ve API'yi aynı anda başlat
python -m bot.telegram_bot &
uvicorn api.main:app --host 0.0.0.0 --port 8000
