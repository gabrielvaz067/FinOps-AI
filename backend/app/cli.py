import argparse
import json

from backend.app.config import PROJECT_ROOT, Settings
from backend.app.db import make_engine, session_factory
from backend.app.detection import run_pipeline
from backend.app.migrations import upgrade
from backend.app.synthetic import seed_database


def main():
    parser = argparse.ArgumentParser(description="FinOps AI: preparar demonstração sintética")
    parser.add_argument("command", choices=["init", "migrate", "pipeline"])
    parser.add_argument("--count", type=int, default=50_000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    (PROJECT_ROOT / "database").mkdir(exist_ok=True)
    engine = make_engine(Settings().database_url)
    upgrade(engine)
    with session_factory(engine)() as session:
        if args.command == "init":
            print(json.dumps(seed_database(session, args.seed, args.count)))
        if args.command in {"init", "pipeline"}:
            run = run_pipeline(session)
            print(
                json.dumps(
                    {
                        "run_id": run.id,
                        "model_version": run.model_version,
                        "metrics": run.metrics,
                        "metadata": run.metadata_json,
                    },
                    indent=2,
                )
            )
    engine.dispose()


if __name__ == "__main__":
    main()
