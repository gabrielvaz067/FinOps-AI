"""Daily account/channel detection; all baselines are fitted before the holdout."""

from datetime import date

import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import IsolationForest
from sklearn.metrics import confusion_matrix, precision_recall_fscore_support
from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from backend.app.models import Anomaly, Dataset, PipelineRun, SyntheticLabel, Transaction

MODEL_VERSION = "iforest-rules-v1"
SPLIT = pd.Timestamp("2025-09-01")
KEYS = ["account_id", "channel_id", "day"]
FEATURES = ["count_ratio", "amount_ratio", "max_ratio", "approval_rate", "night_rate", "duplicate_rate"]


def aggregate_transactions(frame: pd.DataFrame) -> pd.DataFrame:
    """Uses only observed ledger fields; windows close at the end of each day."""
    data = frame.sort_values(["occurred_at", "id"]).copy()
    data["occurred_at"] = pd.to_datetime(data["occurred_at"])
    data["day"] = data.occurred_at.dt.normalize()
    data["approved"] = (data.status == "approved").astype(int)
    data["night"] = (data.occurred_at.dt.hour < 6).astype(int)
    # keep='first' uses only earlier observations; never mark the first occurrence retroactively.
    data["duplicate"] = data.duplicated(["account_id", "channel_id", "payment_ref"], keep="first").astype(int)
    result = (
        data.groupby(KEYS, sort=True)
        .agg(
            count=("id", "size"),
            total_cents=("amount_cents", "sum"),
            max_cents=("amount_cents", "max"),
            approval_rate=("approved", "mean"),
            night_rate=("night", "mean"),
            duplicate_rate=("duplicate", "mean"),
        )
        .reset_index()
    )
    return result


