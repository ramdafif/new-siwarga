import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from uuid import uuid4

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


@contextmanager
def maintenance_lock(path):
    path = Path(path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        if os.name == "nt":
            import msvcrt
            if path.stat().st_size == 0:
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def checksum(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def safe_file(folder, name):
    folder = Path(folder).resolve()
    if not isinstance(name, str) or not name or Path(name).name != name or "/" in name or "\\" in name:
        raise ValueError("Invalid snapshot filename")
    candidate = folder / name
    if candidate.is_symlink() or not candidate.resolve().is_relative_to(folder):
        raise ValueError("Snapshot path escaped its directory")
    return candidate


def database_url(value):
    url = make_url(value)
    if url.drivername != "mysql+pymysql" or not url.database:
        raise ValueError("A named MySQL database is required")
    return url


def validate_recovery_target(value, source, verification=False):
    target = database_url(value)
    origin = database_url(source)
    if target.database == origin.database:
        raise ValueError("Recovery target must not be the application database")
    if verification and not target.database.endswith("_restore_test"):
        raise ValueError("Verification database must end with _restore_test")
    return target


def mysql_binary(name):
    configured = os.getenv("MYSQL_BIN_DIR")
    if configured:
        return str(Path(configured) / (name + (".exe" if os.name == "nt" else "")))
    matches = sorted((ROOT / ".local").glob("mysql-8.*-winx64/bin/" + name + ".exe"))
    if matches:
        return str(matches[-1])
    system = shutil.which(name)
    if system:
        version = subprocess.run([system, "--version"], capture_output=True, text=True, check=True).stdout
        if "MariaDB" not in version and "Ver 8." in version:
            return system
    raise RuntimeError(f"MySQL 8 {name} not found; configure MYSQL_BIN_DIR")


@contextmanager
def mysql_options(url):
    def escape(value):
        return str(value or "").replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r")

    descriptor, name = tempfile.mkstemp(prefix="siwarga-mysql-", suffix=".cnf")
    try:
        os.chmod(name, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write("[client]\n" + "\n".join(f'{key}="{escape(value)}"' for key, value in {
                "host": url.host or "127.0.0.1", "port": url.port or 3306,
                "user": url.username, "password": url.password, "default-character-set": "utf8mb4"}.items()) + "\n")
        yield "--defaults-extra-file=" + name
    finally:
        Path(name).unlink(missing_ok=True)


def run_mysql(url, dump_path=None, output_path=None):
    with mysql_options(url) as options:
        if output_path:
            command = [mysql_binary("mysqldump"), options, "--single-transaction", "--quick", "--hex-blob",
                       "--no-tablespaces", "--set-gtid-purged=OFF", "--column-statistics=0", "--skip-add-locks", url.database]
            with Path(output_path).open("xb") as output:
                subprocess.run(command, stdout=output, stderr=subprocess.PIPE, check=True, timeout=3600)
        else:
            with Path(dump_path).open("rb") as source:
                subprocess.run([mysql_binary("mysql"), options, url.database], stdin=source,
                               stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True, timeout=3600)


def snapshot_attachments(url):
    engine = create_engine(url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            return connection.execute(text("SELECT id, nama_tersimpan FROM lampiran ORDER BY id")).all()
    finally:
        engine.dispose()


def verify_snapshot(directory):
    directory = Path(directory).resolve()
    manifest = json.loads(safe_file(directory, "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("version") != 1 or checksum(safe_file(directory, "database.sql")) != manifest["database_sha256"]:
        raise ValueError("Database snapshot checksum mismatch")
    for attachment in manifest["attachments"]:
        candidate = safe_file(directory / "uploads", attachment["name"])
        if not candidate.is_file() or checksum(candidate) != attachment["sha256"]:
            raise ValueError(f"Missing or corrupt attachment {attachment['id']}")
    return manifest


def create_snapshot(source, verification, uploads, output):
    started = time.monotonic()
    origin = database_url(source)
    target = validate_recovery_target(verification, source, verification=True)
    identity = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
    base = Path(output).resolve()
    base.mkdir(parents=True, exist_ok=True)
    working = base / (".pending-" + identity)
    working.mkdir()
    (working / "uploads").mkdir()
    dump = working / "database.sql"
    snapshot_time = datetime.now(timezone.utc).isoformat()
    engine = create_engine(origin)
    try:
        with engine.connect() as connection:
            unsupported = connection.scalar(text("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = :schema AND table_type = 'BASE TABLE' AND engine != 'InnoDB'"), {"schema": origin.database})
            if unsupported:
                raise ValueError("Online snapshot requires all tables to use InnoDB")
    finally:
        engine.dispose()
    run_mysql(origin, output_path=dump)
    run_mysql(target, dump_path=dump)
    attachments = []
    for attachment_id, name in snapshot_attachments(target):
        source_file = safe_file(uploads, name)
        destination = safe_file(working / "uploads", name)
        shutil.copyfile(source_file, destination)
        source_hash = checksum(source_file)
        if checksum(destination) != source_hash:
            raise ValueError("Attachment changed during backup")
        attachments.append(dict(id=attachment_id, name=name, sha256=source_hash, bytes=destination.stat().st_size))
    manifest = dict(version=1, snapshot_at=snapshot_time, database_sha256=checksum(dump), attachments=attachments,
                    duration_seconds=round(time.monotonic() - started, 3))
    (working / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    verify_snapshot(working)
    destination = base / identity
    working.rename(destination)
    return destination


def restore_snapshot(directory, target, source, uploads):
    from app.image_variants import render_variants
    from app.uploads import atomic_write, variant_filename

    manifest = verify_snapshot(directory)
    target_url = validate_recovery_target(target, source)
    engine = create_engine(target_url)
    try:
        with engine.connect() as connection:
            count = connection.scalar(text("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = :name"), {"name": target_url.database})
            if count:
                raise ValueError("Restore requires an empty target database")
    finally:
        engine.dispose()
    folder = Path(uploads).resolve()
    if folder.exists() and any(folder.iterdir()):
        raise ValueError("Restore requires an empty photo directory")
    folder.mkdir(parents=True, exist_ok=True)
    for attachment in manifest["attachments"]:
        name = attachment["name"]
        content = safe_file(Path(directory) / "uploads", name).read_bytes()
        atomic_write(safe_file(folder, name), content)
        for variant, rendered in render_variants(content).items():
            atomic_write(folder / variant_filename(name, variant), rendered)
    run_mysql(target_url, dump_path=Path(directory) / "database.sql")
    expected = {(item["id"], item["name"]) for item in manifest["attachments"]}
    if set(snapshot_attachments(target_url)) != expected:
        raise ValueError("Restored attachment rows differ from manifest")
    return manifest


def prune_local(output, keep=2):
    base = Path(output).resolve()
    snapshots = sorted((entry for entry in base.iterdir() if re.fullmatch(r"[0-9]{8}T[0-9]{6}Z-[a-f0-9]{8}", entry.name)),
                       key=lambda entry: entry.name, reverse=True)
    for candidate in snapshots[keep:]:
        if candidate.is_symlink() or candidate.resolve().parent != base:
            raise ValueError("Refusing to remove a snapshot outside the backup directory")
        verify_snapshot(candidate)
        shutil.rmtree(candidate.resolve())


def main():
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description="Online database/photo snapshots; originals must remain immutable.")
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create")
    create.add_argument("--output", required=True)
    create.add_argument("--lock", default=os.getenv("MAINTENANCE_LOCK", str(ROOT / "instance" / "maintenance.lock")))
    verify = commands.add_parser("verify")
    verify.add_argument("snapshot")
    restore = commands.add_parser("restore")
    restore.add_argument("snapshot")
    restore.add_argument("--uploads", required=True)
    prune = commands.add_parser("prune-local")
    prune.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        if args.command == "create":
            with maintenance_lock(args.lock):
                result = create_snapshot(os.environ["DATABASE_URL"], os.environ["BACKUP_VERIFY_DATABASE_URL"],
                    os.getenv("UPLOAD_FOLDER", str(ROOT / "instance" / "uploads")), args.output)
            print(json.dumps(dict(snapshot=str(result))))
        elif args.command == "verify":
            result = verify_snapshot(args.snapshot)
            print(json.dumps(dict(status="verified", attachments=len(result["attachments"]))))
        elif args.command == "prune-local":
            prune_local(args.output)
            print(json.dumps(dict(status="pruned")))
        else:
            result = restore_snapshot(args.snapshot, os.environ["RESTORE_DATABASE_URL"], os.environ["DATABASE_URL"], args.uploads)
            print(json.dumps(dict(status="restored", attachments=len(result["attachments"]))))
    except (OSError, ValueError, KeyError, RuntimeError, SQLAlchemyError, subprocess.SubprocessError) as error:
        print(f"Backup/restore failed: {type(error).__name__}; no success marker written.", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
