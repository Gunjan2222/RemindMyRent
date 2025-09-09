from app.models import User, PasswordResetToken , Tenant, Property, Lease, RentPayment, RentReminder, NotificationLog
from app.utils.helper import AuthHelper, TwilioHelper
from app import db, mail
from flask_mail import Message
from flask import Blueprint, request, jsonify, url_for, current_app
import secrets, re
from datetime import datetime, timedelta, date
from flask_jwt_extended import get_jwt_identity
from re import match
from calendar import monthrange

class AuthController:

    def __init__(self):
        self.auth_helper = AuthHelper()
        self.data = request.get_json(silent=True) or request.form
    
    def register(self):
        try:
            username = self.data.get("username", "").strip()
            email = self.data.get("email", "").strip()
            contact = self.data.get("contact", "").strip()
            password = self.data.get("password", "")
            role = self.data.get("role")

            # --- Validation ---
            if not username or not email or not contact or not password:
                current_app.logger.warning("Registration failed: missing required fields")
                return jsonify({"error": "All fields (username, email, contact, password) are required"}), 400

            if len(username) < 3 or len(username) > 50:
                return jsonify({"error": "Username must be between 3 and 50 characters"}), 400

            email_regex = r"^[\w\.-]+@[\w\.-]+\.\w+$"
            if not re.match(email_regex, email):
                return jsonify({"error": "Invalid email format"}), 400

            contact_regex = r"^(?:\+91|0)?[6-9]\d{9}$"
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
                password=self.auth_helper.hash_password(password),
                role = role
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
        
    def login(self):
        try:
            # Get data
            email = (self.data.get("email") or "").strip()
            password = (self.data.get("password") or "").strip()

            # --- Field validations ---
            if not email or not password:
                return jsonify({"error": "Email and password are required"}), 400

            email_regex = r"^[\w\.-]+@[\w\.-]+\.\w+$"
            if not re.match(email_regex, email):
                return jsonify({"error": "Invalid email format"}), 400

            if len(password) < 8 or len(password) > 100:
                return jsonify({"error": "Password must be between 8 and 100 characters"}), 400

            # --- Authentication ---
            user = User.query.filter_by(email=email).first()
            if not user or not self.auth_helper.verify_password(password, user.password):
                return jsonify({"error": "Invalid email or password"}), 401

            # --- Token generation ---
            tokens = self.auth_helper.generate_tokens(
            identity=str(user.id),
            claims={
                "username": user.username,
                "email": user.email,
                "role": user.role
                }
            )
            return jsonify(tokens), 200

        except Exception as e:
            current_app.logger.error(f"Login error: {e}", exc_info=True)
            return jsonify({"error": "Login failed", "details": str(e)}), 500

        
    def logout(self):
        try:
            self.auth_helper.blacklist_token()
            return jsonify({"message": "Access token revoked"}), 200
        except Exception as e:
            current_app.logger.error(f"Logout error: {e}")
            return jsonify({"message": "Logout failed", "details": str(e)}), 500
        
        
    def forgot_password(self):
        try:
            email = (self.data.get("email") or "").strip()

            # --- Validation ---
            if not email:
                return jsonify({"message": "Email is required"}), 400

            if not re.match(r"^[^@]+@[^@]+\.[^@]+$", email):
                return jsonify({"message": "Invalid email format"}), 400
            
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
                return jsonify({"message": "If this email exists, a reset link has been sent"}), 200

            return jsonify({"message": "Password reset email sent"}), 200

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Forgot password error: {e}")
            return jsonify({"message": "Failed to send reset email", "details": str(e)}), 500
        
    def reset_password(self, token):
        try:
            password = self.data.get("password")

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
            user.password = self.auth_helper.hash_password(password)

            db.session.delete(reset_token)
            db.session.commit()

            return jsonify({"message": "Password has been reset successfully"}), 200

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Reset password error: {e}")
            return jsonify({"message": "Failed to reset password", "details": str(e)}), 500

