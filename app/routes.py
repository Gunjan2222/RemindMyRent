from flask import Blueprint, request, jsonify, url_for, current_app
from datetime import datetime, timedelta
import secrets, re
from flask_jwt_extended import jwt_required, get_jwt_identity, create_access_token
from flask_mail import Message
from werkzeug.security import generate_password_hash
from app import db, mail
from app.models import User, RentReminder, RentPayment, PasswordResetToken
from app.utils.helper import AuthHelper, TwilioHelper
from app.config import Config
from app.tasks import send_rent_notifications_task

api = Blueprint("api", __name__)

# ---------------------
# Authentication Routes
# ---------------------

@api.route("/")
def server_testing():
    return "server is running"

@api.route("/register", methods=["POST"])
def register():
    try:
        twilio_helper = TwilioHelper()
        auth_helper = AuthHelper()
        data = request.get_json(silent=True) or request.form

        username = data.get("username", "").strip()
        email = data.get("email", "").strip()
        contact = data.get("contact", "").strip()
        password = data.get("password", "")

        # --- Validation ---
        if not username or not email or not contact or not password:
            current_app.logger.warning("Registration failed: missing required fields")
            return jsonify({"error": "All fields (username, email, contact, password) are required"}), 400

        if len(username) < 3 or len(username) > 50:
            return jsonify({"error": "Username must be between 3 and 50 characters"}), 400

        email_regex = r"^[\w\.-]+@[\w\.-]+\.\w+$"
        if not re.match(email_regex, email):
            return jsonify({"error": "Invalid email format"}), 400

        contact_regex = r"^\+?[1-9]\d{7,14}$"  # E.164 format
        if not re.match(contact_regex, contact):
            return jsonify({"error": "Invalid phone number format (use E.164 format)"}), 400

        if len(password) < 8:
            return jsonify({"error": "Password must be at least 8 characters long"}), 400
        if not any(c.isupper() for c in password) or not any(c.isdigit() for c in password):
            return jsonify({"error": "Password must contain at least one uppercase letter and one digit"}), 400

        if User.query.filter_by(username=username).first():
            return jsonify({"error": "Username already exists"}), 400
        if User.query.filter_by(email=email).first():
            return jsonify({"error": "Email already exists"}), 400
        if User.query.filter_by(contact=contact).first():
            return jsonify({"error": "Contact number already exists"}), 400

        # --- Create new user ---
        new_user = User(
            username=username,
            email=email,
            contact=contact,
            password=auth_helper.hash_password(password),
        )

        db.session.add(new_user)
        db.session.commit()
        current_app.logger.info(f"New user registered: {username} ({email})")

        try:
            subject = "Welcome to RemindMyRent!"
            body = f"Hello {username},\n\nWelcome to RemindMyRent! We're excited to have you on board.\n\nThanks!"
            msg = Message(subject, recipients=[email], body=body)
            mail.send(msg)
            current_app.logger.info(f"Welcome email sent to {email}")
        except Exception as e:
            current_app.logger.error(f"Failed to send welcome email to {email}: {e}", exc_info=True)

        return jsonify({"message": "User registered successfully"}), 201

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error during registration: {e}")
        return jsonify({"error": "Registration failed", "details": str(e)}), 500



@api.route("/login", methods=["POST"])
def login():
    try:
        # Ensure request contains valid JSON or form data
        if not request.is_json and not request.form:
            return jsonify({"message": "Request must be JSON or form data"}), 400

        data = request.get_json(silent=True) or request.form
        username = (data.get("username") or "").strip()
        password = (data.get("password") or "").strip()

        # --- Field validations ---
        if not username or not password:
            return jsonify({"message": "Username and password are required"}), 400
        
        if len(username) < 3 or len(username) > 50:
            return jsonify({"message": "Username must be between 3 and 50 characters"}), 400
        
        if not re.match(r"^[a-zA-Z0-9_.-]+$", username):
            return jsonify({"message": "Username can only contain letters, numbers, dots, hyphens, and underscores"}), 400
        
        if len(password) < 6 or len(password) > 100:
            return jsonify({"message": "Password must be between 6 and 100 characters"}), 400

        # --- Authentication ---
        auth_helper = AuthHelper()
        user = User.query.filter_by(username=username).first()
        if not user or not auth_helper.verify_password(password, user.password):
            return jsonify({"message": "Invalid username or password"}), 401

        # --- Token generation ---
        tokens = auth_helper.generate_tokens(identity=str(user.id))
        return jsonify(tokens), 200

    except Exception as e:
        current_app.logger.error(f"Login error: {e}")
        return jsonify({"message": "Login failed", "details": str(e)}), 500


