import multiprocessing

wsgi_app = "run:app"
bind = "0.0.0.0:10000"
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "gevent"
timeout = 120
graceful_timeout = 30
backlog = 2048
accesslog = "-"
errorlog = "-"
loglevel = "info"
preload_app = True
