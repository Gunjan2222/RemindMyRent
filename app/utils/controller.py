from app.models import User, PasswordResetToken , Tenant, Property, Payment
from app.utils.helper import AuthHelper
from app import db, mail
from flask_mail import Message
from flask import Blueprint, request, jsonify, url_for, current_app
import secrets, re
from datetime import datetime, timedelta, date
from flask_jwt_extended import get_jwt_identity
from app.models import PaymentStatus
from calendar import monthrange
from app.tasks import send_welcome_email_task
# from app.utils.helper import TwilioHelper

class AuthController:

    def __init__(self):
        self.auth_helper = AuthHelper()
        self.data = request.get_json(silent=True) or request.form
    
    def register(self):
        try:
            # twilio = TwilioHelper()
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

            if (
                len(password) < 8
                or not any(c.isupper() for c in password)
                or not any(c.islower() for c in password)
                or not any(c.isdigit() for c in password)
                or not any(not c.isalnum() for c in password)
            ):
                return jsonify({
                    "error": "Password must be at least 8 characters long and contain one uppercase letter and one digit"
                }), 400

            # -------- Uniqueness Checks --------
            if User.query.filter(
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

            # -------- Send Welcome Email --------
            send_welcome_email_task.delay(email, username)

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
        except Exception:
            current_app.logger.exception("Logout failed")
            return jsonify({"message": "Logout failed"}), 500
        
        
    def forgot_password(self):
        try:
            email = (self.data.get("email") or "").strip().lower()

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

            if (
                len(password) < 8
                or not any(c.isupper() for c in password)
                or not any(c.islower() for c in password)
                or not any(c.isdigit() for c in password)
                or not any(not c.isalnum() for c in password)
            ):
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
        
    def change_password(self):
        try:
            user_id = get_jwt_identity()

            old_password = (self.data.get("old_password") or "").strip()
            new_password = (self.data.get("new_password") or "").strip()

            if not old_password or not new_password:
                return jsonify({"message": "Old password and new password are required"}), 400

            if (
                len(new_password) < 8
                or not any(c.isupper() for c in new_password)
                or not any(c.islower() for c in new_password)
                or not any(c.isdigit() for c in new_password)
                or not any(not c.isalnum() for c in new_password)
            ):
                return jsonify({"message": (
                        "Password must contain at least 8 characters, "
                        "one uppercase letter, one lowercase letter, "
                        "one number and one special character."
                    )}), 400

            user = User.query.get(user_id)

            if not user:
                return jsonify({"message": "User not found"}), 404

            if not self.auth_helper.verify_password(old_password,user.password):
                return jsonify({"message": "Old password is incorrect"}), 400

            if self.auth_helper.verify_password(new_password,user.password):
                return jsonify({"message": ("New password cannot be the same as ""the old password")}), 400

            user.password = self.auth_helper.hash_password(new_password)

            db.session.commit()

            return jsonify({"message": "Password changed successfully"}), 200

        except Exception:
            db.session.rollback()

            current_app.logger.exception("Failed to change password")

            return jsonify({"message": "Failed to change password"}), 500

# from flask_mail import Message

# msg = Message(
#     subject="Welcome to Remind My Rent",
#     recipients=[tenant.email]
# )

# msg.body = f"""
# Hello {tenant.name},

# You have been added as a tenant for {property_obj.name}.

# Rent Amount: ₹{rent_amount}
# Maintenance Amount: ₹{maintenance_amount}
# Due Date: {due_day}

# Thank you.
# """

# mail.send(msg)
class TenantController:

    def __init__(self):
        self.data = request.get_json(silent=True) or request.form
        self.user_id = get_jwt_identity()

    # ---------------- ADD TENANT ----------------
    def add_tenant(self):
        try:
            required_fields = [
                "name",
                "email",
                "phone",
                "property_name",
                "rent_amount",
                "due_day"
            ]

            missing = [
                field for field in required_fields
                if not self.data.get(field)
            ]

            if missing:
                return jsonify({
                    "error": f"Missing required fields: {', '.join(missing)}"
                }), 400

            # ---------------- Extract & Clean Data ----------------
            name = self.data.get("name", "").strip()
            email = self.data.get("email", "").strip().lower()
            phone = self.data.get("phone", "").strip()
            property_name = self.data.get("property_name")


            # ---------------- Validate Name ----------------
            if len(name) < 3 or len(name) > 100:
                return jsonify({
                    "error": "Name must be between 3 and 100 characters."
                }), 400

            # ---------------- Validate Email ----------------
            if not re.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", email):
                return jsonify({
                    "error": "Invalid email format."
                }), 400

            # ---------------- Validate Phone ----------------
            if not re.match(r"^(?:\+91|0)?[6-9]\d{9}$", phone):
                return jsonify({
                    "error": "Invalid phone number format."
                }), 400

            # ---------------- Validate Numeric Fields ----------------
            try:
                rent_amount = float(self.data.get("rent_amount"))
                maintenance_amount = float(
                    self.data.get("maintenance_amount", 0)
                )
                due_day = int(self.data.get("due_day"))
            except (ValueError, TypeError):
                return jsonify({
                    "error": "Invalid rent amount, maintenance amount or due day."
                }), 400

            if rent_amount <= 0:
                return jsonify({
                    "error": "Rent amount must be greater than zero."
                }), 400

            if maintenance_amount < 0:
                return jsonify({
                    "error": "Maintenance amount cannot be negative."
                }), 400

            if due_day < 1 or due_day > 31:
                return jsonify({
                    "error": "Due day must be between 1 and 31."
                }), 400

            # ---------------- Parse Start Date ----------------
            if self.data.get("start_date"):
                try:
                    start_date = datetime.strptime(
                        self.data.get("start_date"),
                        "%Y-%m-%d"
                    ).date()
                except ValueError:
                    return jsonify({
                        "error": "Invalid start_date format. Use YYYY-MM-DD."
                    }), 400
            else:
                start_date = date.today()

            # ---------------- Verify Property Ownership ----------------
            property_obj = Property.query.filter_by(
                name=property_name,
                owner_id=self.user_id
            ).first()

            if not property_obj:
                return jsonify({
                    "error": "Property not found or unauthorized."
                }), 404

            # ---------------- Duplicate Tenant Check ----------------
            existing_tenant = Tenant.query.filter(
                Tenant.property_id == property_obj.id,
                (
                    (Tenant.email == email) |
                    (Tenant.phone == phone)
                ),
                Tenant.is_active.is_(True)
            ).first()

            if existing_tenant:
                return jsonify({
                    "error": "A tenant with the same email or phone already exists for this property."
                }), 400

            # ---------------- Create Tenant ----------------
            tenant = Tenant(
                name=name,
                email=email,
                phone=phone,
                property_id=property_obj.id,
                rent_amount=rent_amount,
                maintenance_amount=maintenance_amount,
                due_day=due_day,
                start_date=start_date,
                is_active=True
            )

            db.session.add(tenant)
            db.session.commit()

            current_app.logger.info(
                f"Tenant '{tenant.name}' added successfully by user {self.user_id}"
            )

            return jsonify({
                "message": "Tenant added successfully.",
                "tenant": {
                    "id": str(tenant.id),
                    "name": tenant.name,
                    "email": tenant.email,
                    "phone": tenant.phone,
                    "property_id": str(tenant.property_id),
                    "rent_amount": tenant.rent_amount,
                    "maintenance_amount": tenant.maintenance_amount,
                    "due_day": tenant.due_day,
                    "start_date": tenant.start_date.isoformat(),
                    "is_active": tenant.is_active
                }
            }), 201

        except Exception:
            db.session.rollback()
            current_app.logger.exception("Failed to add tenant")
            return jsonify({
                "error": "Failed to add tenant."
            }), 500


    # ---------------- UPDATE TENANT ----------------
    
    def update_tenant(self, tenant_id):
        try:
            tenant = (
                Tenant.query
                .join(Property)
                .filter(
                    Tenant.id == tenant_id,
                    Property.owner_id == self.user_id
                )
                .first()
            )

            if not tenant:
                return jsonify({
                    "error": "Tenant not found or unauthorized."
                }), 404

            # ---------------- Name ----------------
            if "name" in self.data:
                name = self.data.get("name", "").strip()

                if len(name) < 3 or len(name) > 100:
                    return jsonify({
                        "error": "Name must be between 3 and 100 characters."
                    }), 400

                tenant.name = name

            # ---------------- Email ----------------
            if "email" in self.data:
                email = self.data.get("email", "").strip().lower()

                if not re.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", email):
                    return jsonify({
                        "error": "Invalid email format."
                    }), 400

                existing = Tenant.query.filter(
                    Tenant.email == email,
                    Tenant.id != tenant.id,
                    Tenant.property_id == tenant.property_id,
                    Tenant.is_active.is_(True)
                ).first()

                if existing:
                    return jsonify({
                        "error": "Email already exists for another tenant."
                    }), 400

                tenant.email = email

            # ---------------- Phone ----------------
            if "phone" in self.data:
                phone = self.data.get("phone", "").strip()

                if not re.match(r"^(?:\+91|0)?[6-9]\d{9}$", phone):
                    return jsonify({
                        "error": "Invalid phone number."
                    }), 400

                existing = Tenant.query.filter(
                    Tenant.phone == phone,
                    Tenant.id != tenant.id,
                    Tenant.property_id == tenant.property_id,
                    Tenant.is_active.is_(True)
                ).first()

                if existing:
                    return jsonify({
                        "error": "Phone number already exists for another tenant."
                    }), 400

                tenant.phone = phone

            # ---------------- Rent Amount ----------------
            if "rent_amount" in self.data:
                try:
                    rent_amount = float(self.data.get("rent_amount"))

                    if rent_amount <= 0:
                        return jsonify({
                            "error": "Rent amount must be greater than zero."
                        }), 400

                    tenant.rent_amount = rent_amount

                except (ValueError, TypeError):
                    return jsonify({
                        "error": "Invalid rent amount."
                    }), 400

            # ---------------- Maintenance Amount ----------------
            if "maintenance_amount" in self.data:
                try:
                    maintenance = float(self.data.get("maintenance_amount"))

                    if maintenance < 0:
                        return jsonify({
                            "error": "Maintenance amount cannot be negative."
                        }), 400

                    tenant.maintenance_amount = maintenance

                except (ValueError, TypeError):
                    return jsonify({
                        "error": "Invalid maintenance amount."
                    }), 400

            # ---------------- Due Day ----------------
            if "due_day" in self.data:
                try:
                    due_day = int(self.data.get("due_day"))

                    if due_day < 1 or due_day > 31:
                        return jsonify({
                            "error": "Due day must be between 1 and 31."
                        }), 400

                    tenant.due_day = due_day

                except (ValueError, TypeError):
                    return jsonify({
                        "error": "Invalid due day."
                    }), 400

            # ---------------- Start Date ----------------
            if "start_date" in self.data:
                try:
                    tenant.start_date = datetime.strptime(
                        self.data.get("start_date"),
                        "%Y-%m-%d"
                    ).date()
                except ValueError:
                    return jsonify({
                        "error": "Invalid start_date format. Use YYYY-MM-DD."
                    }), 400

            # ---------------- Active Status ----------------
            if "is_active" in self.data:
                value = str(self.data.get("is_active")).lower()

                if value in ["true", "1", "yes"]:
                    tenant.is_active = True
                elif value in ["false", "0", "no"]:
                    tenant.is_active = False
                else:
                    return jsonify({
                        "error": "Invalid value for is_active."
                    }), 400

            db.session.commit()

            current_app.logger.info(
                f"Tenant {tenant.id} updated successfully by user {self.user_id}"
            )

            return jsonify({
                "message": "Tenant updated successfully.",
                "tenant": {
                    "id": str(tenant.id),
                    "name": tenant.name,
                    "email": tenant.email,
                    "phone": tenant.phone,
                    "rent_amount": tenant.rent_amount,
                    "maintenance_amount": tenant.maintenance_amount,
                    "due_day": tenant.due_day,
                    "start_date": tenant.start_date.isoformat() if tenant.start_date else None,
                    "is_active": tenant.is_active
                }
            }), 200

        except Exception:
            db.session.rollback()
            current_app.logger.exception("Failed to update tenant")
            return jsonify({
                "error": "Failed to update tenant."
            }), 500

    # ---------------- DELETE TENANT (SOFT DELETE) ----------------
    def delete_tenant(self, tenant_id):
        try:
            tenant = (
                Tenant.query
                .join(Property)
                .filter(
                    Tenant.id == tenant_id,
                    Tenant.is_active.is_(True),
                    Property.owner_id == self.user_id
                )
                .first()
            )

            if not tenant:
                return jsonify({
                    "error": "Tenant not found or unauthorized."
                }), 404

            # Soft Delete
            tenant.is_active = False

            db.session.commit()

            current_app.logger.info(
                f"Tenant {tenant.id} marked inactive by user {self.user_id}"
            )

            return jsonify({
                "message": "Tenant deleted successfully."
            }), 200

        except Exception:
            db.session.rollback()
            current_app.logger.exception("Failed to delete tenant")
            return jsonify({
                "error": "Failed to delete tenant."
            }), 500
        

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
            pagination = query.order_by(Tenant.created_at.desc()).paginate(
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
                    "created_at": t.created_at.isoformat() if t.created_at else None,
                    "updated_at": t.updated_at.isoformat() if t.updated_at else None
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
            tenant = (
                Tenant.query
                .join(Property)
                .filter(
                    Tenant.id == tenant_id,
                    Property.owner_id == self.user_id
                )
                .first()
            )

            if not tenant:
                return jsonify({
                    "error": "Tenant not found or unauthorized."
                }), 404

            return jsonify({
                "tenant": {
                    "id": str(tenant.id),
                    "name": tenant.name,
                    "email": tenant.email,
                    "phone": tenant.phone,
                    "rent_amount": tenant.rent_amount,
                    "maintenance_amount": tenant.maintenance_amount,
                    "due_day": tenant.due_day,
                    "start_date": tenant.start_date.isoformat() if tenant.start_date else None,
                    "is_active": tenant.is_active,
                    "created_at": tenant.created_at.isoformat() if tenant.created_at else None,
                    "updated_at": tenant.updated_at.isoformat() if tenant.updated_at else None,
                    "property": {
                        "id": str(tenant.property.id),
                        "name": tenant.property.name,
                        "address": tenant.property.address
                    }
                }
            }), 200

        except Exception:
            current_app.logger.exception("Failed to fetch tenant details")
            return jsonify({
                "error": "Failed to fetch tenant details."
            }), 500

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

            name = self.data["name"].strip()
            address = self.data["address"].strip()

            if len(name) < 3:
                return jsonify({
                    "error": "Property name too short"
                }), 400

            new_property = Property(
                owner_id=self.user_id,
                name=name,
                address=address
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
            
            if prop.tenants:
                return jsonify({"error": "Cannot delete property with active tenants."}), 400

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

    def __init__(self):
        self.data = request.get_json(silent=True) or request.form
        self.user_id = get_jwt_identity()

    def get_pending_summary(self):
        try:
            payments = (
                Payment.query
                .join(Tenant, Payment.tenant_id == Tenant.id)
                .join(Property, Tenant.property_id == Property.id)
                .filter(
                    Property.owner_id == self.user_id,
                    Payment.status == PaymentStatus.PENDING
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
            payments = (
                Payment.query
                .join(Tenant)
                .join(Property)
                .filter(
                    Payment.tenant_id == tenant_id,
                    Property.owner_id == self.user_id
                )
                .all()
            )

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

            if payment.status == PaymentStatus.PAID:
                return jsonify({"message": "Payment already marked as paid"}), 400

            payment.status = PaymentStatus.PAID
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

    def __init__(self):
        self.data = request.get_json(silent=True) or request.form
        self.user_id = get_jwt_identity()

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
                    last_day = monthrange(today.year, today.month)[1]
                    due_day = min(p.tenant.due_day, last_day)
                    due_date = date(today.year, today.month, due_day)
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
                    Payment.status == PaymentStatus.PENDING
                )
                .all()
            )

            overdue_list = []

            for p in payments:
                last_day = monthrange(today.year, today.month)[1]
                due_day = min(p.tenant.due_day, last_day)
                due_date = date(today.year, today.month, due_day)
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











