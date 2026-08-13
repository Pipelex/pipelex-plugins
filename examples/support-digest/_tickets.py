"""Shared ticket helpers — no pipe funcs here, nothing registers from this module.

Both `compute_stats.py` pipe funcs start from the same ticket list, so the frame
they build and the SLA table they read live here rather than in either caller.
"""

from __future__ import annotations

import pandas as pd
from structures import TicketRow

# Hours a ticket of each priority is allowed before it counts as an SLA breach.
SLA_HOURS: dict[str, float] = {
    "urgent": 4.0,
    "high": 12.0,
    "medium": 48.0,
    "low": 120.0,
}

# CSAT is 1-5; 0 is the sentinel for "the requester never rated it" and must be
# excluded from means rather than dragging them toward zero.
UNRATED = 0


def tickets_frame(rows: list[TicketRow]) -> pd.DataFrame:
    """Build the working frame from the pipe's ticket rows.

    Returns an empty frame with the expected columns when there are no tickets,
    so every caller can aggregate without a special case for an empty week.
    """
    columns = ["ticket_id", "category", "priority", "resolution_hours", "satisfaction"]
    if not rows:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(
        [
            {
                "ticket_id": row.ticket_id,
                "category": row.category,
                "priority": row.priority,
                "resolution_hours": float(row.resolution_hours),
                "satisfaction": int(row.satisfaction),
            }
            for row in rows
        ],
        columns=columns,
    )


def mean_satisfaction(frame: pd.DataFrame) -> float:
    """Mean CSAT over rated tickets only; 0.0 when nothing in the frame was rated."""
    rated = frame.loc[frame["satisfaction"] != UNRATED, "satisfaction"]
    if rated.empty:
        return 0.0
    return round(float(rated.mean()), 2)
