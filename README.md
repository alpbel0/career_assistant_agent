# 🤖 Career Assistant AI Agent

An intelligent AI agent system that communicates with potential employers on your behalf — featuring a multi-agent evaluation pipeline built with EvalOps principles.

---

## 📌 Overview

This project implements a **self-evaluating Career AI Agent** via Telegram. When a potential employer sends a message, the system:

1. Generates a professional response using your CV as context
2. Evaluates the response using a **Judge Agent** with 4 metrics
3. Automatically revises if the score is below threshold
4. Sends a **Telegram notification** to you when approved or when human intervention is needed
5. Logs every interaction for dataset generation

> Built as part of an AI Agents course assignment — with a focus on **EvalOps**: systematic, metric-driven evaluation of LLM outputs.

---

## 🏗️ Architecture

```
Employer Message (Telegram)
        ↓
  Career Agent (OpenRouter LLM)
  → Reads CV context
  → Generates draft response
        ↓
  Evaluator / Judge Agent (OpenRouter LLM)
  → Scores response on 4 metrics
  → Returns structured JSON
        ↓
  Score >= Threshold?
  ✅ YES → Send response + notify you
  ❌ NO  → Revise (max 3 iterations)
  ⚠️ INTERVENTION → Pause + alert you
        ↓
  Log everything → CSV → FastAPI → React Dashboard → HuggingFace Dataset
```

---

## 🧠 EvalOps — Evaluation Metrics

The Judge Agent scores every response on 4 core dimensions (1–5 scale):

| Metric | Description |
|---|---|
| **Truthfulness** | Is the response grounded in your CV? No hallucinations? |
| **Robustness** | Does it handle unexpected/adversarial messages well? Prompt injection resistant? |
| **Helpfulness** | Does it actually answer what the employer asked? |
| **Professional Tone** | Professional, clear, polite — even when declining? |

### Judge Agent Output (JSON)

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
  "feedback": "Response is accurate and professional. Slightly verbose but acceptable."
}
```

---

## 🧑‍💼 Human-in-the-Loop — Enhanced Intervention

When intervention is needed, you send the bot a short, casual instruction. The system transforms it into a polished, professional message — the employer always receives corporate-grade language, never your raw note.

**Flow:**

```
You write to the bot (short, casual):
"Accept but ask if they offer hybrid"
        ↓
Career Agent (gpt-4o-mini) professionalizes it:
"Thank you for the invitation. I would be happy to proceed.
Before the interview, could I ask whether this position
offers a hybrid working arrangement?"
        ↓
Judge Agent checks the tone score
        ↓
Employer receives a polished, professional message
```

> Even when you intervene manually, the system never compromises on the **Professional Tone** metric.

---

## ⚠️ Human Intervention Triggers

The agent automatically pauses and notifies you when:

- 💰 **Salary negotiation** — any discussion of compensation
- ⚖️ **Legal questions** — contract terms, NDAs, clauses
- 🔬 **Out-of-domain technical questions** — outside your expertise
- 🌫️ **Ambiguous job offers** — unclear role, company, or terms
- 🚫 **Off-topic messages** — unrelated to career/hiring

You receive a Telegram alert:
```
⚠️ HUMAN INTERVENTION NEEDED
Reason: salary_negotiation
Employer message: "We'd like to offer you 85,000..."
→ Bot is paused. Please respond manually.
```

---

## 🗂️ Dataset & Logging

Every interaction is logged:

```
timestamp | employer_message | draft_response | eval_scores | feedback | final_response | category | iterations
```

After collecting interactions, the dataset is published to **HuggingFace** as:
> `career-agent-evaluation-dataset`

This enables downstream research on LLM-as-a-Judge quality for professional communication tasks.

---

## 🛠️ Tech Stack

| Component | Technology |
|---|---|
| LLM | OpenRouter |
| Career Agent Model | `openai/gpt-4o-mini` |
| Judge Agent Model | `minimax/minimax-m2.5` |
| Bot Interface | Telegram Bot API |
| Backend | Python + FastAPI |
| Containerization | Docker |
| Deployment | Railway |
| Frontend / Dashboard | React + Vercel |
| Memory | `history.json` — per-employer conversation history |
| CV Context | Hybrid: Static (short) / ChromaDB RAG (long) |
| Dataset | HuggingFace |

---

## 🧩 CV Context Strategy

The agent uses a **hybrid approach** for injecting CV context into prompts:

```python
# Short CV → embed directly into prompt
# Long CV → retrieve relevant chunks via ChromaDB (RAG)
if len(cv_content) < 2000:
    context = cv_content        # static, full context
