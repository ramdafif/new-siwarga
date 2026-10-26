import argparse
import hashlib
import json
import os
from pathlib import Path
import statistics
import sys
from time import perf_counter

from dotenv import load_dotenv
from sqlalchemy import event, select
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", default=str(ROOT))
    parser.add_argument("--output", required=True)
    parser.add_argument("--samples", type=int, default=20)
    args = parser.parse_args()
    if args.samples < 5:
        parser.error("At least five samples required")
    load_dotenv(ROOT / ".env")
    target = os.environ["BENCHMARK_DATABASE_URL"]
    if not make_url(target).database.endswith("_benchmark_test"):
        raise SystemExit("Dedicated benchmark database required")
    project = Path(args.project).resolve()
    sys.path.insert(0, str(project))
    from app import create_app
    from app.models import User, db

    app = create_app({"SQLALCHEMY_DATABASE_URI": target, "TESTING": True, "WTF_CSRF_ENABLED": False,
        "UPLOAD_FOLDER": str(ROOT / "test-results" / "benchmark" / "uploads")})
    report = dict(project=project.name, samples=args.samples, measurements=[])
    with app.app_context():
        people = [(user.id, user.role, getattr(user, "session_version", 1)) for user in db.session.scalars(select(User).where(
            User.email.in_(["warga@siwarga.id", "rt@siwarga.id", "rw@siwarga.id", "admin@siwarga.id"])))]
        engine = db.engine
    captured = []

    def collect(connection, cursor, statement, parameters, context, executemany):
        captured.append((statement, parameters))

    event.listen(engine, "before_cursor_execute", collect)
    plans = {}
    try:
        for user_id, role, version in people:
            for route in ("/pengaduan", "/dashboard"):
                client = app.test_client()
                with client.session_transaction() as saved:
                    saved["_user_id"] = str(user_id)
                    saved["_fresh"] = True
                    saved["account_version"] = version
                timings, counts = [], []
                for iteration in range(args.samples + 1):
                    captured.clear()
                    started = perf_counter()
                    response = client.get(route)
                    elapsed = (perf_counter() - started) * 1000
                    if response.status_code != 200:
                        raise RuntimeError(f"{role} {route}: HTTP {response.status_code}")
                    if iteration:
                        timings.append(elapsed)
                        counts.append(len(captured))
                    for statement, parameters in list(captured):
                        identity = hashlib.sha256(statement.encode()).hexdigest()[:16]
                        if statement.lstrip().upper().startswith("SELECT") and identity not in plans:
                            with engine.connect() as connection:
                                plan = connection.exec_driver_sql("EXPLAIN FORMAT=JSON " + statement, parameters).scalar()
                            plans[identity] = dict(sql=statement, explain=json.loads(plan))
                report["measurements"].append(dict(role=role, route=route, average_ms=round(statistics.mean(timings), 3),
                    p95_ms=round(sorted(timings)[max(0, int(len(timings) * .95) - 1)], 3),
                    median_queries=statistics.median(counts)))
    finally:
        event.remove(engine, "before_cursor_execute", collect)
        engine.dispose()
    report["plans"] = plans
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["measurements"]))


if __name__ == "__main__":
    main()
