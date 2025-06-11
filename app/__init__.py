from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_mail import Mail
from celery import Celery
from app.config import Config

db = SQLAlchemy()
mail = Mail()
migrate = Migrate()
celery = Celery(__name__, broker=Config.broker_url)

def create_app():
    app = Flask(__name__)
    app.secret_key = 'your_secret_key'
    app.config.from_object(Config)

    db.init_app(app)
    mail.init_app(app)
    migrate.init_app(app, db)

    from app.routes import api
    app.register_blueprint(api)

    celery.conf.update(app.config)

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask

    return app
