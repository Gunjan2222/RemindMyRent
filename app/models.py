from app import db
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

class TimeStamp(object):
    created_date = db.Column(db.Date, default=datetime.now)
    created_time = db.Column(db.Time, default=datetime.now)
    updated_date = db.Column(db.Date, default=datetime.now, onupdate=datetime.now)
    updated_time = db.Column(db.Time, default=datetime.now, onupdate=datetime.now)
    created_by = db.Column(db.String, default='app')
    updated_by = db.Column(db.String, default='app')

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

    # Relationship to rent reminders
    reminders = db.relationship('RentReminder', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class RentReminder(db.Model, TimeStamp):
    id = db.Column(db.Integer, primary_key=True)
    tenant_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    phone_number = db.Column(db.String(20), nullable=True)
    rent_date = db.Column(db.Date, nullable=False)  # rent start date
    last_notified = db.Column(db.Date, nullable=True)
    rent_amount = db.Column(db.Float, nullable=False)
    due_day = db.Column(db.Integer, nullable=False, default=1)
    frequency = db.Column(db.String(20), default='monthly')

    # Link to user
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # Relationship to payment history
    payments = db.relationship('RentPayment', backref='tenant', lazy=True)

class RentPayment(db.Model, TimeStamp):
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('rent_reminder.id'), nullable=False)
    payment_date = db.Column(db.Date, nullable=False)
    amount_paid = db.Column(db.Float, nullable=False)
    for_month = db.Column(db.Date, nullable=False)  # e.g., 2025-05-01 for May 2025
    is_late = db.Column(db.Boolean, default=False)
