from flask import Blueprint, jsonify, current_app
from app import db
from flask_jwt_extended import jwt_required, get_jwt_identity, create_access_token, get_jwt
# from app.tasks import send_rent_notifications_task, test_celery_task
from app.utils.controller import AuthController, TenantController, PropertyController, PaymentController, DashboardController

api = Blueprint("api", __name__)

# ---------------------
# Authentication Routes
# ---------------------

@api.route("/")
def health():
    db.create_all()
    return jsonify({"status": "ok", "message": "Rent Management API running"}), 200

    

# @api.route('/test-celery', methods=['GET'])
# def test_celery():
#     """
#     Manually trigger a test Celery task to verify worker and Redis connection.
#     """
#     task = test_celery_task.delay()
#     return jsonify({
#         "message": "Celery test task triggered!",
#         "task_id": task.id
#     }), 202

@api.route("/register", methods=["POST"])
def register():
        auth = AuthController()
        response = auth.register()
        return response  # Assuming registration creates a user


@api.route("/login", methods=["POST"])
def login():
        auth = AuthController()
        response = auth.login()
        return response


@api.route("/refresh-token", methods=["POST"])
@jwt_required(refresh=True)
def refresh_token():
    try:
        identity = get_jwt_identity()
        claims = get_jwt()

        token = create_access_token(
            identity=identity,
            additional_claims={
                "username": claims["username"],
                "email": claims["email"],
                "role": claims["role"]
            }
        )
        return jsonify({"status": "success", "access_token": token}), 200
    except Exception as e:
        current_app.logger.error(f"Token refresh error: {e}")
        return jsonify({"status": "error", "message": "Token refresh failed", "details": str(e)}), 500


@api.route("/logout", methods=["POST"])
@jwt_required()
def logout():
        auth = AuthController()
        response = auth.logout()
        return response


# ---------------------
# Password Reset Routes
# ---------------------

@api.route("/forgot-password", methods=["POST"])
def forgot_password():
        auth = AuthController()
        return auth.forgot_password()


@api.route("/reset-password/<token>", methods=["POST"])
def reset_password(token):
        auth = AuthController()
        return auth.reset_password(token)

# ---------------------
# Tenant Routes
# ---------------------

@api.route("/add-tenant", methods=["POST"])
@jwt_required()
def add_tenant():
        tenants = TenantController()
        addTenant = tenants.add_tenant()
        return addTenant


@api.route("/update-tenant/<uuid:tenant_id>", methods=["PUT"])
@jwt_required()
def update_tenant(tenant_id):
        tenants = TenantController()
        updateTenant = tenants.update_tenant(tenant_id)
        return updateTenant


@api.route("/delete-tenant/<uuid:tenant_id>", methods=["DELETE"])
@jwt_required()
def delete_tenant(tenant_id):
        tenants = TenantController()
        deleteTenant = tenants.delete_tenant(tenant_id)
        return deleteTenant
    
@api.route("/tenants", methods=["GET"])
@jwt_required()
def get_tenants():
        tenants = TenantController()
        getTenants = tenants.get_all_tenants()
        return getTenants


@api.route("/tenant-detail/<uuid:tenant_id>", methods=["GET"])
@jwt_required()
def tenant_detail(tenant_id):
    return TenantController().get_tenant_detail(tenant_id)
    
# ---------------------
# Property Routes
# ---------------------

@api.route("/add-property", methods=["POST"])
@jwt_required()
def add_property():
        properties = PropertyController()
        addProperty = properties.add_property()
        return addProperty
    
@api.route("/update-property/<uuid:property_id>", methods=["PUT"])
@jwt_required()
def update_property(property_id):
        properties = PropertyController()
        updateProperty = properties.update_property(property_id)
        return updateProperty

@api.route("/delete-property/<uuid:property_id>", methods=["DELETE"])
@jwt_required()
def delete_property(property_id):
        properties = PropertyController()
        deleteProperty = properties.delete_property(property_id)
        return deleteProperty
    
@api.route("/properties", methods=["GET"])
@jwt_required()
def get_properties():
        properties = PropertyController()
        result = properties.get_all_properties()
        return result
    
@api.route('/property-detail/<uuid:property_id>', methods=['GET'])
@jwt_required()
def property_detail(property_id):
        properties = PropertyController()
        property_data = properties.get_property_detail(property_id)
        return property_data


# @api.route("/profile", methods=["GET", "PUT"])
# @jwt_required()
# def profile():
#     try:
#         con = ProfileController()
#         if request.method == "GET":
#             response = con.get_profile()
#         elif request.method == "PUT":
#             response = con.update_profile()
#         return response
#     except Exception as e:
#         current_app.logger.error(f"Error in profile: {str(e)}")
#         return jsonify({"message": "Internal server error while fetching profile"}), 500
    
@api.route("/change-password", methods=['POST'])
@jwt_required()
def change_pass():
        con = AuthController()
        response = con.change_password()
        return response
    

@api.route("/pending/summary", methods=["GET"])
@jwt_required()
def pending_summary():
        controller = PaymentController()
        response = controller.get_pending_summary()
        return response
    

@api.route("/tenant-payments/<uuid:tenant_id>", methods=["GET"])
@jwt_required()
def tenant_payments(tenant_id):
        controller = PaymentController()
        return controller.get_tenant_payments(tenant_id)
    

@api.route("/payments/<uuid:payment_id>/pay", methods=["POST"])
@jwt_required()
def mark_payment_paid(payment_id):
        controller = PaymentController()
        return controller.mark_payment_paid(payment_id)
    

@api.route("/summary", methods=["GET"])
@jwt_required()
def dashboard_summary():
        controller = DashboardController()
        return controller.get_dashboard_summary()
    

@api.route("/overdue", methods=["GET"])
@jwt_required()
def overdue_payments():
        controller = DashboardController()
        return controller.get_overdue_payments()
    

@api.route("/payments", methods=["GET"])
@jwt_required()
def monthly_payments():
        controller = DashboardController()
        return controller.get_monthly_payments()




