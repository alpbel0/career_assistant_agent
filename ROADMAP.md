# 🗺️ ROADMAP — Career Assistant AI Agent

> Okul ödevi kapsamında geliştirilecek bu proje, üretime alınmayacak ancak sektörel standartlarda tasarlanmış bir EvalOps demosu olarak teslim edilecektir.

---

## 📅 Genel Takvim

| Faz | Konu | Süre |
|---|---|---|
| Faz 1 | Temel Altyapı | 1-2 gün |
| Faz 2 | Agent'lar | 2-3 gün |
| Faz 3 | Telegram Bot | 1-2 gün |
| Faz 4 | EvalOps & Loglama | 1-2 gün |
| Faz 5 | Dashboard | 1-2 gün |
| Faz 6 | Deploy | 1 gün |
| Faz 7 | Test & Teslim | 1 gün |

---

## 1. ✅ FAZ 1 — Temel Altyapı — TAMAMLANDI

### 1.1 Proje Kurulumu ✅
- [x] GitHub reposu oluştur
- [x] Klasör yapısını oluştur (`agent/`, `bot/`, `tools/`, `data/`, `api/`, `tests/`)
- [x] `requirements.txt` yaz
- [x] `.env.example` dosyasını oluştur
- [x] `.gitignore` ekle (`.env`, `__pycache__`, `logs/`, `data/` hassas dosyalar)

### 1.2 Docker ✅
- [x] `Dockerfile` yaz (Python 3.11-slim base image)
- [x] `docker-compose.yml` yaz
- [x] `.dockerignore` ekle
- [x] Lokal olarak `docker compose up --build` ile test et
- [x] Container içinden OpenRouter'a bağlantıyı doğrula (`tools/test_openrouter.py`)

### 1.3 CV & Veri ✅
- [x] `data/cv.txt` dosyası mevcut (3545 karakter → RAG kullanılacak)
- [x] `data/history.json` mevcut — memory (employer bazlı konuşma geçmişi)
- [x] `data/logs.csv` mevcut — evaluation logları
- [x] `tools/cv_context.py` — Hybrid context logic (`len < 2000` → direkt, `>= 2000` → ChromaDB RAG)
- [x] `tools/index_cv.py` — CV chunk'larını ChromaDB'ye index'leyen script
- [x] ChromaDB'ye CV 8 chunk olarak indexlendi (500 char, 50 overlap)

---

## 2. ✅ FAZ 2 — Agent'lar — TAMAMLANDI

### 2.1 Career Agent (`agent/career_agent.py`) ✅ TAMAMLANDI
- [x] OpenRouter API bağlantısını kur (async httpx)
- [x] `CAREER_AGENT_MODEL=openai/gpt-4o-mini` ile test çağrısı
- [x] `prompts/career_prompt.txt` sistem promptu
- [x] CV context'i prompta enjekte eden fonksiyon (ChromaDB RAG entegrasyonu)
- [x] Memory desteği — `history.json` üzerinden per-employer konuşma geçmişi
- [x] Human talimatını profesyonelleştiren fonksiyon (`/reply` komutu için)
- [x] Retry logic (3x, exponential backoff)
- [x] Graceful fallback (API hatasında Türkçe mesaj)
- [x] `feedback` parametresi ile revizyon desteği
- [x] 12 unit test (%100 coverage)
- [x] Agent test edildi: mülakat daveti, professionalize instruction

### 2.2 Judge Agent (`agent/evaluator_agent.py`) ✅ TAMAMLANDI
- [x] `JUDGE_AGENT_MODEL=google/gemini-2.0-flash-001` ile bağlantıyı test et
- [x] `prompts/evaluator_prompt.txt` sistem promptunu yaz
- [x] 4 metrik için JSON çıktısı ürettir:
  - [x] `truthfulness_score`
  - [x] `robustness_score`
  - [x] `helpfulness_score`
  - [x] `tone_score`
  - [x] `overall_score`
  - [x] `is_approved`
  - [x] `trigger_human_intervention`
  - [x] `intervention_reason`
  - [x] `feedback`
