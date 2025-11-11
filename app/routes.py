from flask import Blueprint, request, jsonify, url_for, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity, create_access_token, get_jwt
from app import db, mail
from app.config import Config
from app.tasks import send_rent_notifications_task, test_celery_task
from app.utils.controller import AuthController, TenantController, PropertyController, LeaseController, RentPaymentController, RentReminderController, ProfileController

api = Blueprint("api", __name__)

# ---------------------
# Authentication Routes
# ---------------------

@api.route("/")
def health():
    return jsonify({"status": "ok", "message": "Rent Management API running"}), 200

@api.route('/test-celery', methods=['GET'])
def test_celery():
    """
    Manually trigger a test Celery task to verify worker and Redis connection.
    """
    task = test_celery_task.delay()
    return jsonify({
        "message": "Celery test task triggered!",
        "task_id": task.id
    }), 202

@api.route("/register", methods=["POST"])
def register():
    try:
        auth = AuthController()
        response = auth.register()
        return response  # Assuming registration creates a user
    except Exception as e:
        current_app.logger.error(f"Registration error: {e}")
        return jsonify({"status": "error", "message": "Registration failed", "details": str(e)}), 500


@api.route("/login", methods=["POST"])
def login():
    try:
        auth = AuthController()
        response = auth.login()
        return response
    except Exception as e:
        current_app.logger.error(f"Login error: {e}")
        return jsonify({"status": "error", "message": "Login failed", "details": str(e)}), 500


@api.route("/refresh-token", methods=["POST"])
@jwt_required(refresh=True)
def refresh_token():
    try:
        identity = get_jwt_identity()
        token = create_access_token(identity=identity)
        return jsonify({"status": "success", "access_token": token}), 200
    except Exception as e:
        current_app.logger.error(f"Token refresh error: {e}")
        return jsonify({"status": "error", "message": "Token refresh failed", "details": str(e)}), 500


@api.route("/logout", methods=["POST"])
@jwt_required()
def logout():
    try:
        auth = AuthController()
        response = auth.logout()
        return response
    except Exception as e:
        current_app.logger.error(f"Logout error: {e}")
        return jsonify({"status": "error", "message": "Logout failed", "details": str(e)}), 500


# ---------------------
# Password Reset Routes
# ---------------------

@api.route("/forgot-password", methods=["POST"])
def forgot_password():
    try:
        auth = AuthController()
        return auth.forgot_password()
    except Exception as e:
        current_app.logger.error(f"Error in forgot_password: {e}")
        return jsonify({"error": "Failed to process forgot password"}), 500


@api.route("/reset-password/<token>", methods=["POST"])
def reset_password(token):
    try:
        auth = AuthController()
        return auth.reset_password(token)
    except Exception as e:
        current_app.logger.error(f"Error in reset_password: {e}")
        return jsonify({"error": "Failed to reset password"}), 500

# ---------------------
# Tenant Routes
# ---------------------

@api.route("/add-tenant", methods=["POST"])
@jwt_required()
def add_tenant():
    try:
        tenants = TenantController()
        addTenant = tenants.add_tenant()
        return addTenant
    except Exception as e:
        current_app.logger.error(f"Error adding tenant: {e}")
        return jsonify({"error": "Failed to add tenant", "details": str(e)}), 500


@api.route("/update-tenant/<uuid:tenant_id>", methods=["PUT"])
@jwt_required()
def update_tenant(tenant_id):
    try:
        tenants = TenantController()
        updateTenant = tenants.update_tenant(tenant_id)
        return updateTenant
    except Exception as e:
        current_app.logger.error(f"Error updating tenant {tenant_id}: {e}")
        return jsonify({"error": "Failed to update tenant"}), 500


@api.route("/delete-tenant/<uuid:tenant_id>", methods=["DELETE"])
@jwt_required()
def delete_tenant(tenant_id):
    try:
        tenants = TenantController()
        deleteTenant = tenants.delete_tenant(tenant_id)
        return deleteTenant
    except Exception as e:
        current_app.logger.error(f"Error deleting tenant {tenant_id}: {e}")
        return jsonify({"error": "Failed to delete tenant"}), 500
    
