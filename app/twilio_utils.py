from twilio.rest import Client
from flask import current_app

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
