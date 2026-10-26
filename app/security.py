import hashlib
import hmac
import json
import secrets
from threading import Lock
from time import time

from flask import abort, current_app, g, has_app_context, request, session
from flask.sessions import SecureCookieSessionInterface
from flask_login import current_user
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from redis import Redis, RedisError
from sqlalchemy import event
from sqlalchemy.orm import Session

from .models import AuditEvent, db

WINDOW = 900
RESERVE = """
local clock = redis.call('TIME')
local now = tonumber(clock[1]) + tonumber(clock[2]) / 1000000
local window = tonumber(ARGV[1])
for position, key in ipairs(KEYS) do
    redis.call('ZREMRANGEBYSCORE', key, '-inf', now - window)
    if redis.call('ZCARD', key) >= tonumber(ARGV[position + 2]) then
        return 0
    end
end
for position, key in ipairs(KEYS) do
    redis.call('ZADD', key, now, ARGV[2])
    redis.call('EXPIRE', key, window)
end
return 1
"""
FINISH = """
if ARGV[2] == 'success' then
    redis.call('DEL', KEYS[1])
    redis.call('ZREM', KEYS[2], ARGV[1])
end
return 1
"""


class TelemetryReadOnlySessionInterface(SecureCookieSessionInterface):
    def save_session(self, app, saved_session, response):
        if request.endpoint == "ops.receive_vitals":
            response.vary.add("Cookie")
            return
        super().save_session(app, saved_session, response)


class LimiterUnavailable(Exception):
    pass


class MemoryLoginLimiter:
    def __init__(self):
        self.entries = {}
        self.lock = Lock()

    def reserve(self, keys, token):
        with self.lock:
            now = time()
            self.entries = {key: {member: stamp for member, stamp in entries.items() if stamp > now - WINDOW}
                            for key, entries in self.entries.items() if any(stamp > now - WINDOW for stamp in entries.values())}
            if len(self.entries) > 10000:
                return False
            if any(len(self.entries.get(key, {})) >= limit for key, limit in zip(keys, (5, 30))):
                return False
            for key in keys:
                self.entries.setdefault(key, {})[token] = now
            return True

    def finish(self, keys, token, success):
        if success:
            with self.lock:
                self.entries.pop(keys[0], None)
                self.entries.get(keys[1], {}).pop(token, None)

    def ping(self):
        return True


class RedisLoginLimiter:
    def __init__(self, client):
        self.client = client

    def reserve(self, keys, token):
        try:
            return bool(self.client.eval(RESERVE, 2, *keys, WINDOW, token, 5, 30))
        except RedisError as error:
            raise LimiterUnavailable() from error

    def finish(self, keys, token, success):
        try:
            self.client.eval(FINISH, 2, *keys, token, "success" if success else "failure")
        except RedisError as error:
            raise LimiterUnavailable() from error

    def ping(self):
        return self.client.ping()


def fingerprint(value):
    return hmac.new(current_app.secret_key.encode(), value.encode(), hashlib.sha256).hexdigest()


def login_limiter():
    if "login_attempts" not in current_app.extensions:
        if current_app.config["LOGIN_RATE_LIMIT_BACKEND"] == "redis":
            client = current_app.config.get("REDIS_CLIENT")
            if client is None:
                client = Redis.from_url(current_app.config["REDIS_URL"], socket_timeout=2, socket_connect_timeout=2)
            current_app.extensions["login_attempts"] = RedisLoginLimiter(client)
        else:
            current_app.extensions["login_attempts"] = MemoryLoginLimiter()
    return current_app.extensions["login_attempts"]


def login_keys(email, address):
    prefix = current_app.config["REDIS_NAMESPACE"] + ":login:"
    return [prefix + "account:" + fingerprint(email), prefix + "ip:" + fingerprint(address or "unknown")]


@event.listens_for(Session, "after_commit")
def emit_committed_audit(saved_session):
    events = saved_session.info.pop("security_events", [])
    if has_app_context():
        for values in events:
            current_app.logger.info("security %s", json.dumps(values, separators=(",", ":")))


@event.listens_for(Session, "after_rollback")
def discard_rolled_back_audit(saved_session):
    saved_session.info.pop("security_events", None)


def security_event(event, outcome="success", target=None, details=None, commit=False):
    actor_id = current_user.id if current_user.is_authenticated else None
    request_id = getattr(g, "request_id", secrets.token_hex(16))
    values = dict(event=event, outcome=outcome, actor_id=actor_id,
                  target_id=target.id if target is not None else None,
                  request_id=request_id, details=details or {})
    db.session.add(AuditEvent(**values))
    db.session.info.setdefault("security_events", []).append(values)
    if commit:
        db.session.commit()


def revoke_sessions(user):
    user.session_version = (user.session_version or 1) + 1


def remember_session(user):
    session["account_version"] = user.session_version


def submission_serializer():
    return URLSafeTimedSerializer(current_app.secret_key, salt="complaint-submission-v1")


def issue_submission_token(user_id):
    return submission_serializer().dumps({"user": user_id, "nonce": secrets.token_hex(16)})


def read_submission_token(value, user_id):
    try:
        payload = submission_serializer().loads(value or "", max_age=86400)
        nonce = payload["nonce"]
        if payload["user"] != user_id or not isinstance(nonce, str) or len(nonce) != 32:
            raise ValueError()
        return nonce
    except (BadSignature, SignatureExpired, KeyError, TypeError, ValueError):
        abort(400, description="Formulir pengaduan tidak valid atau kedaluwarsa. Muat ulang formulir.")
