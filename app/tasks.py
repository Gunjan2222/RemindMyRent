from app import celery, db
from app.models import Tenant, Payment, ReminderLog, PaymentStatus
from flask import current_app
from datetime import date, timedelta
from app.utils.helper import EmailHelper
from calendar import monthrange

@celery.task(bind=True, autoretry_for=(Exception,), retry_kwargs={"max_retries": 3, "countdown": 30})
def generate_monthly_payments(self):
    try:
        today = date.today()
        month_str = today.strftime("%Y-%m")  # e.g. 2026-01

        tenants = Tenant.query.filter_by(is_active=True).all()
        created = 0

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
                status=PaymentStatus.PENDING
            )

            db.session.add(payment)
            created += 1

        db.session.commit()

        current_app.logger.info(
            f"Monthly payments generated for {month_str}: {created}"
        )

        return {"month": month_str, "created": created}

    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            "Monthly payment generation failed"
        )
        raise

@celery.task(bind=True, autoretry_for=(Exception,), retry_kwargs={"max_retries": 3, "countdown": 60})
def send_rent_reminders(self):
    try:
        today = date.today()
        email_helper = EmailHelper()

        payments = (
            Payment.query
            .join(Tenant)
            .filter(Payment.status == PaymentStatus.PENDING)
            .all()
        )

        sent_count = 0

        for payment in payments:
            tenant = payment.tenant
            if not tenant or not tenant.due_day:
                continue

            # Parse payment month safely
            try:
                year, month = map(int, payment.month.split("-"))
                last_day = monthrange(year, month)[1]

                due_day = min(
                    tenant.due_day,
                    last_day
                )

                due_date = date(
                    year,
                    month,
                    due_day
                )
            except Exception:
                current_app.logger.warning(
                    f"Invalid due date for tenant {tenant.id}"
                )
                continue

            # Determine reminder type
            if today == due_date - timedelta(days=2):
                reminder_type = "BEFORE"
            elif today == due_date:
                reminder_type = "ON"
            elif today == due_date + timedelta(days=3):
                reminder_type = "AFTER"
            else:
                continue

            # Avoid duplicate reminders
            exists = ReminderLog.query.filter_by(
                payment_id=payment.id,
                reminder_type=reminder_type
            ).first()

            if exists:
                continue

            # -------------------
            # EMAIL REMINDER
            # -------------------
            if tenant.email:
                email_helper.send_rent_email(
                    tenant=tenant,
                    payment=payment,
                    reminder_type=reminder_type
                )

                db.session.add(ReminderLog(
                    payment_id=payment.id,
                    reminder_type=reminder_type,
                    sent_via="EMAIL"
                ))

                sent_count += 1

            current_app.logger.info(
                f"{reminder_type} reminder sent to {tenant.name}"
            )

        db.session.commit()
        return {"sent": sent_count}

    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            "Rent reminder task failed"
        )
        raise