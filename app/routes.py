from flask import Blueprint, request, jsonify
from datetime import datetime
from app.models import db, RentReminder, RentPayment
from app.tasks import send_rent_reminder, send_rent_notifications_task
from app.twilio_utils import send_sms

api = Blueprint('api', __name__)

@api.route('/')
def index():
    return "Server is running!"

@api.route('/test_sms', methods=['POST'])
def test_sms():
    data = request.json
    to = data.get('to')
    message = data.get('message', 'This is a test SMS from RemindMyRent.')

    if not to:
        return jsonify({'error': 'Phone number is required'}), 400

    sms_sid = send_sms(to, message)
    if sms_sid:
        return jsonify({'message': 'SMS sent successfully', 'sid': sms_sid}), 200
    else:
        return jsonify({'error': 'SMS failed to send'}), 500

@api.route('/add_reminder', methods=['POST'])
def add_reminder():
    data = request.json
    reminder = RentReminder(
        tenant_name=data['tenant_name'],
        email=data['email'],
        rent_date=datetime.strptime(data['rent_date'], '%Y-%m-%d').date(),
        rent_amount=data['rent_amount'],
        due_day=data.get('due_day', 1),
        frequency=data.get('frequency', 'monthly')
    )
    db.session.add(reminder)
    db.session.commit()
    return jsonify({'message': 'Reminder added'}), 201

@api.route('/record_payment', methods=['POST'])
def record_payment():
    data = request.json
    tenant_id = data['tenant_id']
    payment_date = datetime.strptime(data['payment_date'], '%Y-%m-%d').date()
    for_month = datetime.strptime(data['for_month'], '%Y-%m-%d').date()
    amount_paid = data['amount_paid']

    reminder = RentReminder.query.get(tenant_id)
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
