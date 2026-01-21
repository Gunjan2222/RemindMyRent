from app import db
from datetime import datetime, date
from sqlalchemy.dialects.postgresql import UUID
import uuid, enum
from sqlalchemy import Enum

class TimeStamp:
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    # created_by = db.Column(db.String(50), default='app')
    # updated_by = db.Column(db.String(50), default='app')


# class User(db.Model, TimeStamp):
#     __tablename__ = 'users'

#     id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
#     username = db.Column(db.String(100), unique=True, nullable=False)
#     email = db.Column(db.String(120), unique=True, nullable=False)
#     contact = db.Column(db.String(15))
#     password = db.Column(db.String(255), nullable=False)
#     role = db.Column(db.String(50), default="landlord")
#     profile_photo = db.Column(db.String(255), nullable=True)

#     properties = db.relationship("Property", backref="owner", lazy=True, cascade="all, delete-orphan")
#     tenants = db.relationship("Tenant", backref="user", lazy=True, cascade="all, delete-orphan")
#     notifications = db.relationship("NotificationLog", backref="landlord", lazy=True, cascade="all, delete-orphan")

class User(db.Model, TimeStamp):
    __tablename__ = "users"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    contact = db.Column(db.String(15))
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default="OWNER")  # OWNER / TENANT

    properties = db.relationship("Property", backref="owner", lazy=True, cascade="all, delete-orphan")



# ---------------------------
# Tenant (No login, just record)
# ---------------------------

class Tenant(db.Model, TimeStamp):
    __tablename__ = "tenants"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    property_id = db.Column(UUID(as_uuid=True), db.ForeignKey("properties.id"), nullable=False)

    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(15), nullable=False)
    email = db.Column(db.String(120))

    rent_amount = db.Column(db.Float, nullable=False)
    maintenance_amount = db.Column(db.Float, default=0.0)
    due_day = db.Column(db.Integer, nullable=False)  # e.g. 5 = 5th of month

    start_date = db.Column(db.Date, default=date.today)
    is_active = db.Column(db.Boolean, default=True)

    payments = db.relationship(
        "Payment",
        backref="tenant",
        cascade="all, delete-orphan",
        lazy=True
    )

# class Tenant(db.Model, TimeStamp):
#     __tablename__ = "tenants"

#     id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4) 
#     name = db.Column(db.String(120), nullable=False)
#     phone_number = db.Column(db.String(15), nullable=False)
#     email = db.Column(db.String(120), nullable=True)
#     address = db.Column(db.String(255), nullable=True)
#     status = db.Column(db.String(20), default="Active")
#     user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("users.id"), nullable=False)
#     leases = db.relationship("Lease", backref="tenant", lazy=True, cascade="all, delete-orphan")
#     payments = db.relationship("RentPayment", backref="tenant", lazy=True, cascade="all, delete-orphan")
#     notifications = db.relationship("NotificationLog", backref="tenant", lazy=True, cascade="all, delete-orphan")


# ---------------------------
# Property
# ---------------------------

class Property(db.Model, TimeStamp):
    __tablename__ = "properties"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id = db.Column(UUID(as_uuid=True), db.ForeignKey("users.id"), nullable=False)

    name = db.Column(db.String(120), nullable=False)
    address = db.Column(db.Text, nullable=False)

    owner = db.relationship("User", backref="properties")

    tenants = db.relationship("Tenant",backref="property",cascade="all, delete-orphan",lazy=True)

# class Property(db.Model, TimeStamp):
#     __tablename__ = "properties"

#     id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
#     owner_id = db.Column(UUID(as_uuid=True), db.ForeignKey("users.id"), nullable=False)
#     title = db.Column(db.String(120), nullable=False)
#     address = db.Column(db.String(255), nullable=False)
#     monthly_rent = db.Column(db.Float, nullable=False)
#     deposit_amount = db.Column(db.Float, default=0.0)

#     leases = db.relationship("Lease", backref="property", lazy=True, cascade="all, delete-orphan")
#     payments = db.relationship("RentPayment", backref="property", lazy=True, cascade="all, delete-orphan")


# ---------------------------
# Lease (Tenant ↔ Property link)
# ---------------------------

# class LeaseStatus(enum.Enum):
#     active = "active"
#     ended = "ended"
    
