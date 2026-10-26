from concurrent.futures import ThreadPoolExecutor
import os
import secrets

import fakeredis
import pytest
from redis import Redis
from sqlalchemy.exc import OperationalError

from app import create_app
from app.models import db
from app.security import login_keys, login_limiter


@pytest.mark.parametrize("configuration", [
    {"APP_ENV": "production", "LOGIN_RATE_LIMIT_BACKEND": "memory"},
    {"APP_ENV": "staging", "LOGIN_RATE_LIMIT_BACKEND": "redis", "SESSION_COOKIE_SECURE": False},
    {"APP_ENV": "production", "LOGIN_RATE_LIMIT_BACKEND": "redis", "SESSION_COOKIE_SECURE": True, "TRUSTED_HOSTS": None},
    {"PROXY_HOPS": 2}, {"LOGIN_RATE_LIMIT_BACKEND": "unrecognized"},
])
def test_unsafe_deployment_configuration_is_rejected(configuration):
    with pytest.raises(RuntimeError):
        create_app(dict(configuration, SECRET_KEY="testing-only-secret-longer-than-thirty-two-characters"))


def test_atomic_login_reservations_across_threads(app):
    client = Redis.from_url(os.environ["TEST_REDIS_URL"]) if os.getenv("TEST_REDIS_URL") else fakeredis.FakeRedis()
    previous = {key: app.config[key] for key in ("LOGIN_RATE_LIMIT_BACKEND", "REDIS_NAMESPACE")}
    app.config.update(LOGIN_RATE_LIMIT_BACKEND="redis", REDIS_CLIENT=client, REDIS_NAMESPACE="integration:" + secrets.token_hex(8))
    app.extensions.pop("login_attempts", None)
    limiter = login_limiter()
    keys = login_keys("parallel@example.com", "203.0.113.50")
    try:
        with ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(lambda token: limiter.reserve(keys, str(token)), range(10)))
        assert sum(results) == 5
        assert 0 < client.ttl(keys[0]) <= 900
        assert client.zcard(keys[1]) == 5
        limiter.finish(keys, "0", True)
        assert client.zcard(keys[0]) == 0
        assert limiter.reserve(keys, "new-attempt")
    finally:
        client.delete(*keys)
        app.config.update(previous)
        app.config.pop("REDIS_CLIENT", None)
        app.extensions.pop("login_attempts", None)


def test_database_outage_keeps_liveness_available_but_readiness_fails(client, monkeypatch):
    def unavailable(*args, **kwargs):
        raise OperationalError("SELECT", {}, Exception("Simulated database unavailable"))

    monkeypatch.setattr(db.session, "execute", unavailable)
    assert client.get("/health/live").status_code == 200
    assert client.get("/health/ready").status_code == 503


def test_untrusted_forwarded_ip_cannot_bypass_local_limit(client, data):
    for index in range(5):
        assert client.post("/login", data={"email": "owner@example.com", "password": "wrong"},
                           headers={"X-Forwarded-For": f"203.0.113.{index}"}).status_code == 200
    assert client.post("/login", data={"email": "owner@example.com", "password": "wrong"},
                       headers={"X-Forwarded-For": "203.0.113.200"}).status_code == 429
