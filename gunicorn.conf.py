# gunicorn.conf.py

import multiprocessing

# ✅ Entry point for your app factory
wsgi_app = "app:create_app()"

# ✅ Bind to all network interfaces on Render's port
bind = "0.0.0.0:10000"

# ✅ Workers = CPU cores * 2 + 1 (a good rule of thumb)
workers = multiprocessing.cpu_count() * 2 + 1

# ✅ Use async workers for better performance with I/O
worker_class = "gevent"

# ✅ Maximum pending connections
backlog = 2048

# ✅ Timeout (seconds) before worker restart
timeout = 120

# ✅ Graceful restart timeout
graceful_timeout = 30

# ✅ Limit request body (in bytes) — 100 MB
limit_request_line = 0
limit_request_fields = 32768
limit_request_field_size = 0

# ✅ Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"

# ✅ Prevent gunicorn from forking too many times
preload_app = True
