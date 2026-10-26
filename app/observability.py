import json
import math
import os
import secrets
import shutil
from time import perf_counter

from flask import Blueprint, Response, current_app, g, has_request_context, jsonify, request
from flask_login import current_user, login_required
from prometheus_client import CollectorRegistry, Counter, Histogram, generate_latest, multiprocess
from redis import RedisError
from sqlalchemy import event, text
from sqlalchemy.exc import SQLAlchemyError

from .models import db
from .security import login_limiter

bp = Blueprint("ops", __name__)
PAGES = {"main.dashboard", "tickets.index", "tickets.detail", "tickets.create", "auth.login", "auth.account"}


def init_observability(app):
    registry = CollectorRegistry()
    requests = Counter("siwarga_http_requests_total", "Completed application requests", ["method", "endpoint", "status"], registry=registry)
    duration = Histogram("siwarga_http_duration_seconds", "Application response duration", ["method", "endpoint"],
                         buckets=(.05, .1, .3, .5, 1, 2, 3, 5, 10, 30), registry=registry)
    queries = Histogram("siwarga_sql_queries", "SQL statements per request", ["endpoint"],
                        buckets=(0, 1, 3, 5, 10, 15, 25, 50), registry=registry)
    sql_duration = Histogram("siwarga_sql_duration_seconds", "Total SQL duration per request", ["endpoint"], registry=registry)
    vitals = Histogram("siwarga_web_vital", "Field web vitals (milliseconds or layout shift)", ["name", "page"],
                       buckets=(.01, .05, .1, .25, .5, 1, 100, 200, 500, 1000, 2500, 4000, 10000), registry=registry)
    app.extensions["observability"] = dict(registry=registry, vitals=vitals)

    @app.before_request
    def start_request():
        g.request_id = secrets.token_hex(16)
        g.started_at = perf_counter()
        g.query_count = 0
        g.query_seconds = 0

    @app.after_request
    def finish_request(response):
        response.headers["X-Request-ID"] = getattr(g, "request_id", "")
        endpoint = request.endpoint or "unmatched"
        if not endpoint.startswith(("ops.", "static")):
            elapsed = perf_counter() - getattr(g, "started_at", perf_counter())
            requests.labels(request.method, endpoint, str(response.status_code)).inc()
            duration.labels(request.method, endpoint).observe(elapsed)
            queries.labels(endpoint).observe(getattr(g, "query_count", 0))
            sql_duration.labels(endpoint).observe(getattr(g, "query_seconds", 0))
            if app.config["PROFILE_REQUESTS"]:
                app.logger.info("performance %s", json.dumps(dict(request_id=g.request_id, endpoint=endpoint,
                    method=request.method, status=response.status_code, duration_ms=round(elapsed * 1000, 3),
                    queries=g.query_count, sql_ms=round(g.query_seconds * 1000, 3))))
        return response

    with app.app_context():
        @event.listens_for(db.engine, "before_cursor_execute")
        def before_query(connection, cursor, statement, parameters, context, executemany):
            if has_request_context():
                context.siwarga_started = perf_counter()
                g.query_count = getattr(g, "query_count", 0) + 1

        @event.listens_for(db.engine, "after_cursor_execute")
        def after_query(connection, cursor, statement, parameters, context, executemany):
            if has_request_context() and hasattr(context, "siwarga_started"):
                g.query_seconds = getattr(g, "query_seconds", 0) + perf_counter() - context.siwarga_started

    app.register_blueprint(bp)


@bp.get("/health/live")
def live():
    return jsonify(status="alive")


@bp.get("/health/ready")
def ready():
    try:
        db.session.execute(text("SELECT 1"))
        login_limiter().ping()
        if (not os.access(current_app.config["UPLOAD_FOLDER"], os.W_OK)
                or shutil.disk_usage(current_app.config["UPLOAD_FOLDER"]).free < current_app.config["MAX_CONTENT_LENGTH"]):
            raise OSError()
    except (SQLAlchemyError, RedisError, OSError):
        db.session.rollback()
        return jsonify(status="not_ready"), 503
    return jsonify(status="ready")


@bp.get("/metrics")
def metrics():
    if request.remote_addr not in {"127.0.0.1", "::1"}:
        return Response(status=404)
    if os.environ.get("PROMETHEUS_MULTIPROC_DIR"):
        registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)
    else:
        registry = current_app.extensions["observability"]["registry"]
    database_metrics = ["siwarga_database_up 0"]
    try:
        connected = db.session.execute(text("SHOW GLOBAL STATUS LIKE 'Threads_connected'")).one()[1]
        maximum = db.session.execute(text("SHOW GLOBAL VARIABLES LIKE 'max_connections'")).one()[1]
        database_metrics = ["siwarga_database_up 1", f"siwarga_database_connections {int(connected)}",
                            f"siwarga_database_connection_limit {int(maximum)}",
                            f"siwarga_database_pool_checked_out {db.engine.pool.checkedout()}"]
    except SQLAlchemyError:
        db.session.rollback()
    try:
        backend_up = int(bool(login_limiter().ping()))
    except RedisError:
        backend_up = 0
    extra = "\n".join(database_metrics + [f"siwarga_login_backend_up {backend_up}"]) + "\n"
    return Response(generate_latest(registry) + extra.encode(), content_type="text/plain; version=0.0.4; charset=utf-8")


@bp.post("/telemetry/vitals")
@login_required
def receive_vitals():
    if not current_app.config["ENABLE_WEB_VITALS"]:
        return Response(status=404)
    if request.content_length is None or request.content_length > 2048:
        return Response(status=413)
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or set(payload) != {"name", "value", "page"}:
        return Response(status=400)
    name, value, page = payload["name"], payload["value"], payload["page"]
    if not isinstance(name, str) or name not in {"LCP", "INP", "CLS"} or not isinstance(page, str) or page not in PAGES:
        return Response(status=400)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0 or value > (100 if name == "CLS" else 3600000):
        return Response(status=400)
    current_app.extensions["observability"]["vitals"].labels(name, page).observe(value)
    current_app.logger.info("web_vital %s", json.dumps(payload, separators=(",", ":")))
    return Response(status=204)
