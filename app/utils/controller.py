from app.models import User, PasswordResetToken , Tenant, Property, Payment
from app.utils.helper import AuthHelper, TwilioHelper
from app import db, mail
from flask_mail import Message
from flask import Blueprint, request, jsonify, url_for, current_app
import secrets, re
from datetime import datetime, timedelta, date
from flask_jwt_extended import get_jwt_identity
from re import match
from calendar import monthrange, month_abbr

class AuthController:

    def __init__(self):
        self.auth_helper = AuthHelper()
        self.data = request.get_json(silent=True) or request.form
    
    def register(self):
        try:
            data = self.data

            username = data.get("username", "").strip()
            email = data.get("email", "").strip()
            contact = data.get("contact", "").strip()
            password = data.get("password", "")
            role = data.get("role", "OWNER")

            # -------- Validation --------
            if not all([username, email, contact, password]):
                return jsonify({
                    "error": "All fields (username, email, contact, password) are required"
                }), 400

            if not 3 <= len(username) <= 50:
                return jsonify({"error": "Username must be between 3 and 50 characters"}), 400

            if not re.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", email):
                return jsonify({"error": "Invalid email format"}), 400

            if not re.match(r"^(?:\+91|0)?[6-9]\d{9}$", contact):
                return jsonify({"error": "Invalid phone number format"}), 400

            if len(password) < 8 or not any(c.isupper() for c in password) or not any(c.isdigit() for c in password):
                return jsonify({
                    "error": "Password must be at least 8 characters long and contain one uppercase letter and one digit"
                }), 400

            # -------- Uniqueness Checks --------
            if User.query.filter(
                (User.username == username) |
                (User.email == email) |
                (User.contact == contact)
            ).first():
                return jsonify({
                    "error": "Username, email, or contact already exists"
                }), 400

            # -------- Create User --------
            new_user = User(
                username=username,
                email=email,
                contact=contact,
                password=self.auth_helper.hash_password(password),
                role=role
            )

            db.session.add(new_user)
            db.session.commit()

            current_app.logger.info(
                f"User registered successfully: {username} ({email})"
            )

            # -------- Send Welcome Email (Non-blocking) --------
            try:
                msg = Message(
                    "Welcome to RemindMyRent!",
                    recipients=[email],
                    body=f"Hello {username},\n\nWelcome to RemindMyRent!"
                )
                mail.send(msg)
            except Exception:
                current_app.logger.warning(
                    f"Welcome email failed for {email}",
                    exc_info=True
                )

            return jsonify({"message": "User registered successfully"}), 201

        except Exception:
            db.session.rollback()
            current_app.logger.error("Registration failed", exc_info=True)
            return jsonify({"error": "Registration failed"}), 500

        
    def login(self):
        try:
            email = (self.data.get("email") or "").strip()
            password = self.data.get("password") or ""

            # -------- Validation --------
            if not email or not password:
                return jsonify({"error": "Email and password are required"}), 400

            if not re.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", email):
                return jsonify({"error": "Invalid email format"}), 400

            if len(password) < 8:
                return jsonify({"error": "Invalid email or password"}), 401

            # -------- Authentication --------
            user = User.query.filter_by(email=email).first()
            if not user or not self.auth_helper.verify_password(password, user.password):
                return jsonify({"error": "Invalid email or password"}), 401

            # -------- Token Generation --------
            tokens = self.auth_helper.generate_tokens(
                identity=str(user.id),
                claims={
                    "username": user.username,
                    "email": user.email,
                    "role": user.role
                }
            )

            return jsonify(tokens), 200

        except Exception:
            current_app.logger.error("Login failed", exc_info=True)
            return jsonify({"error": "Login failed"}), 500


    def logout(self):
        try:
            self.auth_helper.blacklist_token()
            return jsonify({"message": "Successfully logged out"}), 200
        except Exception as e:
            current_app.logger.error(f"Logout error: {e}")
            return jsonify({"message": "Logout failed", "details": str(e)}), 500
        
        
    def forgot_password(self):
        try:
            email = (self.data.get("email") or "").strip()

            # -------- Validation --------
            if not email:
                return jsonify({"error": "Email is required"}), 400

            if not re.match(r"^[^@]+@[^@]+\.[^@]+$", email):
                return jsonify({"error": "Invalid email format"}), 400

            user = User.query.filter_by(email=email).first()

            if user:
                token = secrets.token_urlsafe(32)
                expires_at = datetime.utcnow() + timedelta(hours=1)

                reset_token = PasswordResetToken(
                    user_id=user.id,
                    token=token,
                    expires_at=expires_at
                )
                db.session.add(reset_token)
                db.session.commit()

                reset_link = url_for(
                    "api.reset_password",
                    token=token,
                    _external=True
                )

                try:
                    msg = Message(
                        "Password Reset Request",
                        recipients=[email],
                        body=f"Click the link to reset your password:\n\n{reset_link}"
                    )
                    mail.send(msg)
                    current_app.logger.info(
                        f"Password reset email sent to {email}"
                    )
                except Exception:
                    current_app.logger.warning(
                        f"Failed to send reset email to {email}",
                        exc_info=True
                    )

            # Always return generic response
            return jsonify({
                "message": "If this email exists, a reset link has been sent"
            }), 200

        except Exception:
            db.session.rollback()
            current_app.logger.error("Forgot password failed", exc_info=True)
            return jsonify({"error": "Forgot password failed"}), 500


            
    def reset_password(self, token):
        try:
            password = (self.data.get("password") or "").strip()

            # -------- Password Validation --------
            if not password:
                return jsonify({"error": "Password is required"}), 400

            if len(password) < 8 or not any(c.isupper() for c in password) or not any(c.isdigit() for c in password):
                return jsonify({
                    "error": "Password must be at least 8 characters long and contain one uppercase letter and one digit"
                }), 400

            reset_token = PasswordResetToken.query.filter_by(token=token).first()

            if not reset_token or reset_token.is_expired():
                return jsonify({"error": "Invalid or expired token"}), 400

            user = User.query.get(reset_token.user_id)
            if not user:
                return jsonify({"error": "Invalid or expired token"}), 400

            # -------- Update Password --------
            user.password = self.auth_helper.hash_password(password)

            # -------- Invalidate Token --------
            db.session.delete(reset_token)
            db.session.commit()

            return jsonify({
                "message": "Password has been reset successfully"
            }), 200

        except Exception:
            db.session.rollback()
            current_app.logger.error("Reset password failed", exc_info=True)
            return jsonify({"error": "Reset password failed"}), 500

