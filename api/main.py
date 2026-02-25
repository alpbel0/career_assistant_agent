"""
FastAPI Backend — Career Assistant AI Agent Dashboard API

Endpoints:
    GET /         → health check
    GET /logs     → logs.csv'yi JSON olarak döner
    GET /stats    → özet istatistikler
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from tools.logger import get_summary_stats, LOG_PATH, CSV_COLUMNS

import csv

app = FastAPI(
    title="Career Assistant AI Agent API",
    description="EvalOps dashboard backend — serves evaluation logs and statistics.",
    version="1.0.0",
)

# CORS — React dashboard (Vercel) erişimi için
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/")
def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "career-assistant-api"}


@app.get("/logs")
def get_logs(limit: int = 100):
    """
    Return evaluation logs from logs.csv as JSON.

    Query params:
        limit: max rows to return (default 100, max 1000)
    """
    if not LOG_PATH.exists():
        return {"logs": [], "total": 0}

    limit = min(limit, 1000)

    rows = []
    try:
        with open(LOG_PATH, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Type coercions for numeric fields
                for field in [
                    "truthfulness_score", "robustness_score",
                    "helpfulness_score", "tone_score", "overall_score",
                ]:
                    try:
                        row[field] = float(row[field]) if row[field] else None
                    except ValueError:
                        row[field] = None

                for field in ["iterations"]:
                    try:
                        row[field] = int(row[field]) if row[field] else 0
                    except ValueError:
                        row[field] = 0

                for field in ["is_approved", "intervention_triggered"]:
                    row[field] = str(row.get(field, "")).lower() in ("true", "1")

                rows.append(row)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read logs: {e}")

    # Return most recent first
    rows.reverse()
    return {"logs": rows[:limit], "total": len(rows)}


@app.get("/stats")
def get_stats():
    """
    Return summary statistics computed from logs.csv.

    Returns:
        total_interactions, approval_rate, avg_iterations,
        avg_overall_score, avg per-metric scores,
        intervention_count, category_counts
    """
    try:
        stats = get_summary_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to compute stats: {e}")
