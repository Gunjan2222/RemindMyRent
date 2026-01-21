from celery.schedules import crontab
from app import celery

# ✅ Set timezone for India
celery.conf.timezone = "Asia/Kolkata"
celery.conf.enable_utc = False  # ensure local time (important!)

celery.conf.beat_schedule = {
#     # Daily reminder check (runs every day at 9 AM)
    "send-rent-reminders-daily": {
        "task": "app.tasks.send_rent_reminders",
        "schedule": crontab(hour=9, minute=0),
    },

    # Monthly payment generation (1st of every month)
    "generate-monthly-payments": {
        "task": "app.tasks.generate_monthly_payments",
        "schedule": crontab(day_of_month=1, hour=0, minute=5),
    },
}
