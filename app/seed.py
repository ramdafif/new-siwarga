from datetime import timedelta

import click
from flask import current_app
from flask.cli import with_appcontext
from sqlalchemy import select

from .models import Kategori, Notifikasi, Pengaduan, RT, RW, RiwayatStatus, TindakLanjut, User, db, utcnow


@click.command("seed-demo")
@with_appcontext
def seed_demo():
    """Tambahkan data demo tanpa menimpa data atau password yang sudah ada."""
    if current_app.config.get("APP_ENV") == "production":
        raise click.ClickException("Seed demo dilarang pada lingkungan produksi.")
    password = current_app.config.get("DEMO_PASSWORD")
    if not password or not 10 <= len(password) <= 128:
        raise click.ClickException("Isi DEMO_PASSWORD (10-128 karakter) di .env, khusus pengembangan lokal.")
    rw = db.session.scalar(select(RW).where(RW.nomor == "05"))
    if not rw:
        rw = RW(nomor="05", nama_wilayah="Sukamaju, Bandung")
        db.session.add(rw)
        db.session.flush()
    rts = []
    for number in ("01", "02"):
        rt = db.session.scalar(select(RT).where(RT.rw_id == rw.id, RT.nomor == number))
        if not rt:
            rt = RT(rw_id=rw.id, nomor=number)
            db.session.add(rt)
            db.session.flush()
        rts.append(rt)
    names = ("Jalan & Infrastruktur", "Sampah & Kebersihan", "Drainase", "Penerangan Jalan", "Fasilitas Umum", "Lainnya")
    categories = []
    for name in names:
        category = db.session.scalar(select(Kategori).where(Kategori.nama == name))
        if not category:
            category = Kategori(nama=name, aktif=True)
            db.session.add(category)
            db.session.flush()
        categories.append(category)
    definitions = (
        ("admin", "Admin SiWarga", "SUPERADMIN", None, None, "ACTIVE"),
        ("rw", "Budi Santoso", "RW", rw.id, None, "ACTIVE"),
        ("rt", "Hendra Wijaya", "RT", rw.id, rts[0].id, "ACTIVE"),
        ("rt02", "Dewi Lestari", "RT", rw.id, rts[1].id, "ACTIVE"),
        ("karangtaruna", "Rizky Ramadhan", "KARANG_TARUNA", rw.id, None, "ACTIVE"),
        ("warga", "Aditya Pratama", "WARGA", rw.id, rts[0].id, "ACTIVE"),
        ("warga02", "Nadia Putri", "WARGA", rw.id, rts[1].id, "ACTIVE"),
        ("pending", "Siti Aminah", "WARGA", rw.id, rts[0].id, "PENDING"),
    )
    users = {}
    for handle, name, role, rw_id, rt_id, status in definitions:
        email = f"{handle}@siwarga.id"
        user = db.session.scalar(select(User).where(User.email == email))
        if not user:
            user = User(nama=name, email=email, role=role, rw_id=rw_id, rt_id=rt_id, status=status)
            user.set_password(password)
            db.session.add(user)
            db.session.flush()
        users[handle] = user
    reports = (
        ("Lampu jalan padam di Gang Melati", 3, "MENUNGGU_VERIFIKASI", "Gang Melati, dekat pos ronda RT 01", "Dua lampu jalan di Gang Melati padam sejak tadi malam. Jalan menjadi gelap dan cukup berbahaya bagi warga yang pulang malam.", 0, "warga"),
        ("Sampah menumpuk di tempat pembuangan", 1, "DIPROSES", "TPS Jalan Mawar, RT 01", "Sampah di TPS belum diangkut selama tiga hari. Bau mulai mengganggu rumah di sekitarnya. Mohon dibantu pengangkutan.", 1, "warga"),
        ("Saluran air tersumbat setelah hujan", 2, "DIPROSES", "Depan rumah nomor 12, Jalan Melati", "Saluran air di depan rumah tersumbat daun dan sampah. Air meluap ke jalan ketika hujan dan perlu dibersihkan bersama.", 2, "warga"),
        ("Jalan berlubang di depan pos ronda", 0, "SELESAI", "Jalan Melati, depan pos ronda RT 01", "Terdapat lubang cukup dalam di depan pos ronda. Beberapa pengendara hampir terjatuh terutama saat hujan turun.", 3, "warga"),
        ("Bangku taman perlu diperbaiki", 4, "SELESAI", "Taman warga RW 05, sisi timur", "Papan dudukan bangku taman sudah lapuk dan ada paku yang menonjol. Mohon perbaikan agar aman digunakan anak-anak.", 4, "warga"),
        ("Pembersihan selokan Gang Anggrek", 2, "SELESAI", "Gang Anggrek RT 01", "Endapan lumpur menumpuk di selokan Gang Anggrek. Warga mengusulkan kerja bakti agar aliran air kembali lancar.", 5, "warga"),
        ("Usulan perbaikan pagar rumah pribadi", 5, "DITOLAK", "Rumah nomor 8, RT 01", "Saya ingin meminta bantuan perbaikan pagar rumah pribadi yang rusak akibat usia. Mohon ditinjau oleh pengurus.", 6, "warga"),
        ("Penerangan lapangan mulai redup", 3, "MENUNGGU_VERIFIKASI", "Lapangan bersama RT 02", "Lampu di sisi barat lapangan mulai redup dan berkedip. Aktivitas olahraga warga pada malam hari menjadi terganggu.", 1, "warga02"),
        ("Gotong royong membersihkan taman", 1, "DIPROSES", "Taman RT 02 dekat balai warga", "Daun kering dan sampah plastik menumpuk di taman. Mohon bantuan Karang Taruna untuk penjadwalan kerja bakti.", 3, "warga02"),
    )
    created = 0
    for index, (title, category_index, status, location, description, days, handle) in enumerate(reports, 1):
        number = f"SW-DEMO-{index:06d}"
        if db.session.scalar(select(Pengaduan.id).where(Pengaduan.nomor_tiket == number)):
            continue
        reporter = users[handle]
        manager = users["rt" if handle == "warga" else "rt02"]
        date = utcnow() - timedelta(days=days, hours=2)
        assigned = users["karangtaruna"].id if status in {"DIPROSES", "SELESAI"} else None
        ticket = Pengaduan(nomor_tiket=number, pelapor_id=reporter.id, rt_id=reporter.rt_id,
                           kategori_id=categories[category_index].id, judul=title, deskripsi=description,
                           lokasi_teks=location, status=status, ditugaskan_ke_id=assigned,
                           created_at=date, updated_at=date + timedelta(hours=1))
        if status == "SELESAI":
            ticket.selesai_at = date + timedelta(hours=1)
        if status == "DITOLAK":
            ticket.alasan_penolakan = "Perbaikan properti pribadi berada di luar ruang lingkup fasilitas umum RT/RW. Silakan menghubungi pengurus untuk konsultasi."
        db.session.add(ticket)
        db.session.flush()
        db.session.add(RiwayatStatus(pengaduan_id=ticket.id, aktor_id=reporter.id, status_baru="MENUNGGU_VERIFIKASI",
                                    catatan="Pengaduan dikirim oleh warga.", created_at=date))
        if status != "MENUNGGU_VERIFIKASI":
            next_status = "DITOLAK" if status == "DITOLAK" else "DIPROSES"
            db.session.add(RiwayatStatus(pengaduan_id=ticket.id, aktor_id=manager.id, status_lama="MENUNGGU_VERIFIKASI",
                                        status_baru=next_status, catatan=ticket.alasan_penolakan or "Laporan diterima dan mulai ditindaklanjuti.", created_at=date + timedelta(minutes=15)))
        if assigned:
            note = "Tim Karang Taruna sudah mengecek lokasi dan berkoordinasi dengan pengurus untuk penanganan."
            db.session.add(RiwayatStatus(pengaduan_id=ticket.id, aktor_id=manager.id, status_lama="DIPROSES", status_baru="DIPROSES",
                                        catatan="Ditugaskan kepada Rizky Ramadhan (Karang Taruna).", created_at=date + timedelta(minutes=20)))
            db.session.add(TindakLanjut(pengaduan_id=ticket.id, petugas_id=assigned, catatan=note, created_at=date + timedelta(minutes=40)))
            db.session.add(RiwayatStatus(pengaduan_id=ticket.id, aktor_id=assigned, status_lama="DIPROSES", status_baru="DIPROSES",
                                        catatan=note, created_at=date + timedelta(minutes=40)))
        if status == "SELESAI":
            db.session.add(RiwayatStatus(pengaduan_id=ticket.id, aktor_id=manager.id, status_lama="DIPROSES", status_baru="SELESAI",
                                        catatan="Penanganan selesai. Fasilitas sudah dapat digunakan kembali. Terima kasih atas kepedulian warga.", created_at=ticket.selesai_at))
        db.session.add(Notifikasi(user_id=reporter.id, pengaduan_id=ticket.id, pesan=f"Pembaruan pengaduan: {title}.", created_at=date + timedelta(hours=1)))
        created += 1
    db.session.commit()
    click.echo(f"Seed selesai: {created} tiket baru. Data lama dan password tidak ditimpa.")
    click.echo("Akun: admin, rw, rt, rt02, karangtaruna, warga, warga02, pending @siwarga.id")
    click.echo("Password: nilai DEMO_PASSWORD pada .env (tidak ditampilkan di log).")
