"""PipeFuncs that read the raw ticket list: weekly figures, and SLA breaches.

Both aggregate the same frame, so they share `_tickets.py` and sit together.
"""

from __future__ import annotations

from _tickets import SLA_HOURS, mean_satisfaction, tickets_frame
from pipelex.core.memory.working_memory import WorkingMemory
from pipelex.core.stuffs.list_content import ListContent
from pipelex.system.registries.func_registry import pipe_func
from structures import (
    CategoryStat,
    SlaBreach,
    TicketRow,
    TicketStats,
)


@pipe_func()
async def compute_ticket_stats(working_memory: WorkingMemory) -> TicketStats:
    """Aggregate the week's tickets into totals and a per-category breakdown."""
    rows = working_memory.get_stuff_as_list("tickets", item_type=TicketRow)
    frame = tickets_frame(rows.items)

    by_category: list[CategoryStat] = []
    if not frame.empty:
        # Busiest category first, so the digest's table leads with what mattered most.
        for category, group in sorted(frame.groupby("category"), key=lambda pair: -len(pair[1])):
            by_category.append(
                CategoryStat(
                    category=str(category),
                    ticket_count=int(len(group)),
                    median_resolution_hours=round(float(group["resolution_hours"].median()), 2),
                    mean_satisfaction=mean_satisfaction(group),
                )
            )

    median_hours = 0.0 if frame.empty else round(float(frame["resolution_hours"].median()), 2)
    return TicketStats(
        total_tickets=int(len(frame)),
        median_resolution_hours=median_hours,
        mean_satisfaction=mean_satisfaction(frame),
        by_category=by_category,
    )


@pipe_func()
async def detect_sla_breaches(working_memory: WorkingMemory) -> ListContent[SlaBreach]:
    """List the tickets that resolved outside the SLA allowed for their priority."""
    rows = working_memory.get_stuff_as_list("tickets", item_type=TicketRow)
    frame = tickets_frame(rows.items)

    breaches: list[SlaBreach] = []
    for record in frame.to_dict("records"):
        # An unknown priority has no SLA to breach — skip rather than invent one.
        allowed = SLA_HOURS.get(str(record["priority"]))
        if allowed is None or float(record["resolution_hours"]) <= allowed:
            continue
        breaches.append(
            SlaBreach(
                ticket_id=str(record["ticket_id"]),
                category=str(record["category"]),
                priority=str(record["priority"]),
                resolution_hours=round(float(record["resolution_hours"]), 2),
                allowed_hours=allowed,
            )
        )

    # Worst overrun first.
    breaches.sort(key=lambda breach: breach.allowed_hours - breach.resolution_hours)
    return ListContent(items=breaches)
