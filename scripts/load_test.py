import argparse
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from io import BytesIO
import json
import os
from pathlib import Path
import random
import secrets
import statistics
from threading import Lock
from time import perf_counter, sleep

from PIL import Image
import requests


class FormValues(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.values = {}
        self.category = None
        self.photos = []
        self.in_category = False
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "img" and values.get("src", "").startswith("/lampiran/"):
            self.photos.append(values["src"])
        if tag == "input" and values.get("name"):
            self.values[values["name"]] = values.get("value", "")
        if tag == "meta" and values.get("name") == "csrf-token":
            self.values["csrf_token"] = values.get("content", "")
        if tag == "select":
            self.in_category = values.get("name") == "kategori_id"
        if tag == "option" and self.in_category and not self.category and values.get("value", "0") not in {"", "0"}:
            self.category = values["value"]

    def handle_endtag(self, tag):
        if tag == "select":
            self.in_category = False


def percentile(values, proportion):
    return sorted(values)[max(0, int(len(values) * proportion + .999999) - 1)]


def main():
    parser = argparse.ArgumentParser(description="Mutating staging-only mixed workload: 70% read, 20% comment, 10% upload.")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--ticket-id", required=True, type=int)
    parser.add_argument("--sessions", default="1,10,25,50")
    parser.add_argument("--seconds-per-stage", type=int, default=60)
    parser.add_argument("--think-seconds", type=float, default=2)
    parser.add_argument("--allow-writes", action="store_true")
    parser.add_argument("--email", default="warga@siwarga.id")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if not args.allow_writes:
        parser.error("Explicit --allow-writes required; never target production")
    sessions = [int(value) for value in args.sessions.split(",")]
    if not sessions or any(value < 1 or value > 200 for value in sessions) or args.seconds_per_stage < 1 or args.think_seconds < 0:
        parser.error("Invalid load duration or concurrency")
    base = args.base_url.rstrip("/")
    password = os.environ.get("BENCHMARK_PASSWORD", "BenchmarkPassword123!")
    photo = BytesIO()
    Image.frombytes("RGB", (800, 600), random.Random(42).randbytes(800 * 600 * 3)).save(photo, "JPEG", quality=85)
    photo_bytes = photo.getvalue()
    stages = []
    for concurrency in sessions:
        clients = []
        for unused in range(concurrency):
            client = requests.Session()
            form = FormValues(client.get(base + "/login", timeout=30).text)
            response = client.post(base + "/login", data={"email": args.email, "password": password,
                "csrf_token": form.values["csrf_token"]}, allow_redirects=False, timeout=30)
            if response.status_code != 302 or not response.headers.get("Location", "").endswith("/dashboard"):
                raise RuntimeError(f"Login setup failed with HTTP {response.status_code}; limits were not disabled")
            clients.append(client)
        records = []
        lock = Lock()
        started = perf_counter()
        deadline = started + args.seconds_per_stage

        def run_worker(worker_index):
            client = clients[worker_index]
            randomizer = random.Random(42 + worker_index)

            def send(method, path, label, expected, **kwargs):
                request_started = perf_counter()
                try:
                    response = client.request(method, base + path, allow_redirects=False, timeout=45, **kwargs)
                    status = response.status_code
                    success = status in expected
                except requests.RequestException:
                    response, status, success = None, 0, False
                record = dict(method=method, route=label, status=status, success=success,
                              milliseconds=round((perf_counter() - request_started) * 1000, 3))
                with lock:
                    records.append(record)
                return response if success else None

            while perf_counter() < deadline:
                operation = randomizer.random()
                if operation < .7:
                    path, label = randomizer.choice([("/dashboard", "dashboard"), ("/pengaduan", "list"),
                        (f"/pengaduan/{args.ticket_id}", "detail")])
                    response = send("GET", path, label, {200})
                    if response is not None and label == "detail":
                        for photo_path in FormValues(response.text).photos[:3]:
                            send("GET", photo_path, "photo", {200})
                elif operation < .9:
                    response = send("GET", f"/pengaduan/{args.ticket_id}", "comment_form", {200})
                    if response:
                        form = FormValues(response.text)
                        send("POST", f"/pengaduan/{args.ticket_id}/komentar", "comment", {302},
                             data={"csrf_token": form.values["csrf_token"], "isi": "Catatan uji beban sintetis " + secrets.token_hex(4)})
                else:
                    response = send("GET", "/pengaduan/baru", "report_form", {200})
                    if response:
                        form = FormValues(response.text)
                        send("POST", "/pengaduan", "report_upload", {302}, data={"csrf_token": form.values["csrf_token"],
                            "submission_token": form.values["submission_token"], "kategori_id": form.category,
                            "judul": "Laporan uji beban " + secrets.token_hex(4), "lokasi_teks": "Lokasi staging sintetis",
                            "deskripsi": "Laporan sintetis untuk pengujian kapasitas; bukan laporan warga nyata."},
                            files={"foto": ("load.jpg", photo_bytes, "image/jpeg")})
                sleep(args.think_seconds)

        try:
            with ThreadPoolExecutor(max_workers=concurrency) as executor:
                list(executor.map(run_worker, range(concurrency)))
        finally:
            for client in clients:
                client.close()
        elapsed = perf_counter() - started
        routes = {}
        for record in records:
            key = record["method"] + " " + record["route"]
            routes.setdefault(key, []).append(record)
        summary = {}
        for route, entries in routes.items():
            timings = [entry["milliseconds"] for entry in entries]
            summary[route] = dict(requests=len(entries), average_ms=round(statistics.mean(timings), 3),
                                 p95_ms=round(percentile(timings, .95), 3), failures=sum(not entry["success"] for entry in entries))
        stages.append(dict(sessions=concurrency, elapsed_seconds=round(elapsed, 3), requests=len(records),
            requests_per_second=round(len(records) / elapsed, 3),
            unexpected_responses=sum(not entry["success"] for entry in records),
            server_error_rate=sum(entry["status"] >= 500 for entry in records) / max(len(records), 1),
            network_errors=sum(entry["status"] == 0 for entry in records), routes=summary))
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(dict(workload="70% read / 20% comment / 10% report upload", stages=stages), indent=2) + "\n")
    print(json.dumps(stages))
    if any(stage["unexpected_responses"] for stage in stages):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
