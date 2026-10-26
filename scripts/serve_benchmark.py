import argparse
import os
from pathlib import Path
import sys
from threading import Thread
from werkzeug.serving import make_server

from dotenv import dotenv_values
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description="Local-only benchmark server; never a production entrypoint")
    parser.add_argument("--project", default=str(ROOT))
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    values = dotenv_values(ROOT / ".env")
    target = os.getenv("BENCHMARK_DATABASE_URL") or make_url(values["TEST_DATABASE_URL"]).set(database="siwarga_benchmark_test").render_as_string(hide_password=False)
    if not make_url(target).database.endswith("_benchmark_test"):
        raise SystemExit("Dedicated benchmark database required")
    sys.path.insert(0, str(Path(args.project).resolve()))
    from app import create_app

    app = create_app({"SQLALCHEMY_DATABASE_URI": target, "SECRET_KEY": values["SECRET_KEY"],
        "UPLOAD_FOLDER": str(ROOT / "test-results" / "benchmark" / "uploads"), "LOGIN_RATE_LIMIT_BACKEND": "memory"})
    stop = ROOT / ".local" / f"benchmark-{args.port}.stop"
    stop.parent.mkdir(parents=True, exist_ok=True)
    stop.unlink(missing_ok=True)
    server = make_server("127.0.0.1", args.port, app, threaded=True)
    runner = Thread(target=server.serve_forever, daemon=True)
    runner.start()
    print(f"Benchmark listening on 127.0.0.1:{args.port}; create {stop.name} to stop.", flush=True)
    try:
        while runner.is_alive() and not stop.exists():
            runner.join(.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        server.server_close()
        stop.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
