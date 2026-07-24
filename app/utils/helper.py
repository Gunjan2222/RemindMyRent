import time
from flask import current_app
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt,
)
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Message
from twilio.rest import Client

from app import mail
from app.config import Config
from app.utils.token_blacklist import TokenBlacklist


# =====================================================
# Authentication Helper
# =====================================================

class AuthHelper:
    def __init__(self):
        self.secret_key = Config.JWT_SECRET_KEY
        self.access_expires = Config.JWT_ACCESS_TOKEN_EXPIRES
        self.refresh_expires = Config.JWT_REFRESH_TOKEN_EXPIRES
        self.token_blacklist = TokenBlacklist()

    def hash_password(self, password):
        if not password:
            raise ValueError("Password cannot be empty.")
        return generate_password_hash(password)

    def verify_password(self, password, hashed):
        if not password or not hashed:
            raise ValueError("Password and hash are required.")
        return check_password_hash(hashed, password)

    def generate_tokens(self, identity, claims=None):
        return {
            "access_token": create_access_token(
                identity=identity,
                additional_claims=claims,
                expires_delta=self.access_expires,
            ),
            "refresh_token": create_refresh_token(
                identity=identity,
                additional_claims=claims,
                expires_delta=self.refresh_expires,
            ),
        }

    def blacklist_token(self):
        jwt = get_jwt()

        jti = jwt.get("jti")
        exp = jwt.get("exp")
        token_type = jwt.get("type", "access")

        if not jti or not exp:
            raise ValueError("Invalid JWT.")

        expires_in = exp - int(time.time())

        self.token_blacklist.add(jti, expires_in)

        current_app.logger.info(
            f"{token_type.capitalize()} token blacklisted."
        )


# =====================================================
# Email Helper
# =====================================================

class EmailHelper:

    def rent_email_body(self, tenant, payment, reminder_type):
        total = payment.rent_amount + payment.maintenance_amount

        subject_map = {
            "BEFORE": "Upcoming Rent Reminder",
            "ON": "Rent Due Today",
            "AFTER": "Overdue Rent Notice",
        }

        body = f"""
Hello {tenant.name},

This is a reminder regarding your rent payment.

Month : {payment.month}
Amount : ₹{total}
Status : {payment.status}

Please make the payment as soon as possible.

Thank you,
RemindMyRent
"""

        return subject_map[reminder_type], body

    def send_rent_email(self, tenant, payment, reminder_type):
        subject, body = self.rent_email_body(
            tenant,
            payment,
            reminder_type,
        )

        msg = Message(
            subject=subject,
            recipients=[tenant.email],
            body=body,
        )

        mail.send(msg)

    def send_welcome_email(self, email, username):
        body = f"""
Hello {username},

Welcome to RemindMyRent!

Thank you for registering with us.

Regards,
RemindMyRent Team
"""

        msg = Message(
            subject="Welcome to RemindMyRent!",
            recipients=[email],
            body=body,
        )

        mail.send(msg)



# =====================================================
# Twilio Helper
# =====================================================

class TwilioHelper:

    def __init__(self):
        self.client = Client(
            Config.TWILIO_ACCOUNT_SID,
            Config.TWILIO_AUTH_TOKEN,
        )

        self.from_number = Config.TWILIO_PHONE_NUMBER
        self.whatsapp_number = Config.TWILIO_WHATSAPP_NUMBER

    def send_sms(self, to, message):
        phone = str(to)

        if not phone.startswith("+"):
            phone = "+91" + phone

        response = self.client.messages.create(
            body=message,
            from_=self.from_number,
            to=phone,
        )

        current_app.logger.info(
            f"SMS sent to {to} (SID={response.sid})"
        )

        return response

    def send_whatsapp(self, to_number, message):

        phone = str(to_number)

        if not phone.startswith("+"):
            phone = "+91" + phone

        msg = self.client.messages.create(
            body=message,
            from_=self.whatsapp_number,
            to=f"whatsapp:{phone}",
        )

        current_app.logger.info(
            f"WhatsApp sent to {to_number}"
        )

        return msg

# =====================================================
# Background Welcome Notification
# =====================================================

def send_welcome_notifications_async(app, email, phone, username):
    with app.app_context():

        # ---------------- Email ----------------
        try:
            EmailHelper().send_welcome_email(email, username)
        except Exception as e:
            app.logger.exception(f"Email failed: {e}")

        # ---------------- SMS ----------------
        try:
            sms = (
                f"Hello {username},\n\n"
                "Welcome to RemindMyRent! 🎉\n"
                "Your account has been created successfully.\n\n"
                "Thank you for registering."
            )

            TwilioHelper().send_sms(phone,sms)
        except Exception as e:
            app.logger.exception(f"SMS failed: {e}")

        # ---------------- WhatsApp ----------------
        try:
            message = f"""
Hello {username},

🎉 Welcome to RemindMyRent!

Thank you for registering with us.
"""

            TwilioHelper().send_whatsapp(phone, message)
        except Exception as e:
            app.logger.exception(f"WhatsApp failed: {e}")


# =====================================================
# Background Tenant Added Notification
# =====================================================

def send_tenant_notifications_async(app, tenant, property_name, rent_amount, maintenance_amount, due_day):
    with app.app_context():
        body = f"""
        Hello {tenant.name},

        You have been added as a tenant(Kirayedar) for {property_name}.

        Rent Amount: ₹{rent_amount}
        Maintenance Amount: ₹{maintenance_amount}
        Due Date: {due_day}

        Thank you.
        """
        # ---------------- Email ----------------
        try:
            msg = Message(
                subject="Welcome to RemindMyRent",
                recipients=[tenant.email],
                body=body,
            )

            mail.send(msg)
            app.logger.info(f"Tenant welcome email sent to {tenant.email}")

        except Exception as e:
            app.logger.exception(f"Tenant email failed: {e}")

        # ---------------- SMS ----------------
        try:
            TwilioHelper().send_sms(tenant.phone, body)
            app.logger.info(f"Tenant SMS sent to {tenant.phone}")

        except Exception as e:
            app.logger.exception(f"Tenant SMS failed: {e}")

        # ---------------- WhatsApp ----------------
        try:
            TwilioHelper().send_whatsapp(tenant.phone, body)
            app.logger.info(f"Tenant WhatsApp sent to {tenant.phone}")

        except Exception as e:
            app.logger.exception(f"Tenant WhatsApp failed: {e}")