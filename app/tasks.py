from app import celery, mail, db
from app.models import RentReminder, RentPayment
from flask_mail import Message
from datetime import datetime, date
import logging

@celery.task(name='send_rent_reminder')
def send_rent_reminder(email, tenant_name, rent_amount, due_date):
    month = due_date.strftime('%B %Y')
    msg = Message(
        'Rent Payment Reminder',
        recipients=[email],
        body=(
            f'Hello {tenant_name},\n\n'
            f'Your rent of Rs{rent_amount:.2f} is due on {due_date} for {month}. '
            f'Please pay on time.\n\nThanks!'
        )
    )
    mail.send(msg)
    logging.warning(f"Reminder sent to {email} for {due_date}")

@celery.task(name='send_rent_notifications_task')
def send_rent_notifications_task():
    today = datetime.today().date()
    first_of_month = date(today.year, today.month, 1)

    reminders = RentReminder.query.filter(RentReminder.due_day == today.day).all()
    logging.warning(f"Found {len(reminders)} reminders for today.")

    for reminder in reminders:
        logging.warning(f"Checking reminder for tenant: {reminder.tenant_name}")
        if not RentPayment.query.filter_by(tenant_id=reminder.id, for_month=first_of_month).first():
            due_date = date(today.year, today.month, reminder.due_day)
            logging.warning(f"Sending reminder to {reminder.email} for due date {due_date}")
            send_rent_reminder.delay(reminder.email, reminder.tenant_name, reminder.rent_amount, due_date)
            reminder.last_notified = today

    db.session.commit()
    logging.warning("All reminders processed.")