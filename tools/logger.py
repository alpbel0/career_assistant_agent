"""
Logger — EvalOps interaction logger for Career Assistant AI Agent.

Bu modül:
- Her interaksiyonu CSV'ye append eder (thread-safe)
- Keyword-based kategori tespiti yapar
- CSV'den özet istatistik hesaplar
"""

import csv
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

LOG_PATH = Path("data/logs.csv")

CSV_COLUMNS = [
    "timestamp",
    "employer_id",
    "employer_message",
    "draft_response",
    "truthfulness_score",
    "robustness_score",
    "helpfulness_score",
    "tone_score",
    "overall_score",
    "feedback",
    "final_response",
    "is_approved",
    "category",
    "message_type",
    "iterations",
    "intervention_triggered",
    "intervention_reason",
]

# Keyword maps for category detection
_CATEGORY_KEYWORDS = {
    "interview": [
        "mülakat", "görüşme", "interview", "invite", "davet", "meet",
        "tanışalım", "call", "zoom", "teams",
    ],
    "offer": [
        "maaş", "salary", "ücret", "pay", "compensation", "equity",
        "teklif", "offer", "pozisyon", "işe al", "hire",
    ],
    "technical": [
        "teknik", "technical", "experience", "deneyim", "proje", "project",
        "pipeline", "code", "kod", "llm", "ai", "ml", "python",
        "backend", "frontend", "api", "database",
    ],
}


def _detect_category(message: str) -> str:
    """
    Keyword-based message category detection.

    Args:
        message: Employer message text

    Returns:
        One of: 'interview', 'technical', 'offer', 'unknown'
    """
    lower = message.lower()
    for category, keywords in _CATEGORY_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return category
    return "unknown"


def _ensure_csv() -> None:
    """Create logs.csv with header if it doesn't exist."""
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not LOG_PATH.exists() or LOG_PATH.stat().st_size == 0:
        with open(LOG_PATH, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
            writer.writeheader()


def log_interaction(
    employer_id: str,
    employer_message: str,
    draft_response: str,
    evaluation: Optional[dict],
    final_response: str,
    is_approved: bool,
    iterations: int,
    intervention_triggered: bool,
    intervention_reason: Optional[str] = None,
    message_type: str = "unknown",
) -> None:
    """
    Append one interaction row to logs.csv.

    Args:
        employer_id: Unique employer identifier
        employer_message: Original message from employer
        draft_response: First generated draft (before revisions)
        evaluation: Final evaluation dict from EvaluatorAgent (may be None)
        final_response: Actual response sent (or last draft)
        is_approved: Whether the response was approved by Judge
        iterations: Number of revision iterations used
        intervention_triggered: Whether human intervention was required
        intervention_reason: Reason string for intervention (or None)
        message_type: Reserved field, default "unknown"
    """
    _ensure_csv()

    # Extract scores safely
    scores: dict[str, Any] = {}
    if evaluation:
        scores = {
            "truthfulness_score": evaluation.get("truthfulness_score", ""),
            "robustness_score": evaluation.get("robustness_score", ""),
            "helpfulness_score": evaluation.get("helpfulness_score", ""),
            "tone_score": evaluation.get("tone_score", ""),
            "overall_score": evaluation.get("overall_score", ""),
            "feedback": evaluation.get("feedback", ""),
        }
    else:
        scores = {
            "truthfulness_score": "",
            "robustness_score": "",
            "helpfulness_score": "",
            "tone_score": "",
            "overall_score": "",
            "feedback": "",
        }

    row = {
        "timestamp": datetime.now().isoformat(),
        "employer_id": employer_id,
        "employer_message": employer_message,
        "draft_response": draft_response,
        "truthfulness_score": scores["truthfulness_score"],
        "robustness_score": scores["robustness_score"],
        "helpfulness_score": scores["helpfulness_score"],
        "tone_score": scores["tone_score"],
        "overall_score": scores["overall_score"],
        "feedback": scores["feedback"],
        "final_response": final_response,
        "is_approved": is_approved,
        "category": _detect_category(employer_message),
        "message_type": message_type,
        "iterations": iterations,
        "intervention_triggered": intervention_triggered,
        "intervention_reason": intervention_reason or "",
    }

    with open(LOG_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writerow(row)


def get_summary_stats() -> dict:
    """
    Read logs.csv and return summary statistics.

    Returns:
        Dict with:
            - total_interactions: int
            - approval_rate: float (0.0 – 1.0)
            - avg_iterations: float
            - avg_overall_score: float
            - avg_truthfulness: float
            - avg_robustness: float
            - avg_helpfulness: float
            - avg_tone: float
            - intervention_count: int
            - category_counts: dict (interview/technical/offer/unknown counts)
    """
    _ensure_csv()

    rows = []
    with open(LOG_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        return {
            "total_interactions": 0,
            "approval_rate": 0.0,
            "avg_iterations": 0.0,
            "avg_overall_score": 0.0,
            "avg_truthfulness": 0.0,
            "avg_robustness": 0.0,
            "avg_helpfulness": 0.0,
            "avg_tone": 0.0,
            "intervention_count": 0,
            "category_counts": {
                "interview": 0,
                "technical": 0,
                "offer": 0,
                "unknown": 0,
            },
        }

    total = len(rows)

    def _safe_float(val: str) -> Optional[float]:
        try:
            return float(val)
        except (ValueError, TypeError):
            return None

    def _safe_bool(val: str) -> bool:
        return str(val).strip().lower() in ("true", "1", "yes")

    approved = sum(1 for r in rows if _safe_bool(r.get("is_approved", "")))
    intervention_count = sum(
        1 for r in rows if _safe_bool(r.get("intervention_triggered", ""))
    )

    iterations_vals = [
        v for r in rows if (v := _safe_float(r.get("iterations", ""))) is not None
    ]
    overall_vals = [
        v for r in rows if (v := _safe_float(r.get("overall_score", ""))) is not None
    ]
    truth_vals = [
        v for r in rows if (v := _safe_float(r.get("truthfulness_score", ""))) is not None
    ]
    robust_vals = [
        v for r in rows if (v := _safe_float(r.get("robustness_score", ""))) is not None
    ]
    helpful_vals = [
        v for r in rows if (v := _safe_float(r.get("helpfulness_score", ""))) is not None
    ]
    tone_vals = [
        v for r in rows if (v := _safe_float(r.get("tone_score", ""))) is not None
    ]

    category_counts: dict[str, int] = {"interview": 0, "technical": 0, "offer": 0, "unknown": 0}
    for r in rows:
        cat = r.get("category", "unknown")
        if cat in category_counts:
            category_counts[cat] += 1
        else:
            category_counts["unknown"] += 1

    def _avg(vals: list) -> float:
        return round(sum(vals) / len(vals), 2) if vals else 0.0

    return {
        "total_interactions": total,
        "approval_rate": round(approved / total, 2) if total else 0.0,
        "avg_iterations": _avg(iterations_vals),
        "avg_overall_score": _avg(overall_vals),
        "avg_truthfulness": _avg(truth_vals),
        "avg_robustness": _avg(robust_vals),
        "avg_helpfulness": _avg(helpful_vals),
        "avg_tone": _avg(tone_vals),
        "intervention_count": intervention_count,
        "category_counts": category_counts,
    }
