from app import celery, db
from app.models import Tenant, Payment, ReminderLog
from flask import current_app
from datetime import datetime, date, timedelta
from utils.helper import EmailHelper

@celery.task(bind=True, autoretry_for=(Exception,), retry_kwargs={"max_retries": 3, "countdown": 30})
def generate_monthly_payments():
    try:
        today = date.today()
        month_str = today.strftime("%Y-%m")  # 2026-01

        tenants = Tenant.query.filter_by(is_active=True).all()


        for tenant in tenants:
            exists = Payment.query.filter_by(
                tenant_id=tenant.id,
                month=month_str
            ).first()

            if exists:
                continue

            payment = Payment(
                tenant_id=tenant.id,
                month=month_str,
                rent_amount=tenant.rent_amount,
                maintenance_amount=tenant.maintenance_amount,
                status="PENDING"
            )

            db.session.add(payment)

        db.session.commit()

        return {"message": f"{month_str} payments generated"}

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Payment generation failed: {e}", exc_info=True)
        return {"error": "Failed to generate payments"}

@celery.task(bind=True, autoretry_for=(Exception,), retry_kwargs={"max_retries": 3, "countdown": 60})
def send_rent_reminders():
    try:
        email_helper = EmailHelper()
        # whatsapp_helper = WhatsAppHelper()
        today = date.today()

        payments = (
            Payment.query
            .join(Tenant)
            .filter(Payment.status == "PENDING")
            .all()
        )

        for payment in payments:
            try:
                tenant = payment.tenant
                if not tenant or not tenant.due_day:
                    continue

                # payment.month format -> "YYYY-MM"
                year, month = map(int, payment.month.split("-"))

                # Create due date safely
                try:
                    due_date = date(year, month, tenant.due_day)
                except ValueError:
                    current_app.logger.warning(
                        f"Invalid due date for tenant {tenant.id}"
                    )
                    continue

                # Decide reminder type
                if today == due_date - timedelta(days=2):
                    reminder_type = "BEFORE"
                elif today == due_date:
                    reminder_type = "ON"
                elif today == due_date + timedelta(days=3):
                    reminder_type = "AFTER"
                else:
                    continue

                # Prevent duplicate reminder
                already_sent = ReminderLog.query.filter_by(
                    payment_id=payment.id,
                    reminder_type=reminder_type
                ).first()

                if already_sent:
                    continue

                # -------------------
                # 📧 Email Reminder
                # -------------------
                if tenant.email:
                    email_helper.send_rent_email(
                        tenant, payment, reminder_type
                    )

                    db.session.add(ReminderLog(
                        payment_id=payment.id,
                        reminder_type=reminder_type,
                        sent_via="EMAIL"
                    ))

                # -------------------
                # 📲 WhatsApp (2 times)
                # -------------------
                # if tenant.phone:
                #     for _ in range(2):
                #         whatsapp_helper.send_rent_whatsapp(
                #             tenant, payment, reminder_type
                #         )

                #         db.session.add(ReminderLog(
                #             payment_id=payment.id,
                #             reminder_type=reminder_type,
                #             sent_via="WHATSAPP"
                #         ))

                current_app.logger.info(
                    f"{reminder_type} reminder sent to {tenant.name}"
                )

            except Exception as inner_error:
                db.session.rollback()
                current_app.logger.error(
                    f"Error processing payment {payment.id}: {inner_error}",
                    exc_info=True
                )
                continue

        db.session.commit()

    except Exception as e:
        db.session.rollback()
        current_app.logger.critical(
            f"Reminder job failed: {e}", exc_info=True
        )



# @celery.task(name="app.tasks.send_rent_notifications_task")
