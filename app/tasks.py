from app import celery, mail, db
from app.models import RentReminder, RentPayment
from flask_mail import Message
from datetime import datetime, date
from app.utils.helper import TwilioHelper
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
    twilio = TwilioHelper()
    today = datetime.today().date()
    first_of_month = date(today.year, today.month, 1)

    reminders = RentReminder.query.filter(RentReminder.due_day == today.day).all()
    logging.info(f"[{today}] Found {len(reminders)} reminders for today.")

    for reminder in reminders:
        logging.info(f"Checking tenant: {reminder.tenant_name} (ID: {reminder.id})")

        # Check if payment already exists for this month
        already_paid = RentPayment.query.filter_by(
            tenant_id=reminder.id,
            for_month=first_of_month
        ).first()

        if already_paid:
            logging.info(f"Skipping {reminder.tenant_name} - already paid for this month.")
            continue

        # Compose due date
        due_date = date(today.year, today.month, reminder.due_day)

        # Send email
        send_rent_reminder.delay(
            reminder.email,
            reminder.tenant_name,
            reminder.rent_amount,
            due_date
        )
        logging.info(f"Email reminder queued for {reminder.email}")

        # Send SMS
        if reminder.phone_number:
            sms_body = (
                f"Hi {reminder.tenant_name}, your rent of Rs{reminder.rent_amount:.2f} "
                f"is due on {due_date.strftime('%d %b %Y')}. Please pay on time."
            )
            sms_sid = twilio.send_sms(reminder.phone_number, sms_body)
            logging.info(f"SMS sent to {reminder.phone_number}, SID: {sms_sid}")

        # Update last_notified
        reminder.last_notified = today

    db.session.commit()
    logging.info("All reminders processed and committed.")