@api.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh_token():
    try:
        identity = get_jwt_identity()
        return jsonify(access_token=create_access_token(identity=identity)), 200
    except Exception as e:
        current_app.logger.error(f"Token refresh error: {e}")
        return jsonify({"message": "Token refresh failed", "details": str(e)}), 500


@api.route("/logout", methods=["POST"])
@jwt_required()
def logout():
    try:
        auth_helper = AuthHelper()
        auth_helper.blacklist_token()
        return jsonify({"message": "Access token revoked"}), 200
    except Exception as e:
        current_app.logger.error(f"Logout error: {e}")
        return jsonify({"message": "Logout failed", "details": str(e)}), 500


@api.route("/logout-refresh", methods=["POST"])
@jwt_required(refresh=True)
def logout_refresh():
    try:
        auth_helper = AuthHelper()
        auth_helper.blacklist_token()
        return jsonify({"message": "Refresh token revoked"}), 200
    except Exception as e:
        current_app.logger.error(f"Refresh token logout error: {e}")
        return jsonify({"message": "Logout failed", "details": str(e)}), 500


# ---------------------
# Reminder & Payment Routes
# ---------------------

@api.route("/add_reminder", methods=["POST"])
@jwt_required()
def add_reminder():
    try:
        data = request.get_json(silent=True) or request.form
        user_id = get_jwt_identity()

        # --- Required field checks ---
        required_fields = ["tenant_name", "email", "rent_date", "rent_amount"]
        missing = [f for f in required_fields if not data.get(f)]
        if missing:
            return jsonify({"message": f"Missing required fields: {', '.join(missing)}"}), 400

        # --- Validate email format ---
        from re import match
        if not match(r"^[\w\.-]+@[\w\.-]+\.\w+$", data["email"]):
            return jsonify({"message": "Invalid email format"}), 400

        # --- Validate rent date format ---
        try:
            rent_date = datetime.strptime(data["rent_date"], "%Y-%m-%d").date()
        except ValueError:
            return jsonify({"message": "Invalid date format. Use YYYY-MM-DD."}), 400

        # --- Validate rent amount ---
        try:
            rent_amount = float(data["rent_amount"])
            if rent_amount <= 0:
                return jsonify({"message": "Rent amount must be positive"}), 400
        except ValueError:
            return jsonify({"message": "Rent amount must be a number"}), 400

        # --- Validate optional phone number ---
        phone_number = data.get("phone_number")
        if phone_number and not match(r"^\+?\d{7,15}$", phone_number):
            return jsonify({"message": "Invalid phone number format"}), 400

        # --- Validate due_day if provided ---
        due_day = data.get("due_day", 1)
        try:
            due_day = int(due_day)
            if not (1 <= due_day <= 31):
                return jsonify({"message": "due_day must be between 1 and 31"}), 400
        except ValueError:
            return jsonify({"message": "due_day must be an integer"}), 400

        # --- Validate frequency ---
        frequency = data.get("frequency", "monthly").lower()
        if frequency not in ["monthly", "quarterly", "yearly"]:
            return jsonify({"message": "frequency must be 'monthly', 'quarterly', or 'yearly'"}), 400

        # --- Create reminder ---
        reminder = RentReminder(
            tenant_name=data["tenant_name"],
            email=data["email"],
            phone_number=phone_number,
            rent_date=rent_date,
            rent_amount=rent_amount,
            due_day=due_day,
            frequency=frequency,
            user_id=user_id,
        )
        db.session.add(reminder)
        db.session.commit()

        return jsonify({"message": "Reminder added"}), 201

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error adding reminder: {e}")
        return jsonify({"message": "Failed to add reminder", "details": str(e)}), 500

