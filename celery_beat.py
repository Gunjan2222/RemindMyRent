from app import celery, create_app
 # Ensure beat schedule is loaded

app = create_app()
app.app_context().push()
import app.scheduler 