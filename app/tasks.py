from app import celery, mail, db
from app.models import RentReminder, RentPayment, User
from flask import current_app
from flask_mail import Message
from datetime import datetime, date
from app.utils.helper import TwilioHelper

def send_email(subject, recipients, body):
    """Helper to send email."""
    try:
        msg = Message(subject, recipients=recipients, body=body)
        mail.send(msg)
        current_app.logger.info(f"Email sent to {recipients}")
    except Exception as e:
        current_app.logger.error(f"Failed to send email to {recipients}: {e}", exc_info=True)

@celery.task(name='send_rent_reminder')
def send_rent_reminder(email, tenant_name, rent_amount, due_date):
    """Send rent reminder email to a tenant."""
    try:
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
        current_app.logger.info(f"Email reminder sent to {email} for due date {due_date}")
    except Exception as e:
        current_app.logger.error(f"Failed to send email to {email}: {e}", exc_info=True)

@celery.task(name='send_rent_notifications_task')
def send_rent_notifications_task():
    """Send due rent notifications to tenants and optionally notify landlord."""
    twilio = TwilioHelper()
    today = date.today()
    first_of_month = date(today.year, today.month, 1)
    next_month = date(today.year + int(today.month / 12), (today.month % 12) + 1, 1)

    reminders = RentReminder.query.filter(
        RentReminder.due_day == today.day,
        (RentReminder.last_notified.is_(None)) | (RentReminder.last_notified < today)
    ).all()

    current_app.logger.info(f"[{today}] Found {len(reminders)} reminders for today.")

    for reminder in reminders:
        landlord = User.query.get(reminder.user_id)
        if not landlord:
            current_app.logger.warning(f"Skipping reminder {reminder.id} - landlord not found.")
            continue

        current_app.logger.info(f"Processing tenant: {reminder.tenant_name} (ID: {reminder.id})")

        # Skip if rent already paid this month
        already_paid = RentPayment.query.filter(
            RentPayment.tenant_id == reminder.id,
            RentPayment.for_month >= first_of_month,
            RentPayment.for_month < next_month
        ).first()
        if already_paid:
            current_app.logger.info(f"Skipping {reminder.tenant_name} - already paid for this month.")
            continue

        due_date = date(today.year, today.month, reminder.due_day)
        month_str = due_date.strftime('%B %Y')

        # --- Notify tenant by email ---
        try:
            send_rent_reminder.delay(
                reminder.email,
                reminder.tenant_name,
                reminder.rent_amount,
                due_date
            )
            current_app.logger.info(f"Email reminder queued for tenant {reminder.email}")
        except Exception as e:
            current_app.logger.error(f"Failed to queue tenant email: {e}", exc_info=True)

        # --- Notify tenant by SMS ---
        if reminder.phone_number:
            sms_body_tenant = (
                f"Hi {reminder.tenant_name}, your rent of Rs{reminder.rent_amount:.2f} "
                f"is due on {due_date.strftime('%d %b %Y')}. Please pay on time."
            )
            try:
                sid = twilio.send_sms(reminder.phone_number, sms_body_tenant)
                current_app.logger.info(f"SMS sent to tenant {reminder.phone_number}, SID: {sid}")
            except Exception as e:
                current_app.logger.error(f"Failed to send SMS to tenant {reminder.phone_number}: {e}", exc_info=True)

        # --- Notify landlord ---
        landlord_msg = (
            f"Reminder sent to tenant {reminder.tenant_name} for rent Rs{reminder.rent_amount:.2f} "
            f"due on {due_date.strftime('%d %b %Y')} ({month_str})."
        )

        try:
            send_email("Tenant Rent Reminder Sent", [landlord.email], landlord_msg)
        except Exception as e:
            current_app.logger.error(f"Failed to send landlord email to {landlord.email}: {e}", exc_info=True)

        if landlord.contact:
            try:
                sid = twilio.send_sms(landlord.contact, landlord_msg)
                current_app.logger.info(f"SMS sent to landlord {landlord.contact}, SID: {sid}")
            except Exception as e:
                current_app.logger.error(f"Failed to send SMS to landlord {landlord.contact}: {e}", exc_info=True)

        # --- Update last_notified ---
        reminder.last_notified = today
        try:
            db.session.commit()
        except Exception as e:
            current_app.logger.error(f"Failed to commit reminder {reminder.id}: {e}", exc_info=True)
            db.session.rollback()

    current_app.logger.info("All reminders processed.")