# class Lease(db.Model, TimeStamp):
#     __tablename__ = "leases"

#     id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
#     tenant_id = db.Column(UUID(as_uuid=True), db.ForeignKey("tenants.id"), nullable=False)
#     property_id = db.Column(UUID(as_uuid=True), db.ForeignKey("properties.id"), nullable=False)
#     lease_start_date = db.Column(db.Date, nullable=False)
#     lease_end_date = db.Column(db.Date, nullable=True)
#     due_day = db.Column(db.Integer, nullable=False)  # e.g., 5 = rent due on 5th of each month
#     status = db.Column(Enum(LeaseStatus), default=LeaseStatus.active)

#     reminders = db.relationship("RentReminder", backref="lease", lazy=True, cascade="all, delete-orphan")

# ---------------------------
# Rent Reminder
# ---------------------------

class ReminderLog(db.Model, TimeStamp):
    __tablename__ = "reminder_logs"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    payment_id = db.Column(UUID(as_uuid=True), db.ForeignKey("payments.id"), nullable=False)

    reminder_type = db.Column(db.String(20))  # BEFORE / ON / AFTER
    sent_via = db.Column(db.String(20))       # EMAIL / SMS / WHATSAPP
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)

    # payment = db.relationship("Payment", backref="reminders")

# class RentReminder(db.Model, TimeStamp):
#     __tablename__ = "rent_reminders"

#     id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
#     lease_id = db.Column(UUID(as_uuid=True), db.ForeignKey("leases.id"), nullable=False)
#     due_date = db.Column(db.Date, nullable=False)
#     reminder_sent = db.Column(db.Boolean, default=False)
#     last_sent_date = db.Column(db.Date, nullable=True)


# ---------------------------
# Rent Payment
# ---------------------------

class Payment(db.Model, TimeStamp):
    __tablename__ = "payments"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = db.Column(UUID(as_uuid=True), db.ForeignKey("tenants.id"), nullable=False)

    month = db.Column(db.String(7), nullable=False)  # 2026-01
    rent_amount = db.Column(db.Float, nullable=False)
    maintenance_amount = db.Column(db.Float, default=0.0)

    status = db.Column(db.String(20), default="PENDING")  
    paid_on = db.Column(db.Date)
    payment_mode = db.Column(db.String(50))  # Cash / UPI / Bank

    reminders = db.relationship(
        "ReminderLog",
        backref="payment",
        cascade="all, delete-orphan",
        lazy=True
    )

# class RentPayment(db.Model, TimeStamp):
#     __tablename__ = "rent_payments"

#     id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
#     tenant_id = db.Column(UUID(as_uuid=True), db.ForeignKey("tenants.id"), nullable=False)
#     property_id = db.Column(UUID(as_uuid=True), db.ForeignKey("properties.id"), nullable=False)
#     amount = db.Column(db.Float, nullable=False)
#     payment_date = db.Column(db.Date, default=date.today)
#     payment_mode = db.Column(db.String(50), default="Cash")  # Cash, UPI, Bank Transfer
#     status = db.Column(db.String(50), default="pending")  # paid, pending, late
#     transaction_reference = db.Column(db.String(255), nullable=True)


# ---------------------------
# Notification Log (Optional)
# ---------------------------
# class NotificationLog(db.Model, TimeStamp):
#     __tablename__ = "notification_logs"

#     id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
#     tenant_id = db.Column(UUID(as_uuid=True), db.ForeignKey("tenants.id"), nullable=True)
#     owner_id = db.Column(UUID(as_uuid=True), db.ForeignKey("users.id"), nullable=True)
#     message = db.Column(db.Text, nullable=False)
#     notification_type = db.Column(db.String(50), default="Email")
#     status = db.Column(db.String(50), default="PENDING")  # SENT / FAILED

# ---------------------------
# Tasks Log (Optional)
# ---------------------------

# class DailyTaskLog(db.Model):
#     __tablename__ = "daily_task_log"

#     id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
#     task_name = db.Column(db.String(100), nullable=False)
#     run_date = db.Column(db.Date, nullable=False, default=date.today)

class PasswordResetToken(db.Model, TimeStamp):
    __tablename__ = 'password_reset_tokens'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=False)
    token = db.Column(db.String(100), unique=True, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)

    def is_expired(self):
        return datetime.utcnow() > self.expires_at
