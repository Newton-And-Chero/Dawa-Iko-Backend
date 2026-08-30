from celery.schedules import crontab

WATCHLIST_SWEEPS: list[tuple[str, str]] = [
    ("KEML-SYN-0001", "Kirinyaga"),
    ("KEML-SYN-0003", "Nairobi"),
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
        "schedule": crontab(minute=0),
    },
    "recompute-facility-reliability": {
        "task": "app.workers.analytics_tasks.recompute_facility_reliability_task",
        "schedule": crontab(hour=2, minute=0),
    },
}
