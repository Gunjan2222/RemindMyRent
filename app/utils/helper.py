from twilio.rest import Client
from flask import current_app

from flask_jwt_extended import create_access_token, create_refresh_token, get_jwt, decode_token

from werkzeug.security import generate_password_hash, check_password_hash
from datetime import timedelta
from app.utils.token_blacklist import TokenBlacklist
from app.config import Config

class TwilioHelper:

    @staticmethod
    def send_sms(to, body):
        try:
            account_sid = current_app.config['TWILIO_ACCOUNT_SID']
            auth_token = current_app.config['TWILIO_AUTH_TOKEN']
            from_number = current_app.config['TWILIO_PHONE_NUMBER']

            client = Client(account_sid, auth_token)
            message = client.messages.create(
                body=body,
                from_=from_number,
                to=to
            )
            return message.sid
        except Exception as e:
            print(f"Twilio Error: {e}")
            return None

class AuthHelper:

    @staticmethod
    def hash_password(password):
        """Hashes the password using Werkzeug."""
        return generate_password_hash(password)

    @staticmethod
    def verify_password(password, hashed):
        """Verifies a password against a hashed version."""
        return check_password_hash(hashed, password)

    @staticmethod
    def generate_tokens(identity):
        """Generates access and refresh tokens."""
        access_token = create_access_token(identity=identity, expires_delta=timedelta(seconds=Config.JWT_ACCESS_TOKEN_EXPIRES))
        refresh_token = create_refresh_token(identity=identity, expires_delta=timedelta(seconds=Config.JWT_REFRESH_TOKEN_EXPIRES))
        return {
            "access_token": access_token,
            "refresh_token": refresh_token
        }

    @staticmethod
    def blacklist_token():
        """Add current token to Redis blacklist."""
        jti = get_jwt()["jti"]
        expires = get_jwt()["exp"] - get_jwt()["iat"]  # expiry in seconds
        TokenBlacklist().add(jti, expires)
        return jti

    @staticmethod
    def is_token_blacklisted(token):
        """Check if a token is blacklisted."""
        try:
            decoded_token = decode_token(token)
            jti = decoded_token["jti"]
            return TokenBlacklist().is_blacklisted(jti)
        except Exception:
            return True
            
