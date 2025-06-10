from celery.schedules import crontab
from app import celery

celery.conf.beat_schedule = {
    'daily-rent-notification': {
        'task': 'send_rent_notifications_task',
        'schedule': crontab(hour=8, minute=0),
    },
}
