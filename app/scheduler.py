from celery.schedules import crontab
from app import celery

# ✅ Set timezone for India
celery.conf.timezone = "Asia/Kolkata"
celery.conf.enable_utc = False  # ensure local time (important!)

celery.conf.beat_schedule = {
    # 📅 Send rent reminders every day at 7:15 PM IST
    "daily-rent-notification": {
        "task": "app.tasks.send_rent_notifications_task",
        "schedule": crontab(hour=10, minute=10),
    },

    # 🏠 Auto-end expired leases at midnight IST
    "auto-end-expired-leases": {
        "task": "app.tasks.auto_end_expired_leases",
        "schedule": crontab(hour=0, minute=0),
    },

    # 💰 Update overdue payments daily at 1:00 AM IST
    "update-overdue-payments": {
        "task": "app.tasks.update_overdue_payments",
        "schedule": crontab(hour=1, minute=0),
    },
}
