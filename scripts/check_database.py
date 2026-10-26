import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text


def main():
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            version, database = connection.execute(text("SELECT VERSION(), DATABASE()")).one()
            if not version.startswith("8.") or "MariaDB" in version:
                raise SystemExit("SiWarga requires MySQL 8, not MariaDB or another database.")
            print(f"MySQL {version} connected; database: {database}.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