class ProfileController:

    def __init__(self):
        self.data = request.get_json(silent=True) or request.form
        self.user_id = get_jwt_identity()

    def get_profile(self):
        try:
            user = User.query.get(self.user_id)
            if not user:
                return jsonify({"message": "User not found"}), 404

            return jsonify({
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "contact": user.contact,
                "profile_photo": user.profile_photo,
                "created_date": user.created_date.isoformat()
            }), 200

        except Exception as e:
            current_app.logger.error(f"Error fetching profile: {e}", exc_info=True)
            return jsonify({"message": "Failed to fetch profile", "error": str(e)}), 500

    def update_profile(self):
        try:
            user = User.query.get(self.user_id)
            if not user:
                return jsonify({"message": "User not found"}), 404

            user.username = self.data.get("username", user.username)
            user.contact = self.data.get("contact", user.contact)
            if "profile_photo" in self.data:
                user.profile_photo = self.data["profile_photo"]

            db.session.commit()
            return jsonify({"message": "Profile updated successfully"}), 200

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating profile: {e}", exc_info=True)
            return jsonify({"message": "Failed to update profile", "error": str(e)}), 500

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

    def add_tenant(self):
        try:
            # --- Required field checks ---
            required_fields = ["name", "email", "phone_number"]
            missing = [f for f in required_fields if not self.data.get(f)]
            if missing:
                return jsonify({"message": f"Missing required fields: {', '.join(missing)}"}), 400
            
            # --- Validate email format ---
            if not match(r"^[\w\.-]+@[\w\.-]+\.\w+$", self.data.get("email")):
                return jsonify({"message": "Invalid email format"}), 400
            
            # --- Validate optional phone number ---
            phone_number = self.data.get("phone_number")
            if phone_number and not match(r"^(?:\+91|0)?[6-9]\d{9}$", phone_number):
                return jsonify({"message": "Invalid phone number format"}), 400
            
            tenant = Tenant(name=self.data.get("name"), phone_number=phone_number, email=self.data.get("email"), address=self.data.get("address"), user_id=self.user_id)

            db.session.add(tenant)
            db.session.commit()

            return jsonify({"message": "Tenant added"}), 201

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error adding tenant: {e}")
            return jsonify({"message": "Failed to add tenant", "details": str(e)}), 500
        
    def update_tenant(self,tenant_id):
        try:
            # --- Fetch tenant that belongs to the logged-in user ---
            tenant = Tenant.query.filter_by(id=tenant_id, user_id=self.user_id).first()
            if not tenant:
                return jsonify({"message": "Tenant not found or not authorized"}), 404

            # --- Update fields if provided ---
            if "tenant_name" in self.data and self.data.get("tenant_name"):
                tenant.name = self.data.get("tenant_name")
            
            if "email" in self.data:
                email = self.data.get("email")
                if email and not match(r"^[\w\.-]+@[\w\.-]+\.\w+$", email):
                    return jsonify({"message": "Invalid email format"}), 400
                tenant.email = email

            if "phone_number" in self.data:
                phone_number = self.data.get("phone_number")
                if phone_number and not match(r"^(?:\+91|0)?[6-9]\d{9}$", phone_number):
                    return jsonify({"message": "Invalid phone number format"}), 400
                tenant.phone_number = phone_number

            if "address" in self.data:
                tenant.address = self.data.get("address")

            # --- Commit changes ---
            db.session.commit()
            return jsonify({"message": "Tenant updated successfully"}), 200

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating tenant: {e}")
            return jsonify({"message": "Failed to update tenant", "details": str(e)}), 500
        
    def delete_tenant(self, tenant_id):
        try:
            # --- Fetch tenant that belongs to the logged-in user ---
            tenant = Tenant.query.filter_by(id=tenant_id, user_id=self.user_id).first()
            if not tenant:
                return jsonify({"message": "Tenant not found or not authorized"}), 404

            # --- Delete tenant ---
            db.session.delete(tenant)
            db.session.commit()

            return jsonify({"message": "Tenant deleted successfully"}), 200

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error deleting tenant: {e}")
            return jsonify({"message": "Failed to delete tenant", "details": str(e)}), 500
        
    def get_all_tenants(self):
        try:
            # --- Query params ---
            page = int(request.args.get("page", 1))       # default page = 1
            per_page = int(request.args.get("per_page", 10))  # default 10 tenants per page
            search = request.args.get("search", "").strip()

            # --- Base query ---
            query = Tenant.query.filter_by(user_id=self.user_id)

            # --- Apply search filter if provided ---
            if search:
                like_pattern = f"%{search}%"
                query = query.filter(
                    (Tenant.name.ilike(like_pattern)) |
                    (Tenant.email.ilike(like_pattern)) |
                    (Tenant.phone_number.ilike(like_pattern))
                )

            # --- Paginate results ---
            pagination = query.order_by(Tenant.created_date.desc()).paginate(page=page, per_page=per_page, error_out=False)
            tenants = pagination.items

            # --- Convert to list of dicts ---
            tenant_list = [
                {
                    "id": t.id,
                    "name": t.name,
                    "email": t.email,
                    "phone_number": t.phone_number,
                    "address": t.address,
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

        except Exception as e:
            current_app.logger.error(f"Error fetching tenants: {e}")
            return jsonify({"message": "Failed to fetch tenants", "details": str(e)}), 500
        
    def get_tenant_detail(self, tenant_id):
        try:
            tenant = Tenant.query.filter_by(id=tenant_id, user_id=self.user_id).first()
            if not tenant:
                return jsonify({"message": "Tenant not found"}), 404

            # Get active lease (or first lease if multiple)
            lease = Lease.query.filter_by(tenant_id=tenant.id, status="active").first()
            rent_amount = None
            start_date = None
            end_date = None

            if lease:
                start_date = lease.lease_start_date
                end_date = lease.lease_end_date

                # Get property to fetch monthly rent
                property_obj = Property.query.get(lease.property_id)
                if property_obj:
                    rent_amount = property_obj.monthly_rent

            return jsonify({
                "id": tenant.id,
                "name": tenant.name,
                "email": tenant.email,
                "phone_number": tenant.phone_number,
                "address": tenant.address,
                "rent_amount": rent_amount,
                "start_date": start_date.isoformat() if start_date else None,
                "end_date": end_date.isoformat() if end_date else None
            }), 200

        except Exception as e:
            current_app.logger.error(f"Error fetching tenant details: {e}")
            return jsonify({"message": "Error fetching tenant details", "error": str(e)}), 500
            
class PropertyController:

    def __init__(self):
        self.data = request.get_json(silent=True) or request.form
        self.user_id = get_jwt_identity()

    def add_property(self):
        try:
            # --- Required fields ---
            required_fields = ["title", "address", "monthly_rent"]
            missing = [f for f in required_fields if not self.data.get(f)]
            if missing:
                return jsonify({"message": f"Missing required fields: {', '.join(missing)}"}), 400

            # --- Create property instance ---
            new_property = Property(
                owner_id=self.user_id,
                title=self.data.get("title"),
                address=self.data.get("address"),
                monthly_rent=float(self.data.get("monthly_rent")),
                deposit_amount=float(self.data.get("deposit_amount", 0.0))  # optional
            )

            db.session.add(new_property)
            db.session.commit()

            return jsonify({
                "message": "Property added successfully",
                "property": {
                    "id": new_property.id,
                    "title": new_property.title,
                    "address": new_property.address,
                    "monthly_rent": new_property.monthly_rent,
                    "deposit_amount": new_property.deposit_amount
                }
            }), 201

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error adding property: {e}")
            return jsonify({"error": "Failed to add property", "details": str(e)}), 500
        
    def update_property(self, property_id):
        try:
            if not self.user_id:
                return jsonify({"message": "Unauthorized"}), 401

            # Fetch the property owned by the logged-in user
            property_obj = Property.query.filter_by(id=property_id, owner_id=self.user_id).first()
            if not property_obj:
                return jsonify({"message": "Property not found"}), 404

            # Update only valid fields from the model
            allowed_fields = ["title", "address", "monthly_rent", "deposit_amount"]
            for field in allowed_fields:
                if field in self.data:
                    setattr(property_obj, field, self.data[field])

            db.session.commit()
            return jsonify({"message": "Property updated successfully"}), 200

        except Exception as e:
            db.session.rollback()
            return jsonify({"message": "Error updating property", "error": str(e)}), 500
        
    def delete_property(self, property_id):
        try:
            # --- Find property by ID ---
            prop = Property.query.filter_by(id=property_id, owner_id=self.user_id).first()
            if not prop:
                return jsonify({"message": "Property not found or not authorized"}), 404

            # --- Delete property ---
            db.session.delete(prop)
            db.session.commit()

            return jsonify({"message": "Property deleted successfully"}), 200

        except Exception as e:
            current_app.logger.error(f"Error deleting property: {str(e)}")
            return jsonify({"message": "Failed to delete property"}), 500
        
    def get_all_properties(self):
        try:
            # --- Query params ---
            page = int(request.args.get("page", 1))        # default page = 1
            per_page = int(request.args.get("per_page", 10))  # default 10 properties per page
            search = request.args.get("search", "").strip()

            # --- Base query ---
            query = Property.query.filter_by(owner_id=self.user_id)

            # --- Apply search filter if provided ---
            if search:
                like_pattern = f"%{search}%"
                query = query.filter(
                    (Property.title.ilike(like_pattern)) |
                    (Property.address.ilike(like_pattern))
                )

            # --- Paginate results ---
            pagination = query.order_by(Property.created_date.desc()).paginate(page=page, per_page=per_page, error_out=False)
            properties = pagination.items

            # --- Convert to list of dicts ---
            property_list = [
                {
                    "id": p.id,
                    "title": p.title,
                    "address": p.address,
                    "monthly_rent": p.monthly_rent,
                    "deposit_amount": p.deposit_amount,
                    "created_date": p.created_date.isoformat() if p.created_date else None,
                    "updated_date": p.updated_date.isoformat() if p.updated_date else None
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
            current_app.logger.error(f"Error fetching properties: {e}")
            return jsonify({"message": "Failed to fetch properties", "details": str(e)}), 500

        
    def get_property_detail(self, property_id): 
        try:
            property_obj = Property.query.filter_by(id=property_id, owner_id=self.user_id).first()
            if not property_obj:
                current_app.logger.warning(f"Property ID {property_id} not found for user {self.user_id}")
                return jsonify({"error": "Property not found"}), 404

            result = {
                "id": property_obj.id,
                "owner_id": property_obj.owner_id,
                "owner_name": property_obj.owner.username,  # <-- now you can directly access this
                "title": property_obj.title,
                "address": property_obj.address,
                "monthly_rent": property_obj.monthly_rent,
                "deposit_amount": property_obj.deposit_amount
            }
            return jsonify(result), 200

        except Exception as e:
            current_app.logger.error(f"Failed to fetch property ID {property_id}: {e}")
            return jsonify({"error": "Internal server error"}), 500


class LeaseController:

    def __init__(self):
        self.data = request.get_json(silent=True) or request.form
        self.user_id = get_jwt_identity()

    def add_lease(self):
        if not self.user_id:
            return jsonify({"message": "Unauthorized: No user ID found"}), 401

        try:
            # --- Extract fields ---
            tenant_id = self.data.get("tenant_id")
            property_id = self.data.get("property_id")
            lease_start_date_str = self.data.get("lease_start_date")
            lease_end_date_str = self.data.get("lease_end_date")
            status = self.data.get("status", "active")

            # --- Validate required fields ---
            if not all([tenant_id, property_id, lease_start_date_str]):
                return jsonify({"message": "tenant_id, property_id, and lease_start_date are required"}), 400

            # --- Convert dates ---
            try:
                lease_start_date = datetime.strptime(lease_start_date_str, "%Y-%m-%d").date()
                lease_end_date = datetime.strptime(lease_end_date_str, "%Y-%m-%d").date() if lease_end_date_str else None
            except ValueError:
                return jsonify({"message": "Invalid date format. Use YYYY-MM-DD"}), 400

            # --- Auto-generate due_day from lease_start_date ---
            due_day = lease_start_date.day

            # --- Verify tenant belongs to current user ---
            tenant = Tenant.query.filter_by(id=tenant_id, user_id=self.user_id).first()
            if not tenant:
                return jsonify({"message": "Tenant not found or not owned by user"}), 404

            # --- Verify property belongs to current user ---
            prop = Property.query.filter_by(id=property_id, owner_id=self.user_id).first()
            if not prop:
                return jsonify({"message": "Property not found or not owned by user"}), 404

            # --- Create lease ---
            lease = Lease(
                tenant_id=tenant_id,
                property_id=property_id,
                lease_start_date=lease_start_date,
                lease_end_date=lease_end_date,
                due_day=due_day,
                status=status,
                created_by=str(self.user_id),
                updated_by=str(self.user_id)
            )

            db.session.add(lease)
            db.session.commit()  # commit to get lease.id

            # --- Generate RentReminders automatically ---
            RentReminderController.generate_rent_reminders(lease, months_ahead=12)  # generate 12 months by default

            return jsonify({
                "message": "Lease added successfully",
                "lease_id": lease.id,
                "due_day": lease.due_day
            }), 201

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error adding lease: {e}")
            return jsonify({"message": "Failed to add lease", "details": str(e)}), 500


        
    def update_lease(self, lease_id):
        try:
            # Find lease and ensure property belongs to logged-in user
            lease = (
                db.session.query(Lease)
                .join(Property, Lease.property_id == Property.id)
                .filter(Lease.id == lease_id, Property.owner_id == self.user_id)
                .first()
            )

            if not lease:
                return jsonify({"message": "Lease not found or unauthorized"}), 404

            # --- Update lease_start_date ---
            if "lease_start_date" in self.data and self.data["lease_start_date"]:
                try:
                    lease.lease_start_date = datetime.strptime(
                        self.data["lease_start_date"], "%Y-%m-%d"
                    ).date()
                    # Auto-update due_day
                    lease.due_day = lease.lease_start_date.day

                    # Regenerate future rent reminders
                    RentReminderController.generate_rent_reminders(lease, months_ahead=12)
                except ValueError:
                    return jsonify({"message": "Invalid lease_start_date format. Use YYYY-MM-DD"}), 400

            # --- Update lease_end_date ---
            if "lease_end_date" in self.data:
                lease_end_str = self.data["lease_end_date"]
                if lease_end_str:
                    try:
                        lease.lease_end_date = datetime.strptime(lease_end_str, "%Y-%m-%d").date()
                    except ValueError:
                        return jsonify({"message": "Invalid lease_end_date format. Use YYYY-MM-DD"}), 400

            # --- Validate lease_end_date after lease_start_date ---
            if lease.lease_end_date and lease.lease_end_date < lease.lease_start_date:
                return jsonify({"message": "lease_end_date cannot be before lease_start_date"}), 400

            # --- Update status ---
            if "status" in self.data and self.data["status"] in ["active", "ended"]:
                lease.status = self.data["status"]

            db.session.commit()
            return jsonify({"message": "Lease updated successfully", "due_day": lease.due_day}), 200

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating lease: {e}")
            return jsonify({"message": "Failed to update lease", "details": str(e)}), 500


    def delete_lease(self, lease_id):
        try:

            lease = (
                db.session.query(Lease)
                .join(Property, Lease.property_id == Property.id)
                .filter(Lease.id == lease_id, Property.owner_id == self.user_id)
                .first()
            )

            if not lease:
                return jsonify({"message": "Lease not found or unauthorized"}), 404

            db.session.delete(lease)
            db.session.commit()

            return jsonify({"message": "Lease deleted successfully"}), 200

        except Exception as e:
            db.session.rollback()
            return jsonify({"message": "Error deleting lease", "error": str(e)}), 500
        
    def get_all_leases(self):
        try:
            if not self.user_id:
                return {"message": "Unauthorized"}, 401

            # Fetch leases with tenant and property relationships
            leases = (
                Lease.query
                .join(Tenant)
                .join(Property)
                .filter(Tenant.user_id == self.user_id, Lease.status == "active")
                .all()
            )

            if not leases:
                return {"message": "No active leases found"}, 404

            # Convert Lease objects to dictionaries
            lease_list = []
            for lease in leases:
                lease_data = {
                    "id": lease.id,
                    "tenant_id": lease.tenant_id,
                    "tenant_name": lease.tenant.name if lease.tenant else None,
                    "property_id": lease.property_id,
                    "property_name": lease.property.title if lease.property else None,
                    "lease_start_date": lease.lease_start_date.strftime("%d-%m-%Y") if lease.lease_start_date else None,
                    "lease_end_date": lease.lease_end_date.strftime("%d-%m-%Y") if lease.lease_end_date else None,
                    "due_day": lease.due_day,
                    "status": lease.status,
                }
                lease_list.append(lease_data)

            return {"leases": lease_list}, 200

        except Exception as e:
            current_app.logger.error(f"Error fetching leases for user {self.user_id}: {str(e)}")
            return {"message": "An error occurred while fetching leases"}, 500

        
    def get_lease_detail(self, lease_id):
        try:
            lease = (
                Lease.query
                .join(Tenant)
                .filter(Lease.id == lease_id, Tenant.user_id == self.user_id)
                .first()
            )
            if not lease:
                return {"message": "Lease not found"}, 404

            # Manually serialize the lease object
            lease_data = {
                "id": lease.id,
                "tenant_id": lease.tenant_id,
                "tenant_name": lease.tenant.name if lease.tenant else None,
                "property_id": lease.property_id,
                "property_name": lease.property.title if lease.property else None,
                "lease_start_date": lease.lease_start_date.strftime("%d-%m-%Y") if lease.lease_start_date else None,
                "lease_end_date": lease.lease_end_date.strftime("%d-%m-%Y") if lease.lease_end_date else None,
                "due_day": lease.due_day,
                "status": lease.status,
                "created_by": lease.created_by,
                "updated_by": lease.updated_by,
            }

            return {"lease": lease_data}, 200

        except Exception as e:
            current_app.logger.error(f"Error fetching lease {lease_id}: {e}")
            return {"message": "Internal server error"}, 500


class RentPaymentController:

    def __init__(self):
        self.data = request.get_json(silent=True) or request.form
        self.user_id = get_jwt_identity()

    def add_payment(self):
        try:
            tenant_id = self.data.get("tenant_id")
            property_id = self.data.get("property_id")
            amount = self.data.get("amount")
            payment_mode = self.data.get("payment_mode", "Cash")
            status = self.data.get("status", "paid")
            transaction_reference = self.data.get("transaction_reference")

            # Validate required fields
            if not all([tenant_id, property_id, amount]):
                return jsonify({"message": "tenant_id, property_id, and amount are required"}), 400

            # Verify ownership
            tenant = Tenant.query.filter_by(id=tenant_id, user_id=self.user_id).first()
            if not tenant:
                return jsonify({"message": "Tenant not found or unauthorized"}), 404

            prop = Property.query.filter_by(id=property_id, owner_id=self.user_id).first()
            if not prop:
                return jsonify({"message": "Property not found or unauthorized"}), 404

            # Get active lease for due_day
            lease = Lease.query.filter_by(
                tenant_id=tenant_id, property_id=property_id, status="active"
            ).first()
            due_day = lease.due_day if lease else 1

            # Current month range
            today = date.today()
            start_date = date(today.year, today.month, 1)
            end_date = date(today.year, today.month, monthrange(today.year, today.month)[1])

            # Check if payment exists
            existing_payment = RentPayment.query.filter(
                RentPayment.tenant_id == tenant_id,
                RentPayment.property_id == property_id,
                RentPayment.payment_date >= start_date,
                RentPayment.payment_date <= end_date
            ).first()

            # Auto mark late if unpaid after due
            rent_due_date = date(today.year, today.month, min(due_day, end_date.day))
            if status != "paid" and today > rent_due_date:
                status = "late"

            if existing_payment:
                existing_payment.amount = amount
                existing_payment.payment_mode = payment_mode
                existing_payment.transaction_reference = transaction_reference
                existing_payment.status = status
                existing_payment.updated_date = datetime.utcnow()
                db.session.commit()
                return jsonify({"message": "Payment updated successfully", "payment_id": existing_payment.id}), 200

            new_payment = RentPayment(
                tenant_id=tenant_id,
                property_id=property_id,
                amount=amount,
                payment_date=today,
                payment_mode=payment_mode,
                status=status,
                transaction_reference=transaction_reference
            )
            db.session.add(new_payment)
            db.session.commit()
            return jsonify({"message": "Payment recorded successfully", "payment_id": new_payment.id}), 201

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error adding/updating payment: {e}", exc_info=True)
            return jsonify({"message": "Failed to add or update payment", "details": str(e)}), 500

    def get_payments(self):
        try:
            payments = (
                RentPayment.query
                .join(Tenant)
                .filter(Tenant.user_id == self.user_id)
                .order_by(RentPayment.payment_date.desc())
                .all()
            )

            result = []
            for p in payments:
                result.append({
                    "id": p.id,
                    "tenant_id": p.tenant_id,
                    "tenant_name": p.tenant.name,
                    "property_id": p.property_id,
                    "property_title": p.property.title,
                    "amount": p.amount,
                    "payment_date": p.payment_date.isoformat() if p.payment_date else None,
                    "payment_mode": p.payment_mode,
                    "status": p.status,
                    "transaction_reference": p.transaction_reference
                })

            return jsonify(result), 200

        except Exception as e:
            current_app.logger.error(f"Error fetching payments: {e}", exc_info=True)
            return jsonify({"message": "Failed to fetch payments", "details": str(e)}), 500
        

    def get_payment_detail(self, payment_id):
        try:
            payment = (
                RentPayment.query
                .join(Tenant)
                .filter(RentPayment.id == payment_id, Tenant.user_id == self.user_id)
                .first()
            )

            if not payment:
                return jsonify({"message": "Payment not found"}), 404

            result = {
                "id": payment.id,
                "tenant_id": payment.tenant_id,
                "tenant_name": payment.tenant.name,
                "property_id": payment.property_id,
                "property_title": payment.property.title,
                "amount": payment.amount,
                "payment_date": payment.payment_date.isoformat() if payment.payment_date else None,
                "payment_mode": payment.payment_mode,
                "status": payment.status,
                "transaction_reference": payment.transaction_reference
            }

            return jsonify(result), 200

        except Exception as e:
            current_app.logger.error(f"Error fetching payment detail: {e}", exc_info=True)
            return jsonify({"message": "Failed to fetch payment detail", "details": str(e)}), 500


    def get_payments_by_tenant(self, tenant_id):
        try:
            # Verify tenant belongs to the current user
            tenant = Tenant.query.filter_by(id=tenant_id, user_id=self.user_id).first()
            if not tenant:
                return jsonify({"message": "Tenant not found or unauthorized"}), 404

            # Fetch payments
            payments = tenant.payments
            result = []
            for p in payments:
                result.append({
                    "id": p.id,
                    "property_id": p.property_id,
                    "property_title": p.property.title if p.property else None,
                    "amount": p.amount,
                    "payment_date": p.payment_date.isoformat() if p.payment_date else None,
                    "payment_mode": p.payment_mode,
                    "status": p.status,
                    "transaction_reference": p.transaction_reference
                })

            return jsonify(result), 200

        except Exception as e:
            current_app.logger.error(f"Error fetching payments for tenant {tenant_id}: {e}", exc_info=True)
            return jsonify({"message": "Failed to fetch payments", "details": str(e)}), 500

        
    def get_payments_by_property(self, property_id):
        try:

            # Verify property belongs to current user
            prop = Property.query.filter_by(id=property_id, owner_id=self.user_id).first()
            if not prop:
                return jsonify({"message": "Property not found or unauthorized"}), 404

            # Fetch payments for this property
            payments = RentPayment.query.filter_by(property_id=property_id).order_by(RentPayment.payment_date.desc()).all()
            if not payments:
                return jsonify({"message": "No payments found for this property"}), 404

            result = []
            for p in payments:
                result.append({
                    "id": p.id,
                    "tenant_id": p.tenant_id,
                    "tenant_name": p.tenant.name if p.tenant else None,
                    "amount": p.amount,
                    "payment_date": p.payment_date.isoformat() if p.payment_date else None,
                    "payment_mode": p.payment_mode,
                    "status": p.status,
                    "transaction_reference": p.transaction_reference
                })

            return jsonify(result), 200

        except Exception as e:
            current_app.logger.error(f"Error fetching payments for property {property_id}: {e}", exc_info=True)
            return jsonify({"message": "Failed to fetch property payments", "details": str(e)}), 500
        
class RentReminderController:

    def __init__(self):
        self.data = request.get_json(silent=True) or request.form
        self.user_id = get_jwt_identity()

    @staticmethod
    def generate_rent_reminders(lease: Lease, months_ahead: int = 12):
        """
        Generate rent reminders for the given lease up to `months_ahead`.
        Skips past dates and avoids duplicates.
        """
        reminders_created = 0
        today = date.today()
        start_date = max(today, lease.lease_start_date)
        start_year, start_month = start_date.year, start_date.month

        # Fetch existing due_dates for this lease in one query
        existing_dates = {
            r.due_date for r in RentReminder.query.filter_by(lease_id=lease.id).all()
        }

        new_reminders = []

        for i in range(months_ahead):
            month = (start_month + i - 1) % 12 + 1
            year = start_year + ((start_month + i - 1) // 12)

            last_day = monthrange(year, month)[1]
            due_day = min(lease.due_day, last_day)
            due_date = date(year, month, due_day)

            if due_date < today:  # Skip past dates
                continue

            if due_date not in existing_dates:  # Avoid duplicates
                reminder = RentReminder(
                    lease_id=lease.id,
                    due_date=due_date,
                    reminder_sent=False
                )
                db.session.add(reminder)
                new_reminders.append(reminder)
                reminders_created += 1

        if reminders_created > 0:
            db.session.commit()

        return {
            "created_count": reminders_created,
            "new_reminders": [r.due_date.isoformat() for r in new_reminders]
        }

    def get_reminders(self):
        try:
            reminders = (
                RentReminder.query
                .join(Lease, RentReminder.lease_id == Lease.id)   # Join via lease
                .join(Tenant, Lease.tenant_id == Tenant.id)       # Join tenant
                .join(Property, Lease.property_id == Property.id) # Join property
                .filter(Tenant.user_id == self.user_id)
                .order_by(RentReminder.due_date.desc())
                .all()
            )

            result = []
            for r in reminders:
                result.append({
                    "id": r.id,
                    "tenant_id": r.lease.tenant.id,
                    "tenant_name": r.lease.tenant.name,
                    "property_id": r.lease.property.id,
                    "property_title": r.lease.property.title if r.lease.property else None,
                    "due_date": r.due_date.isoformat() if r.due_date else None,
                    "reminder_sent": r.reminder_sent,
                    "last_sent_date": r.last_sent_date.isoformat() if r.last_sent_date else None
                })

            return jsonify(result), 200

        except Exception as e:
            current_app.logger.error(f"Error fetching reminders: {e}", exc_info=True)
            return jsonify({"message": "Failed to fetch reminders", "details": str(e)}), 500


    def get_upcoming_reminders(self):
        try:
            from datetime import date
            today = date.today()

            reminders = (
                RentReminder.query
                .join(Lease, RentReminder.lease_id == Lease.id)
                .join(Tenant, Lease.tenant_id == Tenant.id)
                .join(Property, Lease.property_id == Property.id)
                .filter(
                    Tenant.user_id == self.user_id,
                    RentReminder.due_date >= today
                )
                .order_by(RentReminder.due_date.asc())
                .all()
            )

            result = []
            for r in reminders:
                result.append({
                    "id": r.id,
                    "tenant_id": r.lease.tenant.id,
                    "tenant_name": r.lease.tenant.name,
                    "property_id": r.lease.property.id,
                    "property_title": r.lease.property.title if r.lease.property else None,
                    "due_date": r.due_date.isoformat() if r.due_date else None,
                    "reminder_sent": r.reminder_sent,
                    "last_sent_date": r.last_sent_date.isoformat() if r.last_sent_date else None
                })

            return jsonify(result), 200

        except Exception as e:
            current_app.logger.error(f"Error fetching upcoming reminders: {e}", exc_info=True)
            return jsonify({"message": "Failed to fetch upcoming reminders", "details": str(e)}), 500
    
# class NotificationController:

#     def get_notifications():
#         try:
#             user_id = get_jwt_identity()
#             notifications = NotificationLog.query.join(Tenant).filter(Tenant.user_id == user_id).order_by(NotificationLog.created_date.desc()).all()

#             result = []
#             for n in notifications:
#                 result.append({
#                     "id": n.id,
#                     "tenant_id": n.tenant_id,
#                     "tenant_name": n.tenant.name,
#                     "message": n.message,
#                     "notification_type": n.notification_type,
#                     "status": n.status,
#                     "created_date": n.created_date.isoformat() if n.created_date else None
#                 })

#             return jsonify(result), 200

#         except Exception as e:
#             current_app.logger.error(f"Error fetching notifications: {e}", exc_info=True)
#             return jsonify({"message": "Failed to fetch notifications", "details": str(e)}), 500


#     def get_notifications_by_tenant(tenant_id):
#         try:
#             user_id = get_jwt_identity()
#             tenant = Tenant.query.filter_by(id=tenant_id, user_id=user_id).first()
#             if not tenant:
#                 return jsonify({"message": "Tenant not found or unauthorized"}), 404

#             notifications = tenant.notifications.order_by(NotificationLog.created_date.desc()).all()

#             result = []
#             for n in notifications:
#                 result.append({
#                     "id": n.id,
#                     "tenant_id": n.tenant_id,
#                     "tenant_name": n.tenant.name,
#                     "message": n.message,
#                     "notification_type": n.notification_type,
#                     "status": n.status,
#                     "created_date": n.created_date.isoformat() if n.created_date else None
#                 })

#             return jsonify(result), 200

#         except Exception as e:
#             current_app.logger.error(f"Error fetching notifications for tenant {tenant_id}: {e}", exc_info=True)
#             return jsonify({"message": "Failed to fetch notifications", "details": str(e)}), 500