- [x] `APPROVAL_THRESHOLD=4.0` karşılaştırmasını yaz
- [x] JSON parsing (markdown tolerant)
- [x] Intervention detection (keyword-based fallback)
- [x] 15 unit test (%100 coverage)
- [x] Docker container içinde test edildi

---

## 3. 🔄 FAZ 3 — Telegram Bot — TAMAMLANDI

### 3.1 Temel Bot (`bot/telegram_bot.py`) ✅ TAMAMLANDI
- [x] `CareerAssistantBot` sınıfı oluşturuldu
- [x] `python-telegram-bot>=21.0` ile entegrasyon
- [x] Admin kontrolü (`TELEGRAM_CHAT_ID` doğrulaması)
- [x] Gelen mesaj handler'ı
- [x] İşveren mesajı → Career Agent → Judge Agent → cevap akışı
- [x] Revizyon loop'u (max 3 iterasyon)
- [x] Error handling ve logging

### 3.2 Admin Komutları ✅ TAMAMLANDI
- [x] `/start` — Hoşgeldin mesajı (admin only)
- [x] `/reply <metin>` — Casual→Professional dönüşüm (admin only)
- [x] `/show_cv` — CV'yi göster (text + document) (admin only)
- [x] `/status` — Bot durumu ve istatistikler (admin only)
- [x] `/update_cv` — CV dosyasını güncelle (.txt yükle) (admin only)
- [x] `/add_info <metin>` — CV'ye bilgi ekle (admin only)
- [x] `/remove_info <metin>` — CV'den bilgi sil (admin only)

### 3.3 Admin Bildirimleri ✅ TAMAMLANDI
- [x] Cevap onaylandığında skor ve iterasyon bilgisi
- [x] Intervention tetiklendiğinde alert:
  ```
  ⚠️ INTERVENTION GEREKLİ
  Sebep: salary_negotiation
  İşveren Mesajı: ...
  Taslak Cevap: ...
  ```
- [x] Max iterasyon aşıldığında uyarı

### 3.4 İnsan Müdahalesi Tetikleyicileri ✅ TAMAMLANDI (EvaluatorAgent içinde)
- [x] Maaş/ücret pazarlığı tespiti (`salary_negotiation`)
- [x] Hukuki soru tespiti (`legal_question`)
- [x] Uzmanlık dışı teknik soru tespiti (`out_of_domain`)
- [x] Belirsiz/muğlak iş teklifi tespiti (`ambiguous_offer`)
- [x] Konu dışı mesaj tespiti (`off_topic`)

---

## 4. ⏳ FAZ 4 — EvalOps & Loglama

### 4.1 Logger (`tools/logger.py`)
- [ ] Her interaksiyonu CSV'ye logla:
  - [ ] `timestamp`
  - [ ] `employer_message`
  - [ ] `draft_response`
  - [ ] `truthfulness_score`
  - [ ] `robustness_score`
  - [ ] `helpfulness_score`
  - [ ] `tone_score`
  - [ ] `overall_score`
  - [ ] `feedback`
  - [ ] `final_response`
  - [ ] `category` (interview / technical / offer / unknown)
  - [ ] `iterations` (kaç revizyonda onaylandı)
  - [ ] `intervention_triggered`
- [ ] Log dosyasının Docker volume'a yazıldığını doğrula
- [ ] CSV'yi okuyup özet istatistik döndüren fonksiyon yaz

### 4.2 Dataset Hazırlığı
- [ ] En az 3 test case'i çalıştır ve logla
- [ ] CSV'yi kontrol et, eksik/hatalı satır var mı bak
- [ ] HuggingFace'e yüklemek için dataset formatını hazırla

---

## 5. ⏳ FAZ 5 — Dashboard (React)

