import time
from datetime import timedelta, datetime
from flask import current_app
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_jwt
)
from werkzeug.security import generate_password_hash, check_password_hash
from app.utils.token_blacklist import TokenBlacklist
from app.config import Config
from flask_mail import Message
from app import mail


class AuthHelper:
    def __init__(self):
        self.secret_key = Config.JWT_SECRET_KEY
        self.access_expires = timedelta(minutes=Config.JWT_ACCESS_TOKEN_EXPIRES)
        self.refresh_expires = timedelta(days=Config.JWT_REFRESH_TOKEN_EXPIRES)
        self.token_blacklist = TokenBlacklist()

    def hash_password(self, password):
        try:
            if not password:
                raise ValueError("Password cannot be empty.")
            return generate_password_hash(password)
        except Exception as e:
            current_app.logger.error(f"Error hashing password: {e}")
            raise

    def verify_password(self, password, hashed):
        try:
            if not password or not hashed:
                raise ValueError("Password and hash are required.")
            return check_password_hash(hashed, password)
        except Exception as e:
            current_app.logger.error(f"Error verifying password: {e}")
            raise

    def generate_tokens(self, identity, claims=None):
        try:
            if not identity:
                raise ValueError("Identity is required to generate tokens.")
            return {
                "access_token": create_access_token(
                    identity=identity, 
                    additional_claims=claims, 
                    expires_delta=self.access_expires
                    ),
                "refresh_token": create_refresh_token(
                    identity=identity,
                    additional_claims=claims, 
                    expires_delta=self.refresh_expires
                    ),
            }
        except Exception as e:
            current_app.logger.error(f"Error generating tokens: {e}")
            raise


    def blacklist_token(self):
        """Blacklist the current JWT (access or refresh)."""
        try:
            jwt = get_jwt()
            jti = jwt.get("jti")
            exp = jwt.get("exp")
            token_type = jwt.get("type", "access")  # default to access if missing

            if not jti or not exp:
                raise ValueError("Invalid JWT structure.")

            expires_in = exp - int(time.time())
            self.token_blacklist.add(jti, expires_in)

            current_app.logger.info(
                f"{token_type.capitalize()} token blacklisted (jti={jti}). "
                f"Expires in {expires_in}s."
            )
        except Exception as e:
            current_app.logger.error(f"Error blacklisting token: {e}", exc_info=True)
            raise

class EmailHelper:
    def rent_email_body(self, tenant, payment, reminder_type):
        total = payment.rent_amount + payment.maintenance_amount

        subject_map = {
            "BEFORE": "Upcoming Rent Reminder",
            "ON": "Rent Due Today",
            "AFTER": "Overdue Rent Notice"
        }

        return subject_map[reminder_type], f"""
    Hello {tenant.name},

    This is a reminder regarding your rent payment.

    📅 Month: {payment.month}
    💰 Amount: ₹{total}
    📌 Status: {payment.status}

    Please make the payment at the earliest.

    Thank you,
    RemindMyRent
    """

    def send_rent_email(self, tenant, payment, reminder_type):
        subject, body = self.rent_email_body(tenant, payment, reminder_type)

        msg = Message(
            subject=subject,
            recipients=[tenant.email],
            body=body
        )

        mail.send(msg)




# class TwilioHelper:
#     def __init__(self):
#         try:
#             self.client = Client(Config.TWILIO_ACCOUNT_SID, Config.TWILIO_AUTH_TOKEN)
#             self.from_number = Config.TWILIO_PHONE_NUMBER
#             self.whatsapp_number = Config.TWILIO_WHATSAPP_NUMBER
#             if not self.from_number:
#                 raise ValueError("Twilio 'from' phone number is not configured.")
#         except Exception as e:
#             current_app.logger.error(f"Error initializing Twilio client: {e}")
#             raise

#     def send_sms(self, to, message, tenant_id=None, landlord_id=None):
#         try:
#             if not to or not message:
#                 raise ValueError("Recipient number and message cannot be empty.")
#             response = self.client.messages.create(body=message, from_=self.from_number, to=to)
#             current_app.logger.info(f"SMS sent to {to}, SID: {response.sid}")

#         except Exception as e:
#             current_app.logger.error(f"Error sending SMS to {to}: {e}", exc_info=True)
#             raise

#     def send_welcome_message(self, to, name, tenant_id=None):
#         try:
#             if not name:
#                 raise ValueError("Name is required for welcome message.")
#             message = f"Welcome {name}! 🎉 You have successfully registered to RemindMyRent."
#             return self.send_sms(to, message, tenant_id=tenant_id)
#         except Exception as e:
#             current_app.logger.error(f"Error sending welcome message to {to}: {e}", exc_info=True)
#             raise

#     def send_whatsapp(self, to_number, message, tenant_id=None):

#         response = self.client.messages.create(body=message, from_= self.whatsapp_number, to='whatsapp:'+ to_number)
#         # msg = client.messages.create(
#         #     body=message,
#         #     from_='whatsapp:' + current_app.config['TWILIO_WHATSAPP_NUMBER'],
#         #     to='whatsapp:' + to_number
#         # )

#         # Log notification
#         # log_notification(tenant_id=tenant_id, message=message, notification_type="WhatsApp", status="sent")
#         return response.sid


# def log_notification(tenant_id, message, notification_type="SMS", status="pending", landlord_id=None):
#         """Save notification logs automatically."""
#         try:
#             log = NotificationLog(
#                 tenant_id=tenant_id,
#                 message=message,
#                 notification_type=notification_type,
#                 status=status,
#                 landlord_id = landlord_id
#             )
#             db.session.add(log)
#             db.session.commit()
#         except Exception as e:
#             db.session.rollback()
#             current_app.logger.error(f"Failed to log notification: {e}", exc_info=True)

# def send_whatsapp_free(tenant_number, message):
#     now = datetime.now()
#     hour = now.hour
#     minute = now.minute + 2  # schedule 2 minutes later to give browser time to open
#     try:
#         pywhatkit.sendwhatmsg(tenant_number, message, hour, minute)
#     except Exception as e:
#         print(f"Error sending WhatsApp message to {tenant_number}: {e}")