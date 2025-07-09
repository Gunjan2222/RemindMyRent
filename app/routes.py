from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from datetime import datetime
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

from app.models import db, RentReminder, RentPayment, User
from app.tasks import send_rent_reminder, send_rent_notifications_task
from app.twilio_utils import send_sms

api = Blueprint('api', __name__)

# ---------------------
# 🟢 Auth routes
# ---------------------
@api.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return redirect(url_for('api.register'))

        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash('Registration successful. Please login.', 'success')
        return redirect(url_for('api.login'))
    return render_template('register.html')

@api.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('api.dashboard'))
        else:
            flash('Invalid email or password.', 'danger')
            return redirect(url_for('api.login'))
    return render_template('login.html')

@api.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('api.login'))

# ---------------------
# 🔐 Protected routes
# ---------------------
@api.route('/')
@login_required
def dashboard():
    reminders = RentReminder.query.filter_by(user_id=current_user.id).all()
    return render_template('dashboard.html', reminders=reminders)

@api.route('/add-reminder', methods=['GET'])
@login_required
def add_reminder_page():
    return render_template('add_reminder.html')

@api.route('/record-payment', methods=['GET'])
@login_required
def record_payment_page():
    reminders = RentReminder.query.filter_by(user_id=current_user.id).all()
    return render_template('record_payment.html', reminders=reminders)

@api.route('/add_reminder', methods=['POST'])
@login_required
def add_reminder():
    data = request.json

    reminder = RentReminder(
        tenant_name=data['tenant_name'],
        email=data['email'],
        rent_date=datetime.strptime(data['rent_date'], '%Y-%m-%d').date(),
        rent_amount=data['rent_amount'],
        due_day=data.get('due_day', 1),
        frequency=data.get('frequency', 'monthly'),
        user_id=current_user.id
    )
    db.session.add(reminder)
    db.session.commit()

    return jsonify({'message': 'Reminder added'}), 201

@api.route('/record_payment', methods=['POST'])
@login_required
def record_payment():
    data = request.json
    tenant_id = data['tenant_id']
    payment_date = datetime.strptime(data['payment_date'], '%Y-%m-%d').date()
    for_month = datetime.strptime(data['for_month'], '%Y-%m-%d').date()
    amount_paid = data['amount_paid']

    reminder = RentReminder.query.filter_by(id=tenant_id, user_id=current_user.id).first()
    if not reminder:
        return jsonify({'error': 'Tenant not found'}), 404

    due_date = for_month.replace(day=reminder.due_day)
    is_late = payment_date > due_date

    payment = RentPayment(
        tenant_id=tenant_id,
        payment_date=payment_date,
        for_month=for_month,
        amount_paid=amount_paid,
        is_late=is_late
    )
    db.session.add(payment)
    db.session.commit()
    return jsonify({'message': 'Payment recorded'}), 201
