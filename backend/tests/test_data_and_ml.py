import pandas as pd
import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from backend.app.db import make_engine, session_factory
from backend.app.detection import (
    FEATURES,
    SPLIT,
    aggregate_transactions,
    detect,
    feature_matrix,
    metrics_for,
    run_pipeline,
)
from backend.app.migrations import upgrade
from backend.app.models import Anomaly, SyntheticLabel, Transaction
from backend.app.synthetic import generate, seed_database


def test_generator_reproducible_and_labels_complete():
    first, labels = generate(count=5000)
    second, second_labels = generate(count=5000)
    assert first == second and labels == second_labels
    assert len(first) == 5000
    assert {row["occurred_at"].month for row in first} == set(range(1, 13))
    assert len({row["id"] for row in first}) == len(first)
    assert len({label["event_type"] for label in labels}) == 5
    assert all("event_type" not in row for row in first)
    assert all(row["amount_cents"] > 0 for row in first)
    assert first != generate(seed=43, count=5000)[0]


def test_idempotent_load_and_pipeline(session):
    before = session.scalar(select(func.count()).select_from(Anomaly))
    assert seed_database(session, count=5000)["created"] is False
    run = run_pipeline(session)
    assert run.id == run_pipeline(session).id
    assert session.scalar(select(func.count()).select_from(Transaction)) == 5000
    assert session.scalar(select(func.count()).select_from(Anomaly)) == before
    with pytest.raises(ValueError, match="Dataset diferente"):
        seed_database(session, seed=99, count=5000)


def test_migration_idempotence_and_referential_integrity(tmp_path):
    engine = make_engine(f"sqlite:///{(tmp_path / 'integrity.db').as_posix()}")
    upgrade(engine)
    upgrade(engine)
    with session_factory(engine)() as session:
        session.add(SyntheticLabel(transaction_id=999, event_type="missing"))
        with pytest.raises(IntegrityError):
            session.commit()
    engine.dispose()


def test_metrics_have_known_confusion_matrix():
    result = metrics_for([True, True, False, False], [True, False, True, False])
    assert result == {
        "precision": 0.5,
        "recall": 0.5,
        "f1": 0.5,
        "true_positives": 1,
        "false_positives": 1,
        "false_negatives": 1,
        "true_negatives": 1,
    }
    assert metrics_for([False], [False])["f1"] == 0


def test_labels_cannot_change_predictions():
    rows, labels = generate(count=5000)
    frame, truth = pd.DataFrame(rows), pd.DataFrame(labels)
    predictions, metrics, metadata = detect(frame, truth)
    changed_predictions, changed_metrics, _ = detect(frame, truth.iloc[:0])
    assert predictions == changed_predictions
    assert metrics != changed_metrics
    assert metadata["features"] == FEATURES
    assert all(item["day"] >= SPLIT.date() for item in predictions)
    # Explicitly separate independently evaluated detectors and their union.
    assert set(metrics) == {"rules", "isolation_forest", "combined"}
    assert metrics["combined"]["recall"] > 0.5
    assert all(value["detected"] > 0 for value in metadata["event_recall"].values())


def test_future_changes_cannot_change_training_features():
    rows, _ = generate(count=5000)
    frame = pd.DataFrame(rows)
    before_buckets = aggregate_transactions(frame)
    _, before = feature_matrix(before_buckets)
    future = pd.to_datetime(frame.occurred_at) >= SPLIT
    frame.loc[future, "amount_cents"] *= 100
    after_buckets = aggregate_transactions(frame)
    _, after = feature_matrix(after_buckets)
    pd.testing.assert_frame_equal(
        before.loc[before_buckets.day < SPLIT], after.loc[after_buckets.day < SPLIT]
    )


def test_duplicate_does_not_retroactively_mark_first_payment():
    rows, _ = generate(count=2000)
    first = rows[0] | {"id": 1, "occurred_at": pd.Timestamp("2025-01-01T12:00:00")}
    second = first | {"id": 2, "occurred_at": pd.Timestamp("2025-10-01T12:00:00")}
    buckets = aggregate_transactions(pd.DataFrame([second, first]))
    assert buckets.iloc[0].duplicate_rate == 0
    assert buckets.iloc[1].duplicate_rate == 1
