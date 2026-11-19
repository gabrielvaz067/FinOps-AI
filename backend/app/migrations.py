from alembic import command
from alembic.config import Config

from backend.app.config import PROJECT_ROOT


def upgrade(engine):
    config = Config(str(PROJECT_ROOT / "database" / "alembic.ini"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
