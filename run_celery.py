import threading
from app import create_app, celery

def start_celery():
    """Start Celery worker and beat scheduler in background threads."""
    from celery.bin.worker import worker as celery_worker
    from celery.bin.beat import beat as celery_beat

    def run_worker():
        worker = celery_worker(app=celery)
        worker.run(loglevel="INFO")

    def run_beat():
        beat = celery_beat(app=celery)
        beat.run(loglevel="INFO")

    threading.Thread(target=run_worker, daemon=True).start()
    threading.Thread(target=run_beat, daemon=True).start()

app = create_app()

if __name__ == "__main__":
    start_celery()
    app.run(host="0.0.0.0", port=5000)