@api.route("/tenants", methods=["GET"])
@jwt_required()
def get_tenants():
    try:
        tenants = TenantController()
        getTenants = tenants.get_all_tenants()
        return getTenants
    except Exception as e:
        current_app.logger.error(f"Error fetching tenants: {e}")
        return jsonify({"error": "Failed to fetch tenants"}), 500

@api.route('/tenant-detail/<uuid:tenant_id>', methods=['GET'])
@jwt_required()
def tenant_detail(tenant_id):
    try:
        tenants = TenantController()
        tenant_data = tenants.get_tenant_detail(tenant_id)

        # If tenant is not found
        if not tenant_data:
            return jsonify({"error": "Tenant not found"}), 404

        return tenant_data
    except Exception as e:
        current_app.logger.error(f"Error fetching tenant details: {e}")
        return jsonify({"error": "Failed to fetch tenant details"}), 500
    
# ---------------------
# Property Routes
# ---------------------

@api.route("/add-property", methods=["POST"])
@jwt_required()
def add_property():
    try:
        properties = PropertyController()
        addProperty = properties.add_property()
        return addProperty
    except Exception as e:
        current_app.logger.error(f"Error adding property: {e}")
        return jsonify({"error": "Failed to add property", "details": str(e)}), 500
    
@api.route("/update-property/<uuid:property_id>", methods=["PUT"])
@jwt_required()
def update_property(property_id):
    try:
        properties = PropertyController()
        updateProperty = properties.update_property(property_id)
        return updateProperty
    except Exception as e:
        current_app.logger.error(f"Error updating property {property_id}: {e}")
        return jsonify({"error": "Failed to update property"}), 500

@api.route("/delete-property/<uuid:property_id>", methods=["DELETE"])
@jwt_required()
def delete_property(property_id):
    try:
        properties = PropertyController()
        deleteProperty = properties.delete_property(property_id)
        return deleteProperty
    except Exception as e:
        current_app.logger.error(f"Error deleting property {property_id}: {e}")
        return jsonify({"error": "Failed to delete property"}), 500  
    
@api.route("/properties", methods=["GET"])
@jwt_required()
def get_properties():
    try:
        properties = PropertyController()
        result = properties.get_all_properties()
        return result
    except Exception as e:
        current_app.logger.error(f"Error fetching properties: {e}")
        return jsonify({"error": "Failed to fetch properties", "details": str(e)}), 500
    
@api.route('/property-detail/<uuid:property_id>', methods=['GET'])
@jwt_required()
def property_detail(property_id):
    try:
        properties = PropertyController()
        property_data = properties.get_property_detail(property_id)

        # If property is not found
        if not property_data:
            return jsonify({"error": "Property not found"}), 404

        return property_data
    except Exception as e:
        current_app.logger.error(f"Error fetching property details: {e}")
        return jsonify({"error": "Failed to fetch property details"}), 500

# ---------------------
# Lease Routes
# ---------------------

@api.route("/add-lease", methods=["POST"])
@jwt_required()
def create_lease():
    try:
        leases = LeaseController()
        result = leases.add_lease()
        return result
    except Exception as e:
        current_app.logger.error(f"Error creating lease: {e}", exc_info=True)
        return jsonify({"message": "Failed to create lease", "details": str(e)}), 500
    
@api.route("/update-lease/<uuid:lease_id>", methods=["PUT"])
@jwt_required()
def update_lease(lease_id):
    try:
        leases = LeaseController()
        result = leases.update_lease(lease_id)
        return result
    except Exception as e:
        current_app.logger.error(f"Error updating lease {lease_id}: {e}", exc_info=True)
        return jsonify({"message": "Failed to update lease", "details": str(e)}), 500
    
@api.route("/delete-lease/<uuid:lease_id>", methods=["DELETE"])
@jwt_required()
def delete_lease(lease_id):
    try:
        leases = LeaseController()
        result = leases.delete_lease(lease_id)
        return result
    except Exception as e:
        current_app.logger.error(f"Error deleting lease {lease_id}: {e}", exc_info=True)
        return jsonify({"message": "Failed to delete lease", "details": str(e)}), 500
    

@api.route("/leases", methods=["GET"])
@jwt_required()
def get_all_leases():
    try:
        leases = LeaseController()
        result = leases.get_all_leases()
        return result
    except Exception as e:
        current_app.logger.error(f"Error fetching all leases: {e}", exc_info=True)
        return jsonify({"message": "Internal server error"}), 500


