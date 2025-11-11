from app import celery, mail, db
from app.models import RentReminder, RentPayment, DailyTaskLog, Lease
from flask import current_app
from flask_mail import Message
from datetime import datetime, date
from app.utils.helper import TwilioHelper, log_notification


@celery.task(name="app.tasks.send_email_task")
def send_email_task(subject, recipients, body, tenant_id=None):
    """Send email and log notification."""
    try:
        msg = Message(subject, recipients=recipients, body=body)
        mail.send(msg)
        current_app.logger.info(f"Email sent to {recipients}")

        log_notification(
            tenant_id=tenant_id,
            message=body,
            notification_type="Email",
            status="sent"
        )
    except Exception as e:
        current_app.logger.error(
            f"Failed to send email to {recipients}: {e}", exc_info=True
        )
        log_notification(
            tenant_id=tenant_id,
            message=body,
            notification_type="Email",
            status="failed"
        )


@celery.task(name="app.tasks.send_rent_notifications_task")
def send_rent_notifications_task():
    """Send due rent notifications to tenants (idempotent)."""
    twilio = TwilioHelper()
    today = date.today()

    # Prevent double execution on same day
    existing = DailyTaskLog.query.filter_by(
        task_name="send_rent_notifications",
        run_date=today
    ).first()
    if existing:
        current_app.logger.info("Task already executed today. Skipping.")
        return "Already ran today"

    # Insert log BEFORE processing to prevent race condition
    new_log = DailyTaskLog(task_name="send_rent_notifications", run_date=today)
    db.session.add(new_log)
    db.session.flush()

    reminders = RentReminder.query.filter(
        RentReminder.due_date == today,
        RentReminder.reminder_sent.is_(False)
    ).all()

    current_app.logger.info(f"[{today}] Found {len(reminders)} reminders for today.")

    for reminder in reminders:
        try:
            lease = Lease.query.get(reminder.lease_id)
            if not lease:
                current_app.logger.warning(
                    f"Skipping reminder {reminder.id} - lease not found."
                )
                continue

            tenant = lease.tenant
            property_ = lease.property
            landlord = property_.owner if property_ else None

            if not tenant or not property_ or not landlord:
                current_app.logger.warning(
                    f"Skipping reminder {reminder.id} - missing tenant/property/landlord."
                )
                continue

            # Skip if rent already paid for this month
            already_paid = RentPayment.query.filter(
                RentPayment.tenant_id == tenant.id,
                RentPayment.property_id == property_.id,
                db.extract("month", RentPayment.payment_date) == today.month,
                db.extract("year", RentPayment.payment_date) == today.year
            ).first()

            if already_paid:
                current_app.logger.info(
                    f"Skipping tenant {tenant.name} - rent already paid for this month."
                )
            else:
                # Auto-generate pending payment
                new_payment = RentPayment(
                    tenant_id=tenant.id,
                    property_id=property_.id,
                    amount=property_.monthly_rent,
                    payment_date=today,
                    status="pending",
                    payment_mode="Cash"
                )
                db.session.add(new_payment)

            # Human-readable month
            month = reminder.due_date.strftime("%B %Y")

            tenant_msg = (
                f"Hello {tenant.name},\n\n"
                f"Your rent of Rs {property_.monthly_rent:.2f} is due on "
                f"{reminder.due_date.strftime('%d %b %Y')} for {month}. "
                f"Please pay on time.\n\nThanks!"
            )

            landlord_msg = (
                f"Reminder sent to tenant {tenant.name} for rent Rs {property_.monthly_rent:.2f} "
                f"due on {reminder.due_date.strftime('%d %b %Y')}."
            )

            # Send email to tenant
            if tenant.email:
                send_email_task.delay(
                    "Rent Payment Reminder", [tenant.email], tenant_msg, tenant_id=tenant.id
                )

            # Send SMS / WhatsApp to tenant
            if tenant.phone_number:
                try:
                    sid = twilio.send_sms(tenant.phone_number, tenant_msg, tenant_id=tenant.id)
                    current_app.logger.info(f"SMS sent to tenant {tenant.phone_number}, SID: {sid}")
                except Exception as e:
                    current_app.logger.error(
                        f"Failed to send SMS to tenant {tenant.phone_number}: {e}",
                        exc_info=True
                    )

                try:
                    twilio.send_whatsapp(tenant.phone_number, tenant_msg, tenant_id=tenant.id)
                    current_app.logger.info(f"WhatsApp sent to tenant {tenant.phone_number}")
                except Exception as e:
                    current_app.logger.error(
                        f"Failed to send WhatsApp to tenant {tenant.phone_number}: {e}",
                        exc_info=True
                    )

            # Notify landlord
            if landlord.email:
                send_email_task.delay(
                    "Tenant Rent Reminder Sent", [landlord.email], landlord_msg, tenant_id=tenant.id
                )

            if landlord.contact:
                try:
                    sid = twilio.send_sms(
                        landlord.contact, landlord_msg, tenant_id=tenant.id, landlord_id=landlord.id
                    )
                    current_app.logger.info(f"SMS sent to landlord {landlord.contact}, SID: {sid}")
                except Exception as e:
                    current_app.logger.error(
                        f"Failed to send SMS to landlord {landlord.contact}: {e}",
                        exc_info=True
                    )

                try:
                    twilio.send_whatsapp(landlord.contact, landlord_msg, tenant_id=tenant.id)
                    current_app.logger.info(f"WhatsApp sent to landlord {landlord.contact}")
                except Exception as e:
                    current_app.logger.error(
                        f"Failed to send WhatsApp to landlord {landlord.contact}: {e}",
                        exc_info=True
                    )

            # Mark reminder as sent
            reminder.reminder_sent = True
            reminder.last_sent_date = today

        except Exception as inner_e:
            current_app.logger.error(
                f"Error processing reminder {reminder.id}: {inner_e}", exc_info=True
            )

    # Commit all changes
    try:
        db.session.commit()
        current_app.logger.info("All reminders processed successfully.")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to commit reminder changes: {e}", exc_info=True)