class ProfileController:

    def __init__(self):
        self.data = request.get_json(silent=True) or request.form
        self.user_id = get_jwt_identity()

    def get_profile(self):
        try:
            user = User.query.get(self.user_id)

            if not user:
                return jsonify({"error": "User not found"}), 404

            return jsonify({
                "id": str(user.id),
                "username": user.username,
                "email": user.email,
                "contact": user.contact,
                "role": user.role,
                "created_date": user.created_date.isoformat() if user.created_date else None
            }), 200

        except Exception:
            current_app.logger.error("Failed to fetch user profile", exc_info=True)
            return jsonify({"error": "Failed to fetch profile"}), 500

    def update_profile(self):
        try:
            user = User.query.get(self.user_id)

            if not user:
                return jsonify({"error": "User not found"}), 404

            # Update fields safely
            user.username = self.data.get("username", user.username).strip()
            user.contact = self.data.get("contact", user.contact).strip()

            db.session.commit()

            return jsonify({"message": "Profile updated successfully"}), 200

        except Exception:
            db.session.rollback()
            current_app.logger.error("Failed to update profile", exc_info=True)
            return jsonify({"error": "Failed to update profile"}), 500


    def change_password(self):
        try:
            auth_helper = AuthHelper()
            old_password = self.data.get("old_password")
            new_password = self.data.get("new_password")

            if not old_password or not new_password:
                return jsonify({"message": "Old and new password are required"}), 400

            user = User.query.get(self.user_id)
            if not user:
                return jsonify({"message": "User not found"}), 404

            if not auth_helper.verify_password(user.password, old_password):
                return jsonify({"message": "Incorrect old password"}), 400

            user.password = auth_helper.hash_password(new_password)
            db.session.commit()

            return jsonify({"message": "Password changed successfully"}), 200

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error changing password: {e}", exc_info=True)
            return jsonify({"message": "Failed to change password", "error": str(e)}), 500

        
