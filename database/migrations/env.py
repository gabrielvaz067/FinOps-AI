from alembic import context
from sqlalchemy import engine_from_config, pool

from backend.app.config import Settings
from backend.app.models import Base

config = context.config
# A supplied connection lets tests/CLI use the same transaction and database.
connection = config.attributes.get("connection")


def migrate(conn):
    context.configure(connection=conn, target_metadata=Base.metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    context.configure(url=Settings().database_url, target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
elif connection is not None:
    migrate(connection)
else:
    section = config.get_section(config.config_ini_section) or {}
    section["sqlalchemy.url"] = Settings().database_url
    engine = engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with engine.connect() as conn:
        migrate(conn)