def feature_matrix(buckets: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    train = buckets[buckets.day < SPLIT]
    baseline = (
        train.groupby(["account_id", "channel_id"])[["count", "total_cents", "max_cents"]]
        .median()
        .clip(lower=1)
    )
    merged = buckets.merge(baseline.add_suffix("_baseline"), on=["account_id", "channel_id"], how="left")
    for column in ["count", "total_cents", "max_cents"]:
        merged[f"{column}_baseline"] = merged[f"{column}_baseline"].fillna(float(train[column].median()))
    merged["count_ratio"] = merged["count"] / merged.count_baseline
    merged["amount_ratio"] = merged.total_cents / merged.total_cents_baseline
    merged["max_ratio"] = merged.max_cents / merged.max_cents_baseline
    matrix = merged[FEATURES].copy()
    matrix[["count_ratio", "amount_ratio", "max_ratio"]] = np.log1p(
        matrix[["count_ratio", "amount_ratio", "max_ratio"]]
    )
    return merged, matrix


def rule_reasons(row) -> list[str]:
    reasons = []
    if row.max_ratio > 9:
        reasons.append("Valor extremo: maior transação supera 9× a referência histórica.")
    if row.count_ratio > 6 and row.count >= 15:
        reasons.append("Pico de volume: quantidade supera 6× a referência histórica.")
    if row.duplicate_rate > 0:
        reasons.append("Referência de pagamento repetida em observações anteriores.")
    if row.approval_rate < 0.65 and row.count >= 8:
        reasons.append("Queda de aprovação: menos de 65% em pelo menos 8 tentativas.")
    if row.night_rate >= 0.15:
        reasons.append("Horário atípico: pelo menos 15% das transações entre 00h e 06h.")
    return reasons


def metrics_for(truth, predicted) -> dict:
    precision, recall, f1, _ = precision_recall_fscore_support(
        truth, predicted, average="binary", zero_division=0
    )
    tn, fp, fn, tp = confusion_matrix(truth, predicted, labels=[False, True]).ravel()
    return {
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "true_positives": int(tp),
        "false_positives": int(fp),
        "false_negatives": int(fn),
        "true_negatives": int(tn),
    }


def detect(frame: pd.DataFrame, labels: pd.DataFrame) -> tuple[list[dict], dict, dict]:
    buckets = aggregate_transactions(frame)
    merged, matrix = feature_matrix(buckets)
    training = merged.day < SPLIT
    if training.sum() < 100 or (~training).sum() < 20:
        raise ValueError("Histórico insuficiente para separar treino e avaliação.")
    model = IsolationForest(n_estimators=160, contamination=0.02, random_state=42, n_jobs=1)
    model.fit(matrix.loc[training])
    scores = -model.decision_function(matrix.loc[~training])
    test = merged.loc[~training].copy().reset_index(drop=True)
    test["score"] = scores
    test["ml_detected"] = scores > 0
    test["reasons"] = [rule_reasons(row) for row in test.itertuples()]
    test["rule_detected"] = test.reasons.map(bool)
    # Ground truth is joined only AFTER fit/predict. It cannot affect features or thresholds.
    ground = frame[["id", "account_id", "channel_id", "occurred_at"]].merge(
        labels, left_on="id", right_on="transaction_id"
    )
    ground["day"] = pd.to_datetime(ground.occurred_at).dt.normalize()
    labeled_keys = set(map(tuple, ground[KEYS].to_numpy()))
    truth = np.array([tuple(row) in labeled_keys for row in test[KEYS].to_numpy()])
    union = test.ml_detected | test.rule_detected
    metrics = {
        "isolation_forest": metrics_for(truth, test.ml_detected),
        "rules": metrics_for(truth, test.rule_detected),
        "combined": metrics_for(truth, union),
    }
    event_recall = {}
    for kind, group in ground.groupby("event_type"):
        keys = set(map(tuple, group[KEYS].to_numpy()))
        event_mask = np.array([tuple(row) in keys for row in test[KEYS].to_numpy()])
        event_recall[str(kind)] = {
            "buckets": int(event_mask.sum()),
            "detected": int((event_mask & union).sum()),
        }
    result = []
    for row in test.loc[union].itertuples():
        reasons = list(row.reasons)
        if row.ml_detected:
            reasons.append("Isolation Forest identificou um perfil multivariado incomum.")
        critical = row.max_ratio > 15 or (row.approval_rate < 0.5 and row.count >= 15) or row.count_ratio > 10
        evidence = {
            "transaction_count": int(row.count),
            "total_cents": int(row.total_cents),
            "max_cents": int(row.max_cents),
            "approval_rate": float(row.approval_rate),
            "night_rate": float(row.night_rate),
            "duplicate_rate": float(row.duplicate_rate),
            "count_baseline": float(row.count_baseline),
            "max_cents_baseline": float(row.max_cents_baseline),
            "count_ratio": float(row.count_ratio),
            "max_ratio": float(row.max_ratio),
        }
        result.append(
            {
                "account_id": int(row.account_id),
                "channel_id": int(row.channel_id),
                "day": row.day.date(),
                "severity": "critical" if critical else ("high" if row.rule_detected else "medium"),
                "score": float(row.score),
                "ml_detected": bool(row.ml_detected),
                "rule_detected": bool(row.rule_detected),
                "reasons": reasons,
                "evidence": evidence,
                "model_version": MODEL_VERSION,
            }
        )
    metadata = {
        "train_buckets": int(training.sum()),
        "test_buckets": int((~training).sum()),
        "positive_buckets": int(truth.sum()),
        "features": FEATURES,
        "contamination": 0.02,
        "estimators": 160,
        "seed": 42,
        "sklearn": sklearn.__version__,
        "evaluation_unit": "account/channel/day",
        "event_recall": event_recall,
        "train_start": "2025-01-01",
        "test_start": "2025-09-01",
        "test_end": "2025-12-31",
    }
    return result, metrics, metadata


def run_pipeline(session: Session) -> PipelineRun:
    dataset = session.scalar(select(Dataset))
    if dataset is None:
        raise ValueError("Execute a carga sintética antes do pipeline.")
    fingerprint = f"{dataset.id}:{MODEL_VERSION}"
    existing = session.scalar(select(PipelineRun).where(PipelineRun.fingerprint == fingerprint))
    if existing:
        return existing
    frame = pd.read_sql(select(Transaction), session.connection())
    labels = pd.read_sql(select(SyntheticLabel), session.connection())
    anomalies, metrics, metadata = detect(frame, labels)
    run = PipelineRun(
        fingerprint=fingerprint,
        model_version=MODEL_VERSION,
        train_end=date(2025, 8, 31),
        metrics=metrics,
        metadata_json=metadata,
    )
    session.add(run)
    session.flush()
    if anomalies:
        session.execute(insert(Anomaly), [{**item, "run_id": run.id} for item in anomalies])
    session.commit()
    return run