class TenantController:

    def __init__(self):
        self.data = request.get_json(silent=True) or request.form
        self.user_id = get_jwt_identity()

    # ---------------- ADD TENANT ----------------
    # ---------------- ADD TENANT ----------------
    def add_tenant(self):
        try:
            required_fields = ["name","email", "phone", "property_id", "rent_amount", "due_day"]
            missing = [f for f in required_fields if not self.data.get(f)]
            if missing:
                return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

            # Extract fields
            name = self.data.get("name").strip()
            email = self.data.get("email").strip()
            phone = self.data.get("phone").strip()
            property_id = self.data.get("property_id")
            rent_amount = float(self.data.get("rent_amount"))
            maintenance_amount = float(self.data.get("maintenance_amount", 0))
            due_day = int(self.data.get("due_day"))
            start_date = self.data.get("start_date") or date.today()

            # Validate email
            if email and not re.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", email):
                return jsonify({"error": "Invalid email format"}), 400

            # Validate phone
            if not re.match(r"^(?:\+91|0)?[6-9]\d{9}$", phone):
                return jsonify({"error": "Invalid phone number format"}), 400

            tenant = Tenant(
                name=name,
                email=email,
                phone=phone,
                property_id=property_id,
                rent_amount=rent_amount,
                maintenance_amount=maintenance_amount,
                due_day=due_day,
                start_date=start_date,
                is_active=True
            )

            db.session.add(tenant)
            db.session.commit()
            return jsonify({"message": "Tenant added successfully", "tenant_id": str(tenant.id)}), 201

        except Exception:
            db.session.rollback()
            current_app.logger.error("Failed to add tenant", exc_info=True)
            return jsonify({"error": "Failed to add tenant"}), 500


    # ---------------- UPDATE TENANT ----------------
    def update_tenant(self, tenant_id):
        try:
            tenant = Tenant.query.filter_by(id=tenant_id, is_active=True).first()
            if not tenant:
                return jsonify({"error": "Tenant not found"}), 404

            # Update fields if provided
            name = self.data.get("name")
            email = self.data.get("email")
            phone = self.data.get("phone")
            rent_amount = self.data.get("rent_amount")
            maintenance_amount = self.data.get("maintenance_amount")
            due_day = self.data.get("due_day")
            start_date = self.data.get("start_date")
            is_active = self.data.get("is_active")

            if name:
                tenant.name = name.strip()
            if email is not None:
                if email and not re.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", email):
                    return jsonify({"error": "Invalid email format"}), 400
                tenant.email = email.strip() if email else None
            if phone is not None:
                if phone and not re.match(r"^(?:\+91|0)?[6-9]\d{9}$", phone):
                    return jsonify({"error": "Invalid phone number format"}), 400
                tenant.phone = phone.strip() if phone else tenant.phone
            if rent_amount is not None:
                tenant.rent_amount = float(rent_amount)
            if maintenance_amount is not None:
                tenant.maintenance_amount = float(maintenance_amount)
            if due_day is not None:
                tenant.due_day = int(due_day)
            if start_date is not None:
                tenant.start_date = start_date
            if is_active is not None:
                tenant.is_active = bool(is_active)

            db.session.commit()
            return jsonify({"message": "Tenant updated successfully"}), 200

        except Exception:
            db.session.rollback()
            current_app.logger.error("Failed to update tenant", exc_info=True)
            return jsonify({"error": "Failed to update tenant"}), 500


    # ---------------- DELETE TENANT (SOFT DELETE) ----------------
    def delete_tenant(self, tenant_id):
        try:
            tenant = Tenant.query.filter_by(id=tenant_id, is_active=True).first()
            if not tenant:
                return jsonify({"error": "Tenant not found"}), 404

            # Soft delete
            tenant.is_active = False
            db.session.commit()

            return jsonify({"message": "Tenant marked as inactive"}), 200

        except Exception:
            db.session.rollback()
            current_app.logger.error("Failed to delete tenant", exc_info=True)
            return jsonify({"error": "Failed to delete tenant"}), 500

    # ---------------- GET ALL TENANTS ----------------
    def get_all_tenants(self):
        try:
            # --- Pagination ---
            page = int(request.args.get("page", 1))
            per_page = int(request.args.get("per_page", 10))
            search = (request.args.get("search") or "").strip()
            status_filter = request.args.get("status")  # Active / Inactive (optional)

            # --- Base Query: tenants of current user via properties ---
            query = Tenant.query.join(Property).filter(Property.owner_id == self.user_id)

            # --- Filter by active/inactive ---
            if status_filter:
                if status_filter.lower() == "active":
                    query = query.filter(Tenant.is_active.is_(True))
                elif status_filter.lower() == "inactive":
                    query = query.filter(Tenant.is_active.is_(False))

            # --- Search by name, email, phone ---
            if search:
                like_pattern = f"%{search}%"
                query = query.filter(
                    (Tenant.name.ilike(like_pattern)) |
                    (Tenant.email.ilike(like_pattern)) |
                    (Tenant.phone.ilike(like_pattern))
                )

            # --- Pagination ---
            pagination = query.order_by(Tenant.created_date.desc()).paginate(
                page=page, per_page=per_page, error_out=False
            )
            tenants = pagination.items

            # --- Format response ---
            tenant_list = [
                {
                    "id": str(t.id),
                    "name": t.name,
                    "email": t.email,
                    "phone": t.phone,
                    "property_id": str(t.property_id),
                    "property_name": t.property.name if t.property else None,
                    "rent_amount": t.rent_amount,
                    "maintenance_amount": t.maintenance_amount,
                    "due_day": t.due_day,
                    "start_date": t.start_date.isoformat() if t.start_date else None,
                    "is_active": t.is_active,
                    "created_date": t.created_date.isoformat() if t.created_date else None,
                    "updated_date": t.updated_date.isoformat() if t.updated_date else None
                }
                for t in tenants
            ]

            return jsonify({
                "tenants": tenant_list,
                "total": pagination.total,
                "page": pagination.page,
                "pages": pagination.pages,
                "per_page": pagination.per_page
            }), 200

        except Exception:
            current_app.logger.error("Failed to fetch tenants", exc_info=True)
            return jsonify({"error": "Failed to fetch tenants"}), 500


    # ---------------- GET TENANT DETAIL ----------------
    def get_tenant_detail(self, tenant_id):
        try:
            # Fetch tenant belonging to current user's property
            tenant = Tenant.query.join(Property)\
                .filter(Tenant.id == tenant_id, Property.owner_id == self.user_id)\
                .first()

            if not tenant:
                return jsonify({"error": "Tenant not found"}), 404

            # Get related property info
            property_obj = tenant.property

            return jsonify({
                "id": str(tenant.id),
                "name": tenant.name,
                "email": tenant.email,
                "phone": tenant.phone,
                "property_id": str(tenant.property_id),
                "property_name": property_obj.name if property_obj else None,
                "rent_amount": tenant.rent_amount,
                "maintenance_amount": tenant.maintenance_amount,
                "due_day": tenant.due_day,
                "start_date": tenant.start_date.isoformat() if tenant.start_date else None,
                "is_active": tenant.is_active,
                "created_date": tenant.created_date.isoformat() if tenant.created_date else None,
                "updated_date": tenant.updated_date.isoformat() if tenant.updated_date else None
            }), 200

        except Exception:
            current_app.logger.error("Error fetching tenant details", exc_info=True)
            return jsonify({"error": "Failed to fetch tenant details"}), 500

