import warnings
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from flask import abort, current_app
from flask_login import current_user
from PIL import Image, ImageOps, UnidentifiedImageError
from werkzeug.utils import secure_filename

from .models import Lampiran, db

MAX_FILE_SIZE = 3 * 1024 * 1024
Image.MAX_IMAGE_PIXELS = 20_000_000
FORMATS = {"jpg": "JPEG", "jpeg": "JPEG", "png": "PNG", "webp": "WEBP"}
MIME_TYPES = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}


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
                with Image.open(BytesIO(data)) as image:
                    detected = image.format
                    if detected != FORMATS[extension] or file.mimetype != MIME_TYPES[detected]:
                        abort(400, description="Ekstensi, tipe konten, dan isi foto tidak cocok.")
                    image.load()
                    clean = ImageOps.exif_transpose(image)
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
        prepared.append((original, f"{uuid4().hex}.{extension}", content))
    return prepared


def commit_with_uploads(ticket, prepared, kind):
    saved = []
    try:
        db.session.flush()
        folder = Path(current_app.config["UPLOAD_FOLDER"])
        for original, stored, content in prepared:
            destination = folder / stored
            destination.write_bytes(content)
            saved.append(destination)
            db.session.add(Lampiran(pengaduan_id=ticket.id, uploader_id=current_user.id,
                                    nama_asli=original, nama_tersimpan=stored, jenis=kind))
        db.session.commit()
    except Exception:
        db.session.rollback()
        for destination in saved:
            destination.unlink(missing_ok=True)
        raise
