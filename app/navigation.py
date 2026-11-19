from flask import abort, request


MAX_PAGE = 10000


def requested_page():
    value = request.args.get("page", "1")
    if not value.isascii() or not value.isdigit() or len(value) > 5:
        abort(400, description="Nomor halaman tidak valid.")
    page = int(value)
    if not 1 <= page <= MAX_PAGE:
        abort(400, description=f"Nomor halaman harus antara 1 dan {MAX_PAGE}.")
    return page
