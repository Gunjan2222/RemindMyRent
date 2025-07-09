from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_mail import Mail
from flask_login import LoginManager   # ✅ added
from celery import Celery
from app.config import Config

db = SQLAlchemy()
mail = Mail()
migrate = Migrate()
login_manager = LoginManager()        # ✅ added
celery = Celery(__name__, broker=Config.broker_url)

def create_app():
    app = Flask(__name__)
    app.secret_key = 'your_secret_key'
    app.config.from_object(Config)

    db.init_app(app)
    mail.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)       # ✅ initialize LoginManager

    login_manager.login_view = "api.login"  # ✅ set login view (update if your route endpoint name is different)

    from app.models import User       # ✅ import your User model

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    from app.routes import api
    app.register_blueprint(api)

    celery.conf.update(app.config)

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask

    return app