class PropertyController:

    def __init__(self):
        self.data = request.get_json(silent=True) or request.form
        self.user_id = get_jwt_identity()


    # ---------------- ADD PROPERTY ----------------
    def add_property(self):
        try:
            required_fields = ["name", "address"]
            missing = [f for f in required_fields if not self.data.get(f)]
            if missing:
                return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

            new_property = Property(
                owner_id=self.user_id,
                name=self.data["name"].strip(),
                address=self.data["address"].strip()
            )

            db.session.add(new_property)
            db.session.commit()

            return jsonify({
                "message": "Property added successfully",
                "property": {
                    "id": str(new_property.id),
                    "name": new_property.name,
                    "address": new_property.address
                }
            }), 201

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error adding property: {e}", exc_info=True)
            return jsonify({"error": "Failed to add property"}), 500

    # ---------------- UPDATE PROPERTY ----------------
    def update_property(self, property_id):
        try:
            prop = Property.query.filter_by(id=property_id, owner_id=self.user_id).first()
            if not prop:
                return jsonify({"error": "Property not found or unauthorized"}), 404

            # Update only valid fields
            if "name" in self.data and self.data["name"]:
                prop.name = self.data["name"].strip()
            if "address" in self.data and self.data["address"]:
                prop.address = self.data["address"].strip()

            db.session.commit()
            return jsonify({"message": "Property updated successfully"}), 200

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating property: {e}", exc_info=True)
            return jsonify({"error": "Failed to update property"}), 500

    # ---------------- DELETE PROPERTY ----------------
    def delete_property(self, property_id):
        try:
            prop = Property.query.filter_by(id=property_id, owner_id=self.user_id).first()
            if not prop:
                return jsonify({"error": "Property not found or unauthorized"}), 404

            db.session.delete(prop)
            db.session.commit()
            return jsonify({"message": "Property deleted successfully"}), 200

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error deleting property: {e}", exc_info=True)
            return jsonify({"error": "Failed to delete property"}), 500

        
    def get_all_properties(self):
        try:
            # --- Query params ---
            page = int(request.args.get("page", 1))
            per_page = int(request.args.get("per_page", 10))
            search = request.args.get("search", "").strip()

            # --- Base query ---
            query = Property.query.filter_by(owner_id=self.user_id)

            # --- Apply search filter if provided ---
            if search:
                like_pattern = f"%{search}%"
                query = query.filter(
                    (Property.name.ilike(like_pattern)) |
                    (Property.address.ilike(like_pattern))
                )

            # --- Paginate results ---
            pagination = query.order_by(Property.created_at.desc()).paginate(
                page=page, per_page=per_page, error_out=False
            )
            properties = pagination.items

            # --- Convert to list of dicts with tenants ---
            property_list = [
                {
                    "id": str(p.id),
                    "name": p.name,
                    "address": p.address,
                    "created_at": p.created_at.isoformat() if p.created_at else None,
                    "updated_at": p.updated_at.isoformat() if p.updated_at else None,
                    "tenants": [
                        {
                            "id": str(t.id),
                            "name": t.name,
                            "email": t.email,
                            "phone": t.phone,
                            "rent_amount": t.rent_amount,
                            "maintenance_amount": t.maintenance_amount,
                            "due_day": t.due_day,
                            "start_date": t.start_date.isoformat() if t.start_date else None,
                            "is_active": t.is_active
                        }
                        for t in p.tenants
                    ]
                }
                for p in properties
            ]

            return jsonify({
                "properties": property_list,
                "total": pagination.total,
                "page": pagination.page,
                "pages": pagination.pages,
                "per_page": pagination.per_page
            }), 200

        except Exception as e:
            current_app.logger.error(f"Error fetching properties: {e}", exc_info=True)
            return jsonify({"error": "Failed to fetch properties"}), 500
            
    def get_property_detail(self, property_id):
        try:
            property_obj = Property.query.filter_by(
                id=property_id, owner_id=self.user_id
            ).first()

            if not property_obj:
                current_app.logger.warning(
                    f"Property ID {property_id} not found for user {self.user_id}"
                )
                return jsonify({"error": "Property not found"}), 404

            result = {
                "id": str(property_obj.id),
                "owner_id": str(property_obj.owner_id),
                "owner_name": getattr(property_obj.owner, "username", None),
                "name": property_obj.name,
                "address": property_obj.address,
                "created_at": property_obj.created_at.isoformat() if property_obj.created_at else None,
                "updated_at": property_obj.updated_at.isoformat() if property_obj.updated_at else None,
                "tenants": [
                    {
                        "id": str(t.id),
                        "name": t.name,
                        "email": t.email,
                        "phone": t.phone,
                        "rent_amount": t.rent_amount,
                        "maintenance_amount": t.maintenance_amount,
                        "due_day": t.due_day,
                        "start_date": t.start_date.isoformat() if t.start_date else None,
                        "is_active": t.is_active
                    }
                    for t in property_obj.tenants
                ]
            }

            return jsonify(result), 200

        except Exception as e:
            current_app.logger.error(
                f"Failed to fetch property ID {property_id}: {e}", exc_info=True
            )
            return jsonify({"error": "Internal server error"}), 500

