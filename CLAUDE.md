# CLAUDE.md — Career Assistant AI Agent

> Okul ödevi kapsamında geliştirilen, EvalOps prensiplerine dayalı çoklu-agent sistem.

## 🎯 Proje Özeti

Bu proje, potansiyel işverenlerle iletişimi otomatize eden, kendi kendini değerlendiren bir AI Agent sistemidir. Telegram üzerinden çalışan sistem, Career Agent (cevap üretir) ve Judge Agent (cevabı değerlendirir) olmak üzere iki ana agent'tan oluşur.

## 🏗️ Mimari

```
Employer Message (Telegram)
    ↓
Career Agent (openai/gpt-4o-mini)
  → CV context (hybrid: static < 2000 char, else ChromaDB RAG)
  → Memory (history.json - per employer)
  → Draft response
    ↓
Judge Agent (minimax/minimax-m2.5)
  → 4 metrics: Truthfulness, Robustness, Helpfulness, Tone
  → JSON output
    ↓
Score >= 4.0?
  ✅ YES → Send + notify admin
  ❌ NO  → Revise (max 3 iterations)
  ⚠️ INTERVENTION → Pause + alert
    ↓
Logger (CSV) → FastAPI → React Dashboard → HuggingFace
```

## 📁 Klasör Yapısı

```
career-agent/
├── agent/
│   ├── career_agent.py       # Cevap üreten ana agent
│   ├── evaluator_agent.py    # Judge Agent (LLM-as-a-Judge)
│   └── prompts/
│       ├── career_prompt.txt
│       └── evaluator_prompt.txt
│
├── api/
│   └── main.py               # FastAPI — dashboard için log endpoint'i
│
├── bot/
│   └── telegram_bot.py       # Telegram bot + admin komutları
│
├── tools/
│   ├── intervention.py       # İnsan müdahalesi tespiti
│   └── logger.py             # CSV loglama
│
├── data/
│   ├── cv.txt                # CV/profil (statik context)
│   ├── history.json          # Memory (employer başına konuşma geçmişi)
│   └── logs.csv              # Evaluation logları
│
└── dashboard/                # React frontend (Vercel deploy)
```

## 🔧 Tech Stack

| Component | Technology |
|-----------|------------|
| LLM Provider | OpenRouter |
| Career Agent | `openai/gpt-4o-mini` |
| Judge Agent | `minimax/minimax-m2.5` |
| Bot | Telegram Bot API (`python-telegram-bot`) |
| Backend | Python + FastAPI |
| Frontend | React + Vite + TailwindCSS + Recharts |
| Database | ChromaDB (RAG için) |
| Deployment | Railway (bot) + Vercel (dashboard) |
| Dataset | HuggingFace |

## 🧠 EvalOps Metrikleri (1-5 scale)

| Metrik | Açıklama |
|--------|----------|
| **Truthfulness** | CV'ye dayalı mı? Hallucination yok mu? |
| **Robustness** | Prompt injection direnci, beklenmedik mesajları yönetme |
| **Helpfulness** | İşverenin sorusuna gerçekten cevap veriyor mu? |
| **Tone** | Profesyonel, net, kibar ton |

Judge Output Format:
```json
{
  "truthfulness_score": 5,
  "robustness_score": 5,
  "helpfulness_score": 4,
  "tone_score": 5,
  "overall_score": 4.75,
  "is_approved": true,
  "trigger_human_intervention": false,
  "intervention_reason": null,
  "feedback": "Response is accurate and professional."
}
```

## ⚠️ İnsan Müdahalesi Trigger'ları

Bot otomatik pause olur ve admin'e bildirim gönderir:
- 💰 **Salary negotiation** — Ücret tartışması
- ⚖️ **Legal questions** — Sözleşme, NDA, maddeler
- 🔬 **Out-of-domain technical** — Uzmanlık dışı teknik sorular
- 🌫️ **Ambiguous offers** — Belirsiz iş teklifi
- 🚫 **Off-topic** — Konu dışı mesajlar

## 📱 Telegram Admin Komutları

| Komut | Açıklama |
|-------|----------|
| `/reply <metin>` | Casual talimat → profesyonel cevap |
| `/update_cv` | Yeni .txt dosyası ile CV güncelle |
| `/add_info <metin>` | CV'ye bilgi ekle |
| `/remove_info <metin>` | CV'den bilgi sil |
| `/show_cv` | Mevcut CV'yi göster |
| `/status` | Bot durumunu göster |

## 🔐 Güvenlik Notları

- Tüm Telegram komutları `TELEGRAM_CHAT_ID` ile korunur
- OpenRouter API key .env'de saklanır
- Prompt injection'a karşı Robustness metriği kontrol eder
- Loglarda hassas bilgi saklanmaz (employer message mask'lenebilir)

## 🧪 Test Cases

### Test 1 — Mülakat Daveti
```
"We'd like to invite you for a technical interview next week. Are you available?"
→ Agent profesyonel kabul, availability önerisi, no intervention
```

### Test 2 — Teknik Soru
```
"Can you describe your experience with building evaluation pipelines for LLMs?"
→ CV bazlı cevap, high truthfulness, no hallucination
```

### Test 3 — Salary / Intervention
```
"We're offering a base salary of $90,000 + equity. Does that work for you?"
→ trigger_human_intervention: true
→ reason: salary_negotiation
→ Bot pause + admin alert
```

## 📦 Environment Variables

```env
OPENROUTER_API_KEY=
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
CAREER_AGENT_MODEL=openai/gpt-4o-mini
JUDGE_AGENT_MODEL=minimax/minimax-m2.5
APPROVAL_THRESHOLD=4.0
```

## 🚀 Geliştirme İpuçları

1. **Her fazı test et** — Bir sonraki faza geçmeden önce çalışır durumda doğrula
2. **Overengineering yapma** — README ve ROADMAP'deki basitlik prensibini takip et
3. **Her iterasyonda logla** — CSV formatına dikkat et, HuggingFace'e uygun
4. **Judge feedback'i önemse** — Revizyon loop'u Judge'un feedback'ini kullanır
5. **CV context stratejisi** — Kısa CV: direkt prompt, Uzun CV: ChromaDB RAG

## 📌 Öncelikli Görevler

Şu anki duruma göre bir sonraki adım:
1. Docker setup'ı tamamla
2. Agent'ları OpenRouter'a bağla
3. Telegram bot'u aktif et
4. EvalOps loop'unu test et

## 🎓 Proje Türü

Bu bir **okul projesi**dir — üretime alınmayacak, ancak sektörel standartlarda bir EvalOps demosu olarak teslim edilecektir.
