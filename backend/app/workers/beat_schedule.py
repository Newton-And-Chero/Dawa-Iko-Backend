"""Static Celery Beat schedule: recurring watchlist sweeps + the retry sweep.

Watchlist entries name a commodity by `keml_code` and a county, resolved to a
commodity id at task run time (`sweep_tasks.py`) rather than frozen here —
commodity UUIDs don't exist until the DB is seeded. Mirrors PROJECT.md's own
example: "sweep carbetocin across Kirinyaga weekly".
"""

from celery.schedules import crontab

# (commodity_keml_code, county) — data/seed/commodities_keml.json is the
# source of truth for these synthetic KEML codes.
WATCHLIST_SWEEPS: list[tuple[str, str]] = [
    ("KEML-SYN-0001", "Kirinyaga"),  # Carbetocin
    ("KEML-SYN-0003", "Nairobi"),  # Human Insulin (Soluble)
]

BEAT_SCHEDULE = {
    f"scheduled-sweep-{keml_code}-{county}": {
        "task": "app.workers.sweep_tasks.run_scheduled_sweep_task",
        "schedule": crontab(day_of_week="monday", hour=6, minute=0),
        "args": (keml_code, county),
    }
    for keml_code, county in WATCHLIST_SWEEPS
} | {
    "retry-failed-calls": {
        "task": "app.workers.sweep_tasks.retry_failed_calls_task",
        "schedule": crontab(minute=0),  # hourly
    }
}