### 5.1 FastAPI Kurulumu (`api/main.py`)
- [ ] `fastapi` ve `uvicorn` dependency'lerini ekle
- [ ] `/logs` endpoint'i yaz — `logs.csv`'yi okuyup JSON döner
- [ ] `/stats` endpoint'i yaz — özet istatistikleri döner
- [ ] CORS ayarlarını yap (React'tan erişim için)
- [ ] Docker'a FastAPI servisini ekle

### 5.2 React Kurulumu
- [ ] `dashboard/` klasöründe yeni React projesi oluştur (`vite` ile)
- [ ] Gerekli kütüphaneleri ekle: `recharts`, `tailwindcss`

### 5.3 Sayfalar & Bileşenler
- [ ] Ana sayfa: Proje açıklaması + mimari özeti
- [ ] Metrik kartları: 4 metriğin ortalama skorları
- [ ] Radar chart: Per-metrik güven skoru görselleştirmesi
- [ ] Tablo: Son değerlendirmeler (CSV'den)
- [ ] İstatistikler:
  - [ ] Toplam işlenen mesaj sayısı
  - [ ] İlk denemede onay oranı
  - [ ] Ortalama iterasyon sayısı
  - [ ] Müdahale tetiklenme sayısı
- [ ] Telegram bot linki butonu

### 5.4 Veri Bağlantısı
- [ ] FastAPI `/logs` endpoint'ini çağır → JSON olarak al → tabloya bas
- [ ] Vercel'e deploy için `vercel.json` ayarlarını yap

---

## 6. ⏳ FAZ 6 — Deploy

### 6.1 Railway (Bot + Backend)
- [ ] Railway hesabı oluştur / giriş yap
- [ ] GitHub reposunu Railway'e bağla
- [ ] Environment variable'ları Railway dashboard'una ekle
- [ ] İlk deploy'u yap ve logları kontrol et
- [ ] Bot'un Railway'de düzgün çalıştığını Telegram'dan test et

### 6.2 Vercel (Dashboard)
- [ ] Vercel hesabı oluştur / giriş yap
- [ ] `dashboard/` klasörünü Vercel'e bağla
- [ ] Deploy et ve linki al
- [ ] README'deki dashboard linkini güncelle

---

## 7. ✅ FAZ 7 — Test, Dokümantasyon & Teslim

### 7.1 3 Zorunlu Test Case
- [ ] **Test 1 — Mülakat Daveti:** "We'd like to invite you for a technical interview next week. Are you available?"
  - [ ] Agent cevap üretiyor mu?
  - [ ] Judge onaylıyor mu?
  - [ ] Log'a yazıldı mı?
- [ ] **Test 2 — Teknik Soru:** "Can you describe your experience with building evaluation pipelines for LLMs?"
  - [ ] Truthfulness skoru yüksek mi? (CV'ye uygun)
  - [ ] Hallucination tespit edildi mi?
  - [ ] Log'a yazıldı mı?
- [ ] **Test 3 — Bilinmeyen/Müdahale:** "We're offering a base salary of $90,000 + equity. Does that work for you?"
  - [ ] `trigger_human_intervention: true` döndü mü?
  - [ ] Sana Telegram bildirimi geldi mi?
  - [ ] Bot beklemeye alındı mı?

### 7.2 Dokümantasyon
- [ ] Flow diyagramı çiz (`draw.io` veya `Excalidraw`)
- [ ] Prompt tasarımı dokümante et (career + judge promptları)
- [ ] 3-5 sayfalık raporu yaz:
  - [ ] Design decisions
  - [ ] Evaluation strategy
  - [ ] Failure cases
  - [ ] Reflection
- [ ] README'yi son kez gözden geçir
- [ ] HuggingFace'e dataset'i yükle

### 7.3 Son Kontroller
- [ ] Docker lokal'de çalışıyor mu?
- [ ] Railway'de bot aktif mi?
- [ ] Vercel dashboard'u açılıyor mu?
- [ ] 3 test case logları CSV'de var mı?
- [ ] GitHub repo public mı?

---

## 8. 📦 Teslim Edilecekler

- [ ] ✅ Çalışan demo (Railway bot linki + Vercel dashboard)
- [ ] ✅ GitHub kaynak kodu
- [ ] ✅ Mimari diyagram
- [ ] ✅ 3 test case sonuçları (loglar + ekran görüntüleri)
- [ ] ✅ Kısa rapor (3-5 sayfa)
- [ ] ✅ HuggingFace dataset

---

> 💡 **Not:** Overengineering yapma. Her faz bittikten sonra çalıştır, test et, bir sonraki faza geç.