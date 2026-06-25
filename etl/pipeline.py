from etl.config import settings
from etl.extract import read_csvs
from etl.load import load_tables
from etl.models import build_analytics_tables
from etl.transform import transform
from etl.views import create_views


def main() -> None:
    print(f"Reading CSVs from: {settings.resolved_data_dir}")
    raw_data = read_csvs(settings.resolved_data_dir)

    print("Transforming raw data...")
    raw_tables = transform(raw_data)

    print(f"Loading raw tables into schema: {settings.db_schema}")
    load_tables(raw_tables, settings.database_url, settings.db_schema, drop_schema=True)

    print("Building analytics tables...")
    analytics_tables = build_analytics_tables(raw_tables)

    print("Loading analytics tables...")
    load_tables(analytics_tables, settings.database_url, settings.db_schema, drop_schema=False)

    print("Creating views...")
    create_views(settings.database_url, settings.db_schema)

    print("Pipeline finished successfully.")


if __name__ == "__main__":
    main()