@api.route("/edit_reminder/<int:reminder_id>", methods=["PUT"])
@jwt_required()
def edit_reminder(reminder_id):
    try:
        data = request.get_json(silent=True) or request.form
        user_id = get_jwt_identity()

        # --- Check if reminder exists and belongs to user ---
        reminder = RentReminder.query.filter_by(id=reminder_id, user_id=user_id).first()
        if not reminder:
            return jsonify({"message": "Reminder not found or unauthorized"}), 403

        # --- Update fields if provided ---
        if "tenant_name" in data:
            tenant_name = data["tenant_name"].strip()
            if not tenant_name:
                return jsonify({"message": "tenant_name cannot be empty"}), 400
            reminder.tenant_name = tenant_name

        if "email" in data:
            email = data["email"].strip()
            if not re.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", email):
                return jsonify({"message": "Invalid email format"}), 400
            reminder.email = email

        if "rent_date" in data:
            try:
                reminder.rent_date = datetime.strptime(data["rent_date"], "%Y-%m-%d").date()
            except ValueError:
                return jsonify({"message": "Invalid rent_date format. Use YYYY-MM-DD"}), 400

        if "rent_amount" in data:
            try:
                rent_amount = float(data["rent_amount"])
                if rent_amount <= 0:
                    return jsonify({"message": "Rent amount must be positive"}), 400
                reminder.rent_amount = rent_amount
            except ValueError:
                return jsonify({"message": "Rent amount must be numeric"}), 400

        if "phone_number" in data:
            phone_number = data["phone_number"].strip() if data["phone_number"] else None
            if phone_number and not re.match(r"^\+?\d{7,15}$", phone_number):
                return jsonify({"message": "Invalid phone number format"}), 400
            reminder.phone_number = phone_number

        if "due_day" in data:
            try:
                due_day = int(data["due_day"])
                if not (1 <= due_day <= 31):
                    return jsonify({"message": "due_day must be between 1 and 31"}), 400
                reminder.due_day = due_day
            except ValueError:
                return jsonify({"message": "due_day must be an integer"}), 400

        if "frequency" in data:
            frequency = data["frequency"].lower()
            if frequency not in ["monthly", "quarterly", "yearly"]:
                return jsonify({"message": "frequency must be 'monthly', 'quarterly', or 'yearly'"}), 400
            reminder.frequency = frequency

        # --- Commit changes ---
        db.session.commit()
        return jsonify({"message": "Reminder updated successfully"}), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Edit reminder error: {e}")
        return jsonify({"message": "Failed to update reminder", "details": str(e)}), 500


@api.route("/delete_reminder/<int:reminder_id>", methods=["DELETE"])
@jwt_required()
def delete_reminder(reminder_id):
    try:
        user_id = get_jwt_identity()

        # --- Check if reminder exists and belongs to user ---
        reminder = RentReminder.query.filter_by(id=reminder_id, user_id=user_id).first()
        if not reminder:
            return jsonify({"message": "Reminder not found or unauthorized"}), 403

        db.session.delete(reminder)
        db.session.commit()
        return jsonify({"message": "Reminder deleted successfully"}), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Delete reminder error: {e}")
        return jsonify({"message": "Failed to delete reminder", "details": str(e)}), 500
    
@api.route("/reminders", methods=["GET"])
@jwt_required()
def get_reminders():
    try:
        # --- Validate JWT identity ---
        user_id = int(get_jwt_identity())
        if not user_id or not isinstance(user_id, int):
            return jsonify({"message": "Invalid token or user ID"}), 400

        # --- Optional: validate query parameters ---
        # For example, if you support filtering by date or tenant name:
        tenant_name = request.args.get("tenant_name")
        if tenant_name is not None and not isinstance(tenant_name, str):
            return jsonify({"message": "tenant_name must be a string"}), 400

        rent_date = request.args.get("rent_date")
        if rent_date is not None:
            try:
                datetime.strptime(rent_date, "%Y-%m-%d")
            except ValueError:
                return jsonify({"message": "rent_date must be in YYYY-MM-DD format"}), 400

        # --- Build query ---
        query = RentReminder.query.filter_by(user_id=user_id)
        if tenant_name:
            query = query.filter(RentReminder.tenant_name.ilike(f"%{tenant_name}%"))
        if rent_date:
            query = query.filter(RentReminder.rent_date == rent_date)

        reminders = query.all()

        # --- Empty result check ---
        if not reminders:
            return jsonify({"message": "No reminders found"}), 200

        # --- Return valid response ---
        return jsonify([
            {
                "id": r.id,
                "tenant_name": r.tenant_name,
                "email": r.email,
                "rent_date": r.rent_date.strftime("%Y-%m-%d"),
                "rent_amount": float(r.rent_amount),
            }
            for r in reminders
        ]), 200

    except Exception as e:
        current_app.logger.error(f"Get reminders error: {e}")
        return jsonify({"message": "Failed to fetch reminders", "details": str(e)}), 500



