"""Reproducible ledger. Injection labels never enter the transaction feature table."""

from datetime import datetime, timedelta

import numpy as np
from sqlalchemy import func, insert, select
from sqlalchemy.orm import Session

from backend.app.models import Account, Channel, Dataset, SyntheticLabel, Transaction

GENERATOR_VERSION = "synthetic-v1"
ACCOUNT_NAMES = [
    "Aurora Commerce",
    "Atlas Serviços",
    "Horizonte Digital",
    "Nexo Varejo",
    "Órbita Studio",
    "Prisma Tech",
    "Raiz Mercado",
    "Vértice Logística",
]
CHANNEL_NAMES = ["Pix", "Cartão", "Boleto", "Transferência"]


def generate(seed: int = 42, count: int = 50_000) -> tuple[list[dict], list[dict]]:
    if count < 2_000 or count > 200_000:
        raise ValueError("Use de 2.000 a 200.000 transações.")
    rng = np.random.default_rng(seed)
    per_event = max(20, count // 250)
    base_count = count - 5 * per_event
    start = datetime(2025, 1, 1)
    rows: list[dict] = []
    labels: list[dict] = []
    # Weekday and annual seasonality; business-hour concentration and account ticket sizes.
    days = np.arange(365)
    weights = np.array([1.0 if (start + timedelta(days=int(d))).weekday() < 5 else 0.55 for d in days])
    weights *= 1 + 0.18 * np.sin(days / 365 * 2 * np.pi)
    weights /= weights.sum()
    sampled_days = rng.choice(days, size=base_count, p=weights)
    for i, day in enumerate(sampled_days):
        account = int(rng.integers(1, 9))
        channel = int(rng.choice([1, 2, 3, 4], p=[0.43, 0.32, 0.15, 0.10]))
        hour = int(rng.integers(8, 22)) if rng.random() > 0.01 else int(rng.integers(0, 6))
        amount = int(max(100, rng.lognormal(9.1 + account * 0.07 + channel * 0.10, 0.65)))
        rows.append(
            {
                "id": i + 1,
                "account_id": account,
                "channel_id": channel,
                "occurred_at": start
                + timedelta(days=int(day), hours=hour, seconds=int(rng.integers(0, 3600))),
                "amount_cents": amount,
                "direction": "inflow" if rng.random() < 0.64 else "outflow",
                "status": "approved" if rng.random() < 0.965 else "declined",
                "payment_ref": f"PAY-{seed}-{i + 1:06d}",
            }
        )
    for kind in ["extreme_amount", "unusual_hour", "duplicate", "volume_spike", "approval_drop"]:
        for j in range(per_event):
            row = dict(rows[int(rng.integers(0, base_count))])
            row["id"] = len(rows) + 1
            row["payment_ref"] = f"PAY-{seed}-{row['id']:06d}"
            row["occurred_at"] = start + timedelta(days=int(rng.integers(243, 365)), hours=12, seconds=j)
            row["status"] = "approved"
            if kind == "extreme_amount":
                row["amount_cents"] *= 45
            elif kind == "unusual_hour":
                row["occurred_at"] = row["occurred_at"].replace(hour=2)
            elif kind == "duplicate":
                # Same business reference/amount/account, observed after the original.
                original = rows[(j * 7) % base_count]
                row.update(
                    {
                        key: original[key]
                        for key in ["account_id", "channel_id", "amount_cents", "payment_ref", "direction"]
                    }
                )
                row["occurred_at"] = max(row["occurred_at"], original["occurred_at"] + timedelta(seconds=30))
                if row["occurred_at"].year > 2025:
                    row["occurred_at"] = datetime(2025, 12, 31, 23, 59, 59)
            elif kind == "volume_spike":
                row.update(
                    account_id=2,
                    channel_id=1,
                    occurred_at=datetime(2025, 10, 15, 14) + timedelta(days=j % 4, seconds=j),
                )
            elif kind == "approval_drop":
                row.update(
                    account_id=5,
                    channel_id=2,
                    status="declined",
                    occurred_at=datetime(2025, 11, 10, 12) + timedelta(days=j % 4, seconds=j),
                )
            rows.append(row)
            labels.append({"transaction_id": row["id"], "event_type": kind})
    return rows, labels


def seed_database(session: Session, seed: int = 42, count: int = 50_000) -> dict:
    key = f"{GENERATOR_VERSION}-{seed}-{count}"
    existing = session.scalar(select(Dataset))
    if existing:
        actual = session.scalar(select(func.count()).select_from(Transaction))
        if existing.id != key or actual != count:
            raise ValueError(
                "Dataset diferente ou incompleto. Use outro DATABASE_URL; a carga não apaga dados."
            )
        return {"dataset": key, "transactions": actual, "created": False}
    rows, labels = generate(seed, count)
    session.execute(
        insert(Account),
        [{"id": i + 1, "name": name, "segment": "Empresa sintética"} for i, name in enumerate(ACCOUNT_NAMES)],
    )
    session.execute(insert(Channel), [{"id": i + 1, "name": name} for i, name in enumerate(CHANNEL_NAMES)])
    session.flush()
    for offset in range(0, len(rows), 2000):
        session.execute(insert(Transaction), rows[offset : offset + 2000])
    session.execute(insert(SyntheticLabel), labels)
    session.add(Dataset(id=key, seed=seed, row_count=count))
    session.commit()
    return {"dataset": key, "transactions": count, "created": True}