@celery.task(name="app.tasks.auto_end_expired_leases")
def auto_end_expired_leases():
    """Set lease status to 'ended' if lease_end_date has passed."""
    today = date.today()

    # Prevent duplicate runs
    existing = DailyTaskLog.query.filter_by(
        task_name="auto_end_expired_leases",
        run_date=today
    ).first()
    if existing:
        current_app.logger.info("auto_end_expired_leases already executed today. Skipping.")
        return "Already ran today"

    new_log = DailyTaskLog(task_name="auto_end_expired_leases", run_date=today)
    db.session.add(new_log)
    db.session.flush()

    try:
        expired_leases = Lease.query.filter(
            Lease.lease_end_date.isnot(None),
            Lease.lease_end_date < today,
            Lease.status != "ended"
        ).all()

        for lease in expired_leases:
            lease.status = "ended"

        if expired_leases:
            db.session.commit()
            current_app.logger.info(f"{len(expired_leases)} leases updated to 'ended'.")
        else:
            current_app.logger.info("No leases to update.")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating expired leases: {e}", exc_info=True)


@celery.task(name="app.tasks.update_overdue_payments")
def update_overdue_payments():
    """Mark pending payments as late if due date passed."""
    today = date.today()
    updated_count = 0

    # Prevent duplicate runs
    existing = DailyTaskLog.query.filter_by(
        task_name="update_overdue_payments",
        run_date=today
    ).first()
    if existing:
        current_app.logger.info("update_overdue_payments already executed today. Skipping.")
        return "Already ran today"

    new_log = DailyTaskLog(task_name="update_overdue_payments", run_date=today)
    db.session.add(new_log)
    db.session.flush()

    try:
        pending_payments = RentPayment.query.filter(
            RentPayment.status == "pending"
        ).all()

        for payment in pending_payments:
            lease = Lease.query.filter_by(
                tenant_id=payment.tenant_id,
                property_id=payment.property_id,
                status="active"
            ).first()

            if lease:
                rent_due_date = date(today.year, today.month, lease.due_day)
                if today > rent_due_date:
                    payment.status = "late"
                    updated_count += 1

        if updated_count > 0:
            db.session.commit()
            current_app.logger.info(f"[Scheduler] Marked {updated_count} payments as late.")
        else:
            current_app.logger.info("[Scheduler] No overdue payments today.")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating overdue payments: {e}", exc_info=True)


@celery.task(name="app.tasks.test_celery_task")
def test_celery_task():
    print("✅ Celery test task executed successfully!")
    return "Celery is connected and running fine 🎉"