@api.route("/record_payment", methods=["POST"])
@jwt_required()
def record_payment():
    try:
        data = request.get_json(silent=True) or request.form
        user_id = get_jwt_identity()

        # --- Required field checks ---
        required_fields = ["tenant_id", "payment_date", "for_month", "amount_paid"]
        missing = [f for f in required_fields if not data.get(f)]
        if missing:
            return jsonify({"message": f"Missing required fields: {', '.join(missing)}"}), 400

        # --- Validate tenant_id ---
        try:
            tenant_id = int(data["tenant_id"])
        except ValueError:
            return jsonify({"message": "tenant_id must be an integer"}), 400

        # --- Check tenant existence and ownership ---
        reminder = RentReminder.query.filter_by(id=tenant_id, user_id=user_id).first()
        if not reminder:
            return jsonify({"message": "Tenant not found or unauthorized"}), 403

        # --- Validate payment_date ---
        try:
            payment_date = datetime.strptime(data["payment_date"], "%Y-%m-%d").date()
        except ValueError:
            return jsonify({"message": "Invalid payment_date format. Use YYYY-MM-DD"}), 400

        # --- Validate for_month ---
        try:
            for_month = datetime.strptime(data["for_month"], "%Y-%m-%d").date()
        except ValueError:
            return jsonify({"message": "Invalid for_month format. Use YYYY-MM-DD"}), 400

        # --- Validate amount_paid ---
        try:
            amount_paid = float(data["amount_paid"])
            if amount_paid <= 0:
                return jsonify({"message": "amount_paid must be a positive number"}), 400
        except ValueError:
            return jsonify({"message": "amount_paid must be numeric"}), 400

        # --- Compute due date and late flag ---
        due_date = for_month.replace(day=reminder.due_day)
        is_late = payment_date > due_date

        # --- Create payment record ---
        payment = RentPayment(
            tenant_id=tenant_id,
            payment_date=payment_date,
            for_month=for_month,
            amount_paid=amount_paid,
            is_late=is_late,
        )
        db.session.add(payment)
        db.session.commit()

        return jsonify({"message": "Payment recorded"}), 201

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Record payment error: {e}")
        return jsonify({"message": "Failed to record payment", "details": str(e)}), 500
    
