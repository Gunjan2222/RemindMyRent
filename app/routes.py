from flask import Blueprint, request, jsonify, render_template
from datetime import datetime
from app.models import db, RentReminder, RentPayment, User
from app.tasks import send_rent_reminder, send_rent_notifications_task
from app.utils.helper import AuthHelper
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity


api = Blueprint('api', __name__)

# ---------------------
# 🟢 Auth routes (API)
# ---------------------

@api.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    if User.query.filter_by(username=username).first():
        return jsonify({"msg": "User already exists"}), 400

    new_user = User(username=username, password= AuthHelper.hash_password(password))
    db.session.add(new_user)
    db.session.commit()

    return jsonify({"msg": "User registered successfully"}), 201


@api.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    user = User.query.filter_by(username=username).first()
    if not user or not AuthHelper.verify_password(password, user.password):
        return jsonify({"msg": "Invalid credentials"}), 401

    tokens = AuthHelper.generate_tokens(identity=user.id)
    return jsonify(tokens), 200

@api.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh_token():
    identity = get_jwt_identity()
    new_access_token = create_access_token(identity=identity)
    return jsonify(access_token=new_access_token), 200

@api.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    AuthHelper.blacklist_token()
    return jsonify({"msg": "Access token revoked"}), 200

@api.route('/logout-refresh', methods=['POST'])
@jwt_required(refresh=True)
def logout_refresh():
    AuthHelper.blacklist_token()
    return jsonify({"msg": "Refresh token revoked"}), 200

# ---------------------
# 🔐 Protected routes (JWT Required)
# ---------------------

# @api.route('/')
# @jwt_required()
# def dashboard():
#     user_id = get_jwt_identity()
#     reminders = RentReminder.query.filter_by(user_id=user_id).all()
#     return render_template('dashboard.html', reminders=reminders)

# @api.route('/add-reminder', methods=['GET'])
# @jwt_required()
# def add_reminder_page():
#     return render_template('add_reminder.html')

# @api.route('/record-payment', methods=['GET'])
# @jwt_required()
# def record_payment_page():
#     user_id = get_jwt_identity()
#     reminders = RentReminder.query.filter_by(user_id=user_id).all()
#     return render_template('record_payment.html', reminders=reminders)

@api.route('/add_reminder', methods=['POST'])
@jwt_required()
def add_reminder():
    data = request.get_json()
    user_id = get_jwt_identity()

    reminder = RentReminder(
        tenant_name=data['tenant_name'],
        email=data['email'],
        phone_number=data.get('phone_number'),
        rent_date=datetime.strptime(data['rent_date'], '%Y-%m-%d').date(),
        rent_amount=data['rent_amount'],
        due_day=data.get('due_day', 1),
        frequency=data.get('frequency', 'monthly'),
        user_id=user_id
    )
    db.session.add(reminder)
    db.session.commit()

    return jsonify({'message': 'Reminder added'}), 201

@api.route('/record_payment', methods=['POST'])
@jwt_required()
def record_payment():
    data = request.get_json()
    user_id = get_jwt_identity()

    tenant_id = data['tenant_id']
    payment_date = datetime.strptime(data['payment_date'], '%Y-%m-%d').date()
    for_month = datetime.strptime(data['for_month'], '%Y-%m-%d').date()
    amount_paid = data['amount_paid']

    # Ensure this tenant belongs to the current user
    reminder = RentReminder.query.filter_by(id=tenant_id, user_id=user_id).first()
    if not reminder:
        return jsonify({'error': 'Tenant not found or unauthorized'}), 403

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
