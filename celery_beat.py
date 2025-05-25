from app import celery, create_app
import app.scheduler  # Ensure beat schedule is loaded

app = create_app()
app.app_context().push()
