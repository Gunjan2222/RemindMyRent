from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_mail import Mail
from flask_jwt_extended import JWTManager
from celery import Celery
from flask_cors import CORS 

from app.config import Config
from app.utils.token_blacklist import TokenBlacklist

# Initialize Flask extensions
db = SQLAlchemy()
mail = Mail()
migrate = Migrate()
jwt = JWTManager()
celery = Celery(__name__, broker=Config.broker_url, backend=Config.result_backend)

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    CORS(app, resources={r"/*": {"origins": "*"}})

    # Initialize extensions with app
    db.init_app(app)
    mail.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)

    @jwt.token_in_blocklist_loader
    def check_if_token_revoked(jwt_header, jwt_payload):
        jti = jwt_payload["jti"]
        blacklist = TokenBlacklist()
        return blacklist.is_blacklisted(jti)

    @jwt.revoked_token_loader
    def revoked_token_callback(jwt_header, jwt_payload):
        return jsonify({"msg": "Token has been revoked"}), 401

    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return jsonify({"msg": "Token has expired"}), 401

    @jwt.invalid_token_loader
    def invalid_token_callback(reason):
        return jsonify({"msg": f"Invalid token: {reason}"}), 422

    @jwt.unauthorized_loader
    def missing_token_callback(reason):
        return jsonify({"msg": f"Missing token: {reason}"}), 401
    # --- End JWT Setup ---

    # Register blueprints
    from app.routes import api
    app.register_blueprint(api)

    # Celery context integration
    celery.conf.update(app.config)

    class FlaskTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = FlaskTask

    return app
