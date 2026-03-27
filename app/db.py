from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DB_PATH = DATA_DIR / "app.db"

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def ensure_columns(engine, table_name: str, columns: dict[str, str]) -> None:
    with engine.connect() as connection:
        result = connection.execute(f"PRAGMA table_info({table_name});")
        existing = {row[1] for row in result.fetchall()}
        for col_name, col_type in columns.items():
            if col_name not in existing:
                connection.execute(
                    f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type};"
                )