else:
    context = chroma.query(employer_message)  # RAG, relevant chunks only
```

This ensures the system stays efficient as your CV grows over time via `/add_info` commands — only the relevant parts of your profile are sent to the LLM.

---

## 📋 CV Management (via Telegram)

Update your profile anytime without touching the code or redeploying:

| Command | Description |
|---|---|
| `/update_cv` | Replace entire CV by sending a new `.txt` file |
| `/add_info <text>` | Append new information to your CV |
| `/remove_info <text>` | Remove a specific line from your CV |
| `/show_cv` | Display your current CV |

All commands are admin-only — protected by your `TELEGRAM_CHAT_ID`.

---

## ✅ Core Features

- **Multi-agent pipeline** — Career Agent + Judge Agent
- **4-metric evaluation** — structured JSON scoring on every response (Truthfulness, Robustness, Helpfulness, Tone)
- **Auto-revision loop** — up to 3 iterations before escalation
- **Human intervention system** — 5 trigger categories
- **Memory** — full conversation history tracked per employer
- **CV management via Telegram** — update, append, or remove profile info without redeploying
- **Confidence visualization** — per-metric radar chart in dashboard
- **Automatic dataset generation** — every interaction logged and published to HuggingFace
- **Cloud deployment** — bot on Railway, dashboard on Vercel

---

## 📁 Project Structure

```
career-agent/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
│
├── agent/
│   ├── career_agent.py       # Draft response generation
│   ├── evaluator_agent.py    # Judge Agent (LLM-as-a-Judge)
│   └── prompts/
│       ├── career_prompt.txt
│       └── evaluator_prompt.txt
│
├── api/
│   └── main.py               # FastAPI — serves logs to React dashboard
│
├── bot/
│   └── telegram_bot.py       # Telegram interface + notification logic
│
├── tools/
│   ├── intervention.py       # Human intervention detection & alert
│   └── logger.py             # CSV logging
│
├── data/
│   ├── cv.txt                # Your CV/profile (static context)
│   ├── history.json          # Memory (per-employer conversation history)
│   └── logs.csv              # Evaluation logs → HuggingFace dataset
│
└── dashboard/                # React frontend (separate repo/folder)
```

---

## 🧪 Test Cases

### Test 1 — Interview Invitation
> "We'd like to invite you for a technical interview next week. Are you available?"

Expected: Agent accepts professionally, proposes availability, no intervention triggered.

### Test 2 — Technical Question
> "Can you describe your experience with building evaluation pipelines for LLMs?"

Expected: Agent answers based on CV, high truthfulness score, no hallucination.

### Test 3 — Unknown / Intervention Required
> "We're offering a base salary of $90,000 + equity. Does that work for you?"

Expected: `trigger_human_intervention: true`, reason: `salary_negotiation`, bot pauses.

---

## 🚀 Getting Started

### Prerequisites
- Docker
- Telegram Bot Token (`@BotFather`)
- OpenRouter API Key
- Railway account (for deployment)

### Local Setup

```bash
git clone https://github.com/yourusername/career-agent
cd career-agent
cp .env.example .env
# Fill in your API keys in .env

docker compose up --build
```

### Environment Variables

```env
OPENROUTER_API_KEY=your_key_here
TELEGRAM_BOT_TOKEN=your_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
CAREER_AGENT_MODEL=openai/gpt-4o-mini
JUDGE_AGENT_MODEL=minimax/minimax-m2.5
APPROVAL_THRESHOLD=4.0
```

### Deploy to Railway

```bash
railway login
railway up
```

---

## 📊 Dashboard

The React dashboard (deployed on Vercel) displays:

- Total messages processed
- Approval rate (first pass vs. revised)
- Metric breakdown (radar chart)
- Intervention log
- Sample evaluated conversations

🔗 [Live Dashboard](#) ← _link after deploy_

---

## 📄 License

MIT