@api.route("/lease-detail/<uuid:lease_id>", methods=["GET"])
@jwt_required()
def get_lease_detail(lease_id):
    try:
        leases = LeaseController()
        result = leases.get_lease_detail(lease_id)
        if not result:
            return jsonify({"message": "Lease not found"}), 404
        return result
    except Exception as e:
        current_app.logger.error(f"Error fetching lease detail for ID {lease_id}: {e}", exc_info=True)
        return jsonify({"message": "Internal server error"}), 500

# ---------------------
# Payments Routes
# ---------------------

@api.route("/add-payment", methods=["POST"])
@jwt_required()
def add_payment():
    try:
        payments = RentPaymentController()
        result = payments.add_payment()
        return result
    except Exception as e:
        current_app.logger.error(f"Error in add_payment: {str(e)}", exc_info=True)
        return jsonify({"message": "Failed to add payment", "details": str(e)}), 500


@api.route("/payments", methods=["GET"])
@jwt_required()
def get_payments():
    try:
        payments = RentPaymentController()
        result = payments.get_payments()
        return result
    except Exception as e:
        current_app.logger.error(f"Error in get_payments: {str(e)}", exc_info=True)
        return jsonify({"message": "Failed to fetch payments", "details": str(e)}), 500


@api.route("/payment-detail/<uuid:payment_id>", methods=["GET"])
@jwt_required()
def get_payment_detail(payment_id):
    try:
        payments = RentPaymentController()
        result = payments.get_payment_detail(payment_id)
        return result
    except Exception as e:
        current_app.logger.error(f"Error in get_payment_detail (ID: {payment_id}): {str(e)}", exc_info=True)
        return jsonify({"message": "Failed to fetch payment detail", "details": str(e)}), 500


# ---------------------
# Reminders Routes
# ---------------------


@api.route("/reminders", methods=["GET"])
@jwt_required()
def get_reminders():
    try:
        reminders = RentReminderController()
        result = reminders.get_reminders()
        return result
    except Exception as e:
        current_app.logger.error(f"Error in get_reminders: {str(e)}")
        return jsonify({"message": "Internal server error while fetching reminders"}), 500


@api.route("/reminders/upcoming", methods=["GET"])
@jwt_required()
def get_upcoming_reminders():
    try:
        reminders = RentReminderController()
        result = reminders.get_upcoming_reminders()
        return result
    except Exception as e:
        current_app.logger.error(f"Error in get_upcoming_reminders: {str(e)}")
        return jsonify({"message": "Internal server error while fetching upcoming reminders"}), 500


@api.route("/reminders/send-today", methods=["POST"])
@jwt_required()
def trigger_today_reminders():
    """Manually trigger rent reminder notifications for today."""
    try:
        task = send_rent_notifications_task.delay()
        return jsonify({"message": "Reminder task queued successfully", "task_id": task.id}), 202
    except Exception as e:
        current_app.logger.error(f"Error triggering reminder task: {e}", exc_info=True)
        return jsonify({"message": "Failed to trigger reminder task", "details": str(e)}), 500

@api.route("/dashboard/stats", methods=["GET"])
@jwt_required()
def stats():
    try:
        con = RentReminderController()
        response = con.get_dashboard_stats()
        return response
    except Exception as e:
        current_app.logger.error(f"Error fetching dashboard stats: {e}", exc_info=True)
        return jsonify({
            "message": "Internal server error while fetching dashboard stats",
            "details": str(e)
        }), 500

@api.route("/profile", methods=["GET", "PUT"])
@jwt_required()
def profile():
    try:
        con = ProfileController()
        if request.method == "GET":
            response = con.get_profile()
        elif request.method == "PUT":
            response = con.update_profile()
        return response
    except Exception as e:
        current_app.logger.error(f"Error in profile: {str(e)}")
        return jsonify({"message": "Internal server error while fetching profile"}), 500
    
@api.route("/change-password", methods=['POST'])
@jwt_required()
def change_pass():
    try:
        con = ProfileController()
        response = con.change_password()
        return response
    except Exception as e:
        current_app.logger.error(f"Error in change password: {str(e)}")
        return jsonify({"message": "Internal server error while changing password"}), 500
