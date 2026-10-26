import os

bind = "127.0.0.1:8000"
workers = int(os.getenv("WEB_WORKERS", "2"))
threads = int(os.getenv("WEB_THREADS", "2"))
worker_class = "gthread"
timeout = 60
graceful_timeout = 60
max_requests = 1000
max_requests_jitter = 100
accesslog = "-"
errorlog = "-"
access_log_format = '%(m)s %(U)s %(s)s %(L)s'
worker_tmp_dir = "/run/siwarga"


def child_exit(server, worker):
    from prometheus_client import multiprocess
    multiprocess.mark_process_dead(worker.pid)
