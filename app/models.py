from app import db
from datetime import datetime

class TimeStamp:
    created_date = db.Column(db.DateTime, default=datetime.utcnow)
    updated_date = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.String(50), default='app')
    updated_by = db.Column(db.String(50), default='app')


class User(db.Model, TimeStamp):
    __tablename__ = 'users'   # avoid reserved keyword 'user'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    contact = db.Column(db.String(15))
    password = db.Column(db.String(200), nullable=False)

    reminders = db.relationship('RentReminder', backref='user', lazy=True)


class RentReminder(db.Model, TimeStamp):
    __tablename__ = 'rent_reminders'

    id = db.Column(db.Integer, primary_key=True)
    tenant_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    phone_number = db.Column(db.String(20))
    rent_date = db.Column(db.Date, nullable=False)
    last_notified = db.Column(db.Date)
    rent_amount = db.Column(db.Float, nullable=False)
    due_day = db.Column(db.Integer, nullable=False, default=1)
    frequency = db.Column(db.String(20), default='monthly')

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    payments = db.relationship('RentPayment', backref='tenant', lazy=True)


class RentPayment(db.Model, TimeStamp):
    __tablename__ = 'rent_payments'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('rent_reminders.id'), nullable=False)
    payment_date = db.Column(db.Date, nullable=False)
    amount_paid = db.Column(db.Float, nullable=False)
    for_month = db.Column(db.Date, nullable=False)
    is_late = db.Column(db.Boolean, default=False)


class PasswordResetToken(db.Model):
    __tablename__ = 'password_reset_tokens'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    token = db.Column(db.String(100), unique=True, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)

    def is_expired(self):
        return datetime.utcnow() > self.expires_at
