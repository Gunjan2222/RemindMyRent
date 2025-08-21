import time
from datetime import timedelta
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
from twilio.rest import Client


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

    def generate_tokens(self, identity):
        try:
            if not identity:
                raise ValueError("Identity is required to generate tokens.")
            return {
                "access_token": create_access_token(identity=identity, expires_delta=self.access_expires),
                "refresh_token": create_refresh_token(identity=identity, expires_delta=self.refresh_expires),
            }
        except Exception as e:
            current_app.logger.error(f"Error generating tokens: {e}")
            raise

    def decode_token(self, token):
        try:
            if not token:
                raise ValueError("Token is required.")
            return decode_token(token)
        except Exception as e:
            current_app.logger.error(f"Error decoding token: {e}")
            raise

    def blacklist_token(self):
        """Blacklist the current JWT."""
        try:
            jwt = get_jwt()
            jti = jwt.get("jti")
            exp = jwt.get("exp")

            if not jti or not exp:
                raise ValueError("Invalid JWT structure.")

            expires_in = exp - int(time.time())
            self.token_blacklist.add(jti, expires_in)
            current_app.logger.info(f"Token blacklisted (jti={jti}). Expires in {expires_in}s.")
        except Exception as e:
            current_app.logger.error(f"Error blacklisting token: {e}")
            raise

    def is_token_revoked(self):
        try:
            jti = get_jwt().get("jti")
            if not jti:
                raise ValueError("JWT missing 'jti' claim.")
            revoked = self.token_blacklist.is_blacklisted(jti)
            current_app.logger.info(f"Token revoked check (jti={jti}): {revoked}")
            return revoked
        except Exception as e:
            current_app.logger.error(f"Error checking token revocation: {e}")
            raise


class TwilioHelper:
    def __init__(self):
        try:
            self.client = Client(Config.TWILIO_ACCOUNT_SID, Config.TWILIO_AUTH_TOKEN)
            self.from_number = Config.TWILIO_PHONE_NUMBER
            if not self.from_number:
                raise ValueError("Twilio 'from' phone number is not configured.")
        except Exception as e:
            current_app.logger.error(f"Error initializing Twilio client: {e}")
            raise

    def send_sms(self, to, message):
        try:
            if not to or not message:
                raise ValueError("Recipient number and message cannot be empty.")
            response = self.client.messages.create(body=message, from_=self.from_number, to=to)
            current_app.logger.info(f"SMS sent to {to}, SID: {response.sid}")
            return response.sid
        except Exception as e:
            current_app.logger.error(f"Error sending SMS to {to}: {e}")
            raise

    def send_welcome_message(self, to, name):
        try:
            if not name:
                raise ValueError("Name is required for welcome message.")
            message = f"Welcome {name}! 🎉 You have successfully registered to RemindMyRent."
            return self.send_sms(to, message)
        except Exception as e:
            current_app.logger.error(f"Error sending welcome message to {to}: {e}")
            raise
