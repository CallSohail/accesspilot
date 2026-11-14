"""In-memory job store for completed reports.

The MVP keeps finished reports in memory so the user can download them as
JSON or HTML immediately after analyzing, without a database. Reports are
evicted when the store exceeds a small cap. This is intentionally
stateless-friendly: restarting the server clears completed jobs.
"""

from __future__ import annotations

import time
from collections import OrderedDict
from typing import Any

from .models import Report

_MAX_JOBS = 200


class JobStore:
    def __init__(self, max_jobs: int = _MAX_JOBS) -> None:
        self._data: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._max = max_jobs

    def add(self, report: Report) -> None:
        self._data[report.report_id] = {
            "report": report,
            "created_at": time.time(),
        }
        self._data.move_to_end(report.report_id)
        self._evict()

    def get(self, report_id: str) -> Report | None:
        item = self._data.get(report_id)
        if item is None:
            return None
        self._data.move_to_end(report_id)
        return item["report"]

    def _evict(self) -> None:
        while len(self._data) > self._max:
            self._data.popitem(last=False)
