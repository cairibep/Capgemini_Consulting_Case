from pathlib import Path

from sqlalchemy import text

from etl.load import get_engine

SQL_DIR = Path(__file__).resolve().parents[1] / "sql"


def create_views(database_url: str, schema: str) -> None:
    sql = (SQL_DIR / "views.sql").read_text(encoding="utf-8")
    engine = get_engine(database_url)

    with engine.begin() as conn:
        for statement in [s.strip() for s in sql.format(schema=schema).split(";") if s.strip()]:
            conn.execute(text(statement))
