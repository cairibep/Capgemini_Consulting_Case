from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv
import os


load_dotenv(override=True)


@dataclass(frozen=True)
class Settings:
    base_dir: Path = Path(__file__).resolve().parents[1]
    data_dir: Path = Path(
        os.getenv("DATA_DIR", "../../work/consulting_case/Consulting_Case/data")
    )
    db_host: str = os.getenv("POSTGRES_HOST", "localhost")
    db_port: str = os.getenv("POSTGRES_PORT", "55432")
    db_name: str = os.getenv("POSTGRES_DB", "olist")
    db_user: str = os.getenv("POSTGRES_USER", "olist")
    db_password: str = os.getenv("POSTGRES_PASSWORD", "olist")
    db_schema: str = os.getenv("POSTGRES_SCHEMA", "analytics")

    @property
    def resolved_data_dir(self) -> Path:
        if self.data_dir.is_absolute():
            return self.data_dir
        return (self.base_dir / self.data_dir).resolve()

    @property
    def database_url(self) -> str:
        user = quote_plus(self.db_user)
        password = quote_plus(self.db_password)
        connection_string = f"postgresql+psycopg://{user}:{password}@{self.db_host}:{self.db_port}/{self.db_name}"
        print(connection_string)
        return connection_string

settings = Settings()
