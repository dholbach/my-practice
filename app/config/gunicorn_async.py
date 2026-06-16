# Gunicorn Configuration for Async Support
# =========================================
#
# This configuration enables async view support in Django 5.1+
# Uses uvicorn workers for ASGI compatibility
#
# Usage:
#   gunicorn -c config/gunicorn_async.py config.asgi:application

import multiprocessing

# Server socket
bind = "0.0.0.0:8000"
backlog = 2048

# Worker processes
# Use uvicorn worker class for async support
worker_class = "uvicorn.workers.UvicornWorker"
workers = multiprocessing.cpu_count() * 2 + 1
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50
timeout = 30
keepalive = 2

# Async worker settings
# Enable async I/O for better performance
worker_tmp_dir = "/dev/shm"

# Logging
accesslog = "-"  # Log to stdout
errorlog = "-"  # Log to stderr
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = "payments-async"

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# SSL (uncomment for HTTPS)
# keyfile = "/path/to/key.pem"
# certfile = "/path/to/cert.pem"

# Graceful timeout
graceful_timeout = 30

# Preload app for faster worker spawn
# Disable if using async workers with different behavior
preload_app = False


def on_starting(server):  # noqa: ARG001, vulture
    """Called just before the master process is initialized."""
    print("🚀 Starting Gunicorn with async worker support")


def on_reload(server):  # noqa: ARG001, vulture
    """Called to recycle workers during a reload via SIGHUP."""
    print("♻️  Reloading workers")


def when_ready(server):  # noqa: ARG001, vulture
    """Called just after the server is started."""
    print(f"✅ Server ready with {workers} async workers")


def worker_int(worker):
    """Called when a worker receives SIGINT or SIGQUIT signal."""
    print(f"⚠️  Worker {worker.pid} interrupted")


def worker_abort(worker):
    """Called when a worker receives SIGABRT signal."""
    print(f"❌ Worker {worker.pid} aborted")
