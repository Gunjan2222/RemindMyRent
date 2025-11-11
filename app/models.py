from app import db
from datetime import datetime, date
from sqlalchemy.dialects.postgresql import UUID
import uuid, enum
from sqlalchemy import Enum

class TimeStamp:
    created_date = db.Column(db.DateTime, default=datetime.now)
    updated_date = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    created_by = db.Column(db.String(50), default='app')
    updated_by = db.Column(db.String(50), default='app')


class User(db.Model, TimeStamp):
    __tablename__ = 'users'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    contact = db.Column(db.String(15))
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), default="landlord")
    profile_photo = db.Column(db.String(255), nullable=True)

    properties = db.relationship("Property", backref="owner", lazy=True, cascade="all, delete-orphan")
    tenants = db.relationship("Tenant", backref="user", lazy=True, cascade="all, delete-orphan")
    notifications = db.relationship("NotificationLog", backref="landlord", lazy=True, cascade="all, delete-orphan")


# ---------------------------
# Tenant (No login, just record)
# ---------------------------
class Tenant(db.Model, TimeStamp):
    __tablename__ = "tenants"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4) 
    name = db.Column(db.String(120), nullable=False)
    phone_number = db.Column(db.String(15), nullable=False)
    email = db.Column(db.String(120), nullable=True)
    address = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(20), default="Active")
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("users.id"), nullable=False)
    leases = db.relationship("Lease", backref="tenant", lazy=True, cascade="all, delete-orphan")
    payments = db.relationship("RentPayment", backref="tenant", lazy=True, cascade="all, delete-orphan")
    notifications = db.relationship("NotificationLog", backref="tenant", lazy=True, cascade="all, delete-orphan")


# ---------------------------
# Property
# ---------------------------
class Property(db.Model, TimeStamp):
    __tablename__ = "properties"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id = db.Column(UUID(as_uuid=True), db.ForeignKey("users.id"), nullable=False)
    title = db.Column(db.String(120), nullable=False)
    address = db.Column(db.String(255), nullable=False)
    monthly_rent = db.Column(db.Float, nullable=False)
    deposit_amount = db.Column(db.Float, default=0.0)

    leases = db.relationship("Lease", backref="property", lazy=True, cascade="all, delete-orphan")
    payments = db.relationship("RentPayment", backref="property", lazy=True, cascade="all, delete-orphan")


# ---------------------------
# Lease (Tenant ↔ Property link)
# ---------------------------

class LeaseStatus(enum.Enum):
    active = "active"
    ended = "ended"
    
class Lease(db.Model, TimeStamp):
    __tablename__ = "leases"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = db.Column(UUID(as_uuid=True), db.ForeignKey("tenants.id"), nullable=False)
    property_id = db.Column(UUID(as_uuid=True), db.ForeignKey("properties.id"), nullable=False)
    lease_start_date = db.Column(db.Date, nullable=False)
    lease_end_date = db.Column(db.Date, nullable=True)
    due_day = db.Column(db.Integer, nullable=False)  # e.g., 5 = rent due on 5th of each month
    status = db.Column(Enum(LeaseStatus), default=LeaseStatus.active)

    reminders = db.relationship("RentReminder", backref="lease", lazy=True, cascade="all, delete-orphan")

# ---------------------------
# Rent Reminder
# ---------------------------
class RentReminder(db.Model, TimeStamp):
    __tablename__ = "rent_reminders"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lease_id = db.Column(UUID(as_uuid=True), db.ForeignKey("leases.id"), nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    reminder_sent = db.Column(db.Boolean, default=False)
    last_sent_date = db.Column(db.Date, nullable=True)


# ---------------------------
# Rent Payment
# ---------------------------
class RentPayment(db.Model, TimeStamp):
    __tablename__ = "rent_payments"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = db.Column(UUID(as_uuid=True), db.ForeignKey("tenants.id"), nullable=False)
    property_id = db.Column(UUID(as_uuid=True), db.ForeignKey("properties.id"), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    payment_date = db.Column(db.Date, default=date.today)
    payment_mode = db.Column(db.String(50), default="Cash")  # Cash, UPI, Bank Transfer
    status = db.Column(db.String(50), default="pending")  # paid, pending, late
    transaction_reference = db.Column(db.String(255), nullable=True)


# ---------------------------
# Notification Log (Optional)
# ---------------------------
class NotificationLog(db.Model, TimeStamp):
    __tablename__ = "notification_logs"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = db.Column(UUID(as_uuid=True), db.ForeignKey("tenants.id"), nullable=True)
    landlord_id = db.Column(UUID(as_uuid=True), db.ForeignKey("users.id"), nullable=True)
    message = db.Column(db.Text, nullable=False)
    notification_type = db.Column(db.String(50), default="WhatsApp")
    status = db.Column(db.String(50), default="pending")  # sent, failed, pending

# ---------------------------
# Tasks Log (Optional)
# ---------------------------

class DailyTaskLog(db.Model):
    __tablename__ = "daily_task_log"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_name = db.Column(db.String(100), nullable=False)
    run_date = db.Column(db.Date, nullable=False, default=date.today)

class PasswordResetToken(db.Model, TimeStamp):
    __tablename__ = 'password_reset_tokens'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=False)
    token = db.Column(db.String(100), unique=True, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)

    def is_expired(self):
        return datetime.utcnow() > self.expires_at
