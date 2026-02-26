from __future__ import annotations

import os
from pathlib import Path

from phase1_collector import MetricsDB, build_report_payload
from api.common import get_query_param, json_response


def handler(request):
    db_path = Path(os.getenv("DB_PATH", "social_metrics.db"))
    limit_str = get_query_param(request, "limit", "5")
    limit = int(limit_str) if limit_str.isdigit() else 5

    db = MetricsDB(db_path)
    db.initialize()
    payload = build_report_payload(db, limit=limit)

    return json_response(200, {"ok": True, "top_posts": payload, "db_path": str(db_path), "limit": limit})
