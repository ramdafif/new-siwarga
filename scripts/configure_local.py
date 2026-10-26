import secrets
from pathlib import Path

import pymysql

ROOT = Path(__file__).resolve().parent.parent
PORT = 13308


def main():
    env_path = ROOT / ".env"
    root_env = ROOT / ".local" / "mysql.env"
    if env_path.exists() or root_env.exists():
        raise SystemExit("Configuration already exists; refusing to overwrite credentials.")
    root_password = secrets.token_urlsafe(32)
    app_password = secrets.token_urlsafe(24)
    test_password = secrets.token_urlsafe(24)
    demo_password = secrets.token_urlsafe(12)
    def quoted(value):
        return "'" + pymysql.converters.escape_string(value) + "'"

    statements = [
        "CREATE DATABASE IF NOT EXISTS siwarga_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;",
        "CREATE DATABASE IF NOT EXISTS siwarga_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;",
        f"CREATE USER 'siwarga'@'127.0.0.1' IDENTIFIED BY {quoted(app_password)};",
        "GRANT ALL PRIVILEGES ON siwarga_db.* TO 'siwarga'@'127.0.0.1';",
        f"CREATE USER 'siwarga_test'@'127.0.0.1' IDENTIFIED BY {quoted(test_password)};",
        "GRANT ALL PRIVILEGES ON siwarga_test.* TO 'siwarga_test'@'127.0.0.1';",
        f"ALTER USER 'root'@'localhost' IDENTIFIED BY {quoted(root_password)};",
        f"CREATE USER 'root'@'127.0.0.1' IDENTIFIED BY {quoted(root_password)};",
        "GRANT ALL PRIVILEGES ON *.* TO 'root'@'127.0.0.1' WITH GRANT OPTION;",
    ]
    (ROOT / ".local" / "bootstrap.sql").write_text("\n".join(statements) + "\n", encoding="utf-8")
    root_env.write_text(f"MYSQL_ROOT_PASSWORD={root_password}\nMYSQL_PORT={PORT}\n", encoding="utf-8")
    env_path.write_text(
        f"SECRET_KEY={secrets.token_urlsafe(48)}\n"
        f"DATABASE_URL=mysql+pymysql://siwarga:{app_password}@127.0.0.1:{PORT}/siwarga_db?charset=utf8mb4\n"
        f"TEST_DATABASE_URL=mysql+pymysql://siwarga_test:{test_password}@127.0.0.1:{PORT}/siwarga_test?charset=utf8mb4\n"
        f"DEMO_PASSWORD={demo_password}\nSESSION_COOKIE_SECURE=false\n",
        encoding="utf-8",
    )
    print(f"Prepared isolated MySQL on 127.0.0.1:{PORT}. Start it once with --init-file pointing to .local/bootstrap.sql, then remove that file.")


if __name__ == "__main__":
    main()
