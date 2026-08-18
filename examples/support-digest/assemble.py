"""The rendering PipeFunc: figures, themes, and actions into the finished digest.

Separate from `compute_stats.py` because it reads no raw tickets — it consumes what
the earlier steps produced and does formatting only.
"""

from __future__ import annotations

from pipelex.core.memory.working_memory import WorkingMemory
from pipelex.system.registries.func_registry import pipe_func
from structures import (
    ActionPlan,
    SlaBreach,
    SupportDigest,
    ThemeSummary,
    TicketStats,
)


def _stats_table(stats: TicketStats) -> str:
    """Render the per-category breakdown as a Markdown table."""
    header = "| Category | Tickets | Median hours | Mean CSAT |\n| --- | ---: | ---: | ---: |"
    if not stats.by_category:
        return f"{header}\n| _no tickets this week_ | 0 | 0 | 0 |"
    rows = [f"| {stat.category} | {stat.ticket_count} | {stat.median_resolution_hours} | {stat.mean_satisfaction} |" for stat in stats.by_category]
    return "\n".join([header, *rows])


def _headline(stats: TicketStats, breach_count: int) -> str:
    """One line a reader can take in without opening the table."""
    if stats.total_tickets == 0:
        return "No tickets closed this week."
    breaches = "no SLA breaches" if breach_count == 0 else f"{breach_count} SLA breach(es)"
    return (
        f"{stats.total_tickets} tickets closed, median {stats.median_resolution_hours}h "
        f"to resolution, mean CSAT {stats.mean_satisfaction}, {breaches}."
    )


@pipe_func()
async def assemble_digest(working_memory: WorkingMemory) -> SupportDigest:
    """Render the figures, themes, and actions into the finished digest."""
    stats = working_memory.get_stuff_as("stats", content_type=TicketStats)
    breaches = working_memory.get_stuff_as_list("breaches", item_type=SlaBreach)
    themes = working_memory.get_stuff_as("themes", content_type=ThemeSummary)
    actions = working_memory.get_stuff_as("actions", content_type=ActionPlan)

    breach_count = len(breaches.items)
    return SupportDigest(
        headline=_headline(stats, breach_count),
        stats_table=_stats_table(stats),
        breach_count=breach_count,
        narrative=themes.narrative,
        actions=list(actions.actions),
    )