@api.route("/update_payment/<int:payment_id>", methods=["PUT"])
@jwt_required()
def update_payment(payment_id):
    try:
        data = request.get_json(silent=True) or request.form
        user_id = get_jwt_identity()

        payment = (
            RentPayment.query
            .join(RentReminder)
            .filter(RentPayment.id == payment_id, RentReminder.user_id == user_id)
            .first()
        )
        if not payment:
            return jsonify({"error": "Payment not found or not authorized"}), 404

        # Optional updates
        if "payment_date" in data:
            payment.payment_date = datetime.strptime(data["payment_date"], "%Y-%m-%d").date()
        if "for_month" in data:
            payment.for_month = datetime.strptime(data["for_month"], "%Y-%m-%d").date()
        if "amount_paid" in data:
            payment.amount_paid = float(data["amount_paid"])

        db.session.commit()
        return jsonify({"message": "Payment updated successfully", "payment_id": payment.id}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500



# --- Delete rent payment ---
@api.route("/delete_payment/<int:payment_id>", methods=["DELETE"])
@jwt_required()
def delete_payment(payment_id):
    try:
        user_id = get_jwt_identity()

        # Fetch the payment and ensure it belongs to the user
        payment = (
            RentPayment.query
            .join(RentReminder)
            .filter(RentPayment.id == payment_id, RentReminder.user_id == user_id)
            .first()
        )
        if not payment:
            return jsonify({"error": "Payment not found or not authorized"}), 404

        db.session.delete(payment)
        db.session.commit()
        return jsonify({"message": "Payment deleted successfully"}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@api.route("/payments", methods=["GET"])
@jwt_required()
def get_payments():
    user_id = get_jwt_identity()

    tenant_name = request.args.get("tenant_name")
    for_month = request.args.get("for_month")  # expected format: YYYY-MM
    start_date = request.args.get("start_date")  # expected format: YYYY-MM-DD
    end_date = request.args.get("end_date")      # expected format: YYYY-MM-DD

    query = RentPayment.query.join(RentReminder).filter(RentReminder.user_id == user_id)

    # --- optional filters ---
    if tenant_name:
        query = query.filter(RentReminder.tenant_name.ilike(f"%{tenant_name}%"))

    if for_month:
        try:
            month_date = datetime.strptime(for_month, "%Y-%m")
            query = query.filter(RentPayment.for_month == month_date.date())
        except ValueError:
            return jsonify({"error": "Invalid for_month format. Use YYYY-MM"}), 400

    if start_date:
        try:
            sd = datetime.strptime(start_date, "%Y-%m-%d")
            query = query.filter(RentPayment.payment_date >= sd.date())
        except ValueError:
            return jsonify({"error": "Invalid start_date format. Use YYYY-MM-DD"}), 400

    if end_date:
        try:
            ed = datetime.strptime(end_date, "%Y-%m-%d")
            query = query.filter(RentPayment.payment_date <= ed.date())
        except ValueError:
            return jsonify({"error": "Invalid end_date format. Use YYYY-MM-DD"}), 400

    payments = query.order_by(RentPayment.payment_date.desc()).all()

    result = [
        {
            "id": p.id,
            "tenant_name": p.tenant.tenant_name,
            "payment_date": p.payment_date.isoformat(),
            "for_month": p.for_month.isoformat(),
            "amount_paid": p.amount_paid,
            "is_late": p.is_late
        }
        for p in payments
    ]

    return jsonify(result), 200



# ---------------------
# Password Reset Routes
# ---------------------

@api.route("/forgot-password", methods=["POST"])
def forgot_password():
    try:
        data = request.get_json(silent=True) or request.form
        email = data.get("email")
        user = User.query.filter_by(email=email).first()
        if not user:
            return jsonify({"message": "Email not found"}), 404

        token = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(hours=1)
        reset_token = PasswordResetToken(user_id=user.id, token=token, expires_at=expires_at)

        db.session.add(reset_token)
        db.session.commit()

        reset_link = url_for("api.reset_password", token=token, _external=True)
        msg = Message("Password Reset Request", recipients=[email])
        msg.body = f"Click the link to reset your password: {reset_link}"

        try:
            mail.send(msg)
        except Exception as e:
            current_app.logger.error(f"Mail send failed: {e}")

        return jsonify({"message": "Password reset email sent"}), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Forgot password error: {e}")
        return jsonify({"message": "Failed to send reset email", "details": str(e)}), 500


@api.route("/reset-password/<token>", methods=["POST"])
def reset_password(token):
    try:
        data = request.get_json(silent=True) or request.form
        password = data.get("password")

        # --- Password validation ---
        if not password:
            return jsonify({"message": "Password is required"}), 400
        if len(password) < 8:
            return jsonify({"message": "Password must be at least 8 characters long"}), 400
        if not any(c.isupper() for c in password) or not any(c.isdigit() for c in password):
            return jsonify({"message": "Password must contain at least one uppercase letter and one digit"}), 400

        reset_token = PasswordResetToken.query.filter_by(token=token).first()
        if not reset_token or reset_token.is_expired():
            return jsonify({"message": "Invalid or expired token"}), 400

        user = User.query.get(reset_token.user_id)
        user.password = generate_password_hash(password)

        db.session.delete(reset_token)
        db.session.commit()

        return jsonify({"message": "Password has been reset successfully"}), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Reset password error: {e}")
        return jsonify({"message": "Failed to reset password", "details": str(e)}), 500

