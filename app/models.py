from app import db
from datetime import datetime

class TimeStamp(object):
    created_date = db.Column(db.Date, default=datetime.now)
    created_time = db.Column(db.TIME, default=datetime.now)
    updated_date = db.Column(db.Date, default=datetime.now, onupdate=datetime.now)
    updated_time = db.Column(db.TIME, default=datetime.now, onupdate=datetime.now)
    created_by = db.Column(db.String, default='app')
    updated_by = db.Column(db.String, default='app')

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
    
    # Relationship to payment history
    payments = db.relationship('RentPayment', backref='tenant', lazy=True)

class RentPayment(db.Model, TimeStamp):
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('rent_reminder.id'), nullable=False)
    payment_date = db.Column(db.Date, nullable=False)
    amount_paid = db.Column(db.Float, nullable=False)
    for_month = db.Column(db.Date, nullable=False)  # e.g., 2025-05-01 for May 2025
    is_late = db.Column(db.Boolean, default=False)