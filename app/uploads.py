import os
import warnings
import click
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from flask import abort, current_app
from flask_login import current_user
from PIL import Image, ImageOps, UnidentifiedImageError
from werkzeug.utils import secure_filename

from .models import Lampiran, db
from .image_variants import render_variants

MAX_FILE_SIZE = 3 * 1024 * 1024
Image.MAX_IMAGE_PIXELS = 20_000_000
VARIANTS = {"thumbnail": (480, 60000), "display": (1280, 220000)}
FORMATS = {"jpg": "JPEG", "jpeg": "JPEG", "png": "PNG", "webp": "WEBP"}
MIME_TYPES = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}


def variant_filename(stored, variant):
    if variant not in VARIANTS:
        raise ValueError("Unknown image variant")
    return f"{Path(stored).stem}.{variant}.webp"


def atomic_write(destination, content):
    temporary = destination.with_name(f".{uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, destination)
        if os.name == "posix":
            descriptor = os.open(destination.parent, os.O_DIRECTORY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
    finally:
        temporary.unlink(missing_ok=True)


def validate_uploads(files):
    files = [file for file in files if file and file.filename]
    if len(files) > 3:
        abort(400, description="Maksimal 3 foto dalam satu pengiriman.")
    prepared = []
    for file in files:
        original = secure_filename(file.filename)[:220]
        extension = original.rsplit(".", 1)[-1].lower() if "." in original else ""
        if extension not in FORMATS:
            abort(400, description="Foto harus berformat JPG, PNG, atau WebP.")
        data = file.stream.read(MAX_FILE_SIZE + 1)
        if not data or len(data) > MAX_FILE_SIZE:
            abort(400, description="Setiap foto harus berukuran maksimal 3 MB dan tidak boleh kosong.")
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(BytesIO(data), formats=[FORMATS[extension]]) as image:
                    detected = image.format
                    if detected != FORMATS[extension] or file.mimetype != MIME_TYPES[detected]:
                        abort(400, description="Ekstensi, tipe konten, dan isi foto tidak cocok.")
                    image.load()
                    clean = ImageOps.exif_transpose(image)
                    if detected == "PNG" and clean.mode == "I":
                        clean = clean.convert("I;16")
                    if detected == "JPEG":
                        clean = clean.convert("RGB")
                    elif detected == "WEBP":
                        clean = clean.convert("RGBA" if "A" in clean.getbands() else "RGB")
                    clean.info.clear()
                    output = BytesIO()
                    clean.save(output, format=detected)
                    content = output.getvalue()
                    if len(content) > MAX_FILE_SIZE:
                        abort(400, description="Foto setelah diproses melebihi 3 MB. Gunakan foto yang lebih kecil.")
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
            abort(400, description="Foto tidak valid, rusak, atau memiliki resolusi terlalu besar.")
        variants = render_variants(content)
        prepared.append((original, f"{uuid4().hex}.{extension}", content, variants))
    return prepared


def commit_with_uploads(ticket, prepared, kind):
    saved = []
    try:
        db.session.flush()
        folder = Path(current_app.config["UPLOAD_FOLDER"])
        for original, stored, content, variants in prepared:
            destination = folder / stored
            saved.append(destination)
            atomic_write(destination, content)
            for variant, rendered in variants.items():
                destination = folder / variant_filename(stored, variant)
                saved.append(destination)
                atomic_write(destination, rendered)
            db.session.add(Lampiran(pengaduan_id=ticket.id, uploader_id=current_user.id,
                                    nama_asli=original, nama_tersimpan=stored, jenis=kind))
        db.session.commit()
    except Exception:
        db.session.rollback()
        for destination in saved:
            try:
                destination.unlink(missing_ok=True)
            except OSError:
                current_app.logger.error("Upload cleanup failed for %s", destination.name)
        raise
