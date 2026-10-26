import json
from pathlib import Path

import click
from flask import current_app
from flask.cli import with_appcontext
from sqlalchemy import select

from .image_variants import render_variants
from .models import Lampiran, db
from .uploads import atomic_write, variant_filename


@click.command("upgrade-safe")
@with_appcontext
def upgrade_safe():
    import os
    from flask_migrate import upgrade
    from scripts.backup import maintenance_lock

    path = os.getenv("MAINTENANCE_LOCK", str(Path(current_app.instance_path) / "maintenance.lock"))
    with maintenance_lock(path):
        upgrade(directory=str(Path(current_app.root_path).parent / "migrations"))


@click.command("backfill-photos")
@click.option("--after-id", default=0, type=click.IntRange(min=0))
@click.option("--batch-size", default=100, type=click.IntRange(1, 1000))
@with_appcontext
def backfill_photos(after_id, batch_size):
    folder = Path(current_app.config["UPLOAD_FOLDER"])
    written = skipped = failed = 0
    while True:
        rows = db.session.execute(select(Lampiran.id, Lampiran.nama_tersimpan).where(Lampiran.id > after_id)
                                  .order_by(Lampiran.id).limit(batch_size)).all()
        if not rows:
            break
        for attachment_id, stored in rows:
            after_id = attachment_id
            try:
                missing = [name for name in ("thumbnail", "display") if not (folder / variant_filename(stored, name)).is_file()]
                if not missing:
                    skipped += 1
                    continue
                variants = render_variants((folder / stored).read_bytes())
                for name in missing:
                    atomic_write(folder / variant_filename(stored, name), variants[name])
                written += 1
            except (OSError, ValueError) as error:
                failed += 1
                click.echo(f"Attachment {attachment_id}: {type(error).__name__}", err=True)
        db.session.remove()
    click.echo(json.dumps(dict(written=written, skipped=skipped, failed=failed, last_id=after_id)))
    if failed:
        raise click.ClickException("Ada foto gagal diproses; perbaiki file sumber dan ulangi tanpa --after-id.")
