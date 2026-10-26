import os
from datetime import timedelta
from io import BytesIO
from pathlib import Path
import random
import sys

from dotenv import load_dotenv
from flask_migrate import upgrade
from PIL import Image
from sqlalchemy import func, insert, select
from sqlalchemy.engine import make_url
from werkzeug.datastructures import FileStorage

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app import create_app
from app.models import Kategori, Komentar, Lampiran, Pengaduan, RT, RW, RiwayatStatus, User, db, utcnow
from app.uploads import atomic_write, validate_uploads, variant_filename


def main():
    load_dotenv(ROOT / ".env")
    target = os.environ["BENCHMARK_DATABASE_URL"]
    if not make_url(target).database.endswith("_benchmark_test"):
        raise SystemExit("Dedicated database ending _benchmark_test required")
    uploads = ROOT / "test-results" / "benchmark" / "uploads"
    app = create_app({"SQLALCHEMY_DATABASE_URI": target, "UPLOAD_FOLDER": str(uploads),
        "DEMO_PASSWORD": os.getenv("BENCHMARK_PASSWORD", "BenchmarkPassword123!"), "LOGIN_RATE_LIMIT_BACKEND": "memory"})
    with app.app_context():
        upgrade(directory=str(ROOT / "migrations"))
        result = app.test_cli_runner().invoke(args=["seed-demo"])
        if result.exit_code:
            raise RuntimeError(result.output)
        owner = db.session.scalar(select(User).where(User.email == "warga@siwarga.id"))
        second = db.session.scalar(select(User).where(User.email == "warga02@siwarga.id"))
        category = db.session.scalar(select(Kategori))
        other_rw = db.session.scalar(select(RW).where(RW.nomor == "99"))
        if not other_rw:
            other_rw = RW(nomor="99", nama_wilayah="Benchmark wilayah terpisah")
            db.session.add(other_rw)
            db.session.flush()
            other_rt = RT(rw_id=other_rw.id, nomor="01")
            db.session.add(other_rt)
            db.session.flush()
            outside = User(nama="Benchmark Luar RW", email="outside@benchmark.invalid", role="WARGA", status="ACTIVE", rw_id=other_rw.id, rt_id=other_rt.id)
            outside.set_password("BenchmarkPassword123!")
            db.session.add(outside)
            db.session.flush()
        outside = db.session.scalar(select(User).where(User.email == "outside@benchmark.invalid"))
        existing = set(db.session.scalars(select(Pengaduan.nomor_tiket).where(Pengaduan.nomor_tiket.like("SW-BENCH-%"))))
        now = utcnow()
        rows = []
        for index in range(10000):
            number = f"SW-BENCH-{index:07d}"
            if number in existing:
                continue
            reporter = (owner, second, outside)[index % 3]
            rows.append(dict(nomor_tiket=number, pelapor_id=reporter.id, rt_id=reporter.rt_id, kategori_id=category.id,
                judul=f"Laporan benchmark sintetis {index:07d}", deskripsi="Dataset sintetis untuk pengukuran query dan isolasi wilayah.",
                lokasi_teks="Lokasi benchmark", status="MENUNGGU_VERIFIKASI", created_at=now - timedelta(minutes=index), updated_at=now))
        for offset in range(0, len(rows), 500):
            db.session.execute(insert(Pengaduan), rows[offset:offset + 500])
        db.session.commit()
        sample = db.session.scalars(select(Pengaduan).where(Pengaduan.nomor_tiket.like("SW-BENCH-%"), Pengaduan.pelapor_id == owner.id)
                                    .order_by(Pengaduan.created_at.desc()).limit(10)).all()
        for ticket in sample:
            if not ticket.riwayat:
                db.session.add_all([RiwayatStatus(pengaduan_id=ticket.id, aktor_id=owner.id, status_baru=ticket.status,
                    catatan="Riwayat benchmark sintetis.") for unused in range(10)])
                db.session.add_all([Komentar(pengaduan_id=ticket.id, user_id=owner.id, isi="Komentar benchmark sintetis.") for unused in range(5)])
        ticket = sample[0]
        if not ticket.lampiran:
            noise = random.Random(42)
            for index in range(3):
                stream = BytesIO()
                Image.frombytes("RGB", (1800, 1200), noise.randbytes(1800 * 1200 * 3)).save(stream, "JPEG", quality=90)
                stream.seek(0)
                prepared = validate_uploads([FileStorage(stream=stream, filename=f"benchmark-{index}.jpg", content_type="image/jpeg")])[0]
                original, stored, content, variants = prepared
                atomic_write(uploads / stored, content)
                for variant, rendered in variants.items():
                    atomic_write(uploads / variant_filename(stored, variant), rendered)
                db.session.add(Lampiran(pengaduan_id=ticket.id, uploader_id=owner.id, nama_asli=original, nama_tersimpan=stored, jenis="LAPORAN"))
        db.session.commit()
        import json
        output = dict(tickets=db.session.scalar(select(func.count()).select_from(Pengaduan)), photo_ticket_id=ticket.id,
                      photo_bytes=sum((uploads / attachment.nama_tersimpan).stat().st_size for attachment in ticket.lampiran))
        (ROOT / "test-results" / "benchmark" / "fixture.json").write_text(json.dumps(output, indent=2) + "\n")
        print(json.dumps(output))


if __name__ == "__main__":
    main()