class PaymentController:

    def get_pending_summary(self):
        try:
            payments = (
                Payment.query
                .join(Tenant, Payment.tenant_id == Tenant.id)
                .join(Property, Tenant.property_id == Property.id)
                .filter(
                    Property.owner_id == self.user_id,
                    Payment.status == "PENDING"
                )
                .all()
            )

            data = []
            total_due = 0

            for p in payments:
                amount = p.rent_amount + p.maintenance_amount
                total_due += amount

                data.append({
                    "payment_id": str(p.id),
                    "tenant_name": p.tenant.name,
                    "property_name": p.tenant.property.name,
                    "month": p.month,
                    "total_amount": amount
                })

            return jsonify({
                "pending_count": len(data),
                "total_due": total_due,
                "payments": data
            }), 200

        except Exception as e:
            current_app.logger.error(f"Pending summary error: {e}", exc_info=True)
            return jsonify({"message": "Failed to load pending summary"}), 500

        
        
    def get_tenant_payments(self, tenant_id):
        try:
            payments = Payment.query.filter_by(
                tenant_id=tenant_id
            ).order_by(Payment.month.desc()).all()

            return jsonify([
                {
                    "id": str(p.id),
                    "month": p.month,
                    "rent_amount": p.rent_amount,
                    "maintenance_amount": p.maintenance_amount,
                    "total": p.rent_amount + p.maintenance_amount,
                    "status": p.status,
                    "paid_on": p.paid_on.isoformat() if p.paid_on else None
                }
                for p in payments
            ]), 200

        except Exception as e:
            current_app.logger.error(f"Fetch payments failed: {e}", exc_info=True)
            return jsonify({"message": "Failed to fetch payments"}), 500

    def mark_payment_paid(self, payment_id):
        try:
            payment = (
                Payment.query
                .join(Tenant)
                .join(Property)
                .filter(
                    Payment.id == payment_id,
                    Property.owner_id == self.user_id
                )
                .first()
            )

            if not payment:
                return jsonify({"message": "Payment not found"}), 404

            if payment.status == "PAID":
                return jsonify({"message": "Payment already marked as paid"}), 400

            payment.status = "PAID"
            payment.paid_on = date.today()
            payment.payment_mode = self.data.get("payment_mode", "Cash")

            db.session.commit()

            return jsonify({
                "message": "Payment marked as paid",
                "payment_id": str(payment.id),
                "paid_on": payment.paid_on.isoformat(),
                "payment_mode": payment.payment_mode
            }), 200

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Payment update failed: {e}", exc_info=True)
            return jsonify({"message": "Failed to update payment"}), 500


