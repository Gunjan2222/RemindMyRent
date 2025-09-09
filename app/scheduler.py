from celery.schedules import crontab
from app import celery

celery.conf.beat_schedule = {
    'daily-rent-notification': {
        'task': 'app.tasks.send_rent_notifications_task',
        'schedule': crontab(hour=19, minute=15),  # 7:15 PM
    },
    'auto-end-expired-leases': {
        'task': 'app.tasks.auto_end_expired_leases',
        'schedule': crontab(hour=0, minute=0),  # every day at midnight
    },
}
