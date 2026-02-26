from __future__ import annotations

import os
from pathlib import Path

from phase1_collector import MetricsDB, run_collection
from api.common import get_header, get_query_param, json_response


def handler(request):
    token = os.getenv("CRON_SECRET")
    auth = get_header(request, "authorization", "")
    if token and auth != f"Bearer {token}":
        return json_response(401, {"ok": False, "error": "unauthorized"})

    max_posts_str = get_query_param(request, "max_posts", "10")
    max_posts = int(max_posts_str) if max_posts_str.isdigit() else 10
    db_path = Path(os.getenv("DB_PATH", "social_metrics.db"))

    db = MetricsDB(db_path)
    db.initialize()

    try:
        logs = run_collection(db, max_posts=max_posts)
    except Exception as exc:  # pragma: no cover
        return json_response(500, {"ok": False, "error": str(exc)})

    return json_response(200, {"ok": True, "logs": logs, "db_path": str(db_path), "max_posts": max_posts})