class DashboardController:


    def get_dashboard_summary(self):
        try:
            today = date.today()
            month_str = today.strftime("%Y-%m")

            payments = (
                Payment.query
                .join(Tenant)
                .join(Property)
                .filter(
                    Property.owner_id == self.user_id,
                    Payment.month == month_str
                )
                .all()
            )

            total_due = 0
            total_paid = 0
            overdue = 0

            for p in payments:
                amount = p.rent_amount + p.maintenance_amount
                total_due += amount

                if p.status == "PAID":
                    total_paid += amount
                else:
                    due_date = date(today.year, today.month, p.tenant.due_day)
                    if today > due_date:
                        overdue += amount

            active_tenants = Tenant.query.join(Property).filter(
                Property.owner_id == self.user_id,
                Tenant.is_active == True
            ).count()

            return jsonify({
                "month": month_str,
                "total_due": total_due,
                "total_paid": total_paid,
                "total_pending": total_due - total_paid,
                "overdue_amount": overdue,
                "active_tenants": active_tenants
            }), 200

        except Exception as e:
            current_app.logger.error(f"Dashboard error: {e}", exc_info=True)
            return jsonify({"message": "Failed to load dashboard"}), 500

    def get_overdue_payments(self):
        try:
            today = date.today()
            month_str = today.strftime("%Y-%m")

            payments = (
                Payment.query
                .join(Tenant)
                .join(Property)
                .filter(
                    Property.owner_id == self.user_id,
                    Payment.month == month_str,
                    Payment.status == "PENDING"
                )
                .all()
            )

            overdue_list = []

            for p in payments:
                due_date = date(today.year, today.month, p.tenant.due_day)
                if today > due_date:
                    overdue_list.append({
                        "payment_id": str(p.id),
                        "tenant_name": p.tenant.name,
                        "phone": p.tenant.phone,
                        "amount": p.rent_amount + p.maintenance_amount,
                        "due_day": p.tenant.due_day,
                        "days_overdue": (today - due_date).days
                    })

            return jsonify(overdue_list), 200

        except Exception as e:
            current_app.logger.error(f"Overdue fetch failed: {e}", exc_info=True)
            return jsonify({"message": "Failed to fetch overdue payments"}), 500
        

    def get_monthly_payments(self):        #owner view
        try:
            month = request.args.get("month") or date.today().strftime("%Y-%m")

            payments = (
                Payment.query
                .join(Tenant)
                .join(Property)
                .filter(
                    Property.owner_id == self.user_id,
                    Payment.month == month
                )
                .order_by(Payment.created_at.desc())
                .all()
            )

            return jsonify([
                {
                    "id": str(p.id),
                    "tenant": p.tenant.name,
                    "phone": p.tenant.phone,
                    "rent": p.rent_amount,
                    "maintenance": p.maintenance_amount,
                    "total": p.rent_amount + p.maintenance_amount,
                    "status": p.status,
                    "paid_on": p.paid_on.isoformat() if p.paid_on else None
                }
                for p in payments
            ]), 200

        except Exception as e:
            current_app.logger.error(f"Monthly payments error: {e}")
            return jsonify({"message": "Failed to fetch payments"}), 500











