import logging
import secrets
import threading
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from datetime import time as daytime
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from backend.app.automation import pending_query, run_automation
from backend.app.config import PROJECT_ROOT, Settings
from backend.app.db import make_engine, session_factory
from backend.app.detection import run_pipeline
from backend.app.investigation import InvestigationRequest, deterministic, history, investigate
from backend.app.models import (
    Account,
    Anomaly,
    AutomationRun,
    Channel,
    Notification,
    NotificationAttempt,
    PipelineRun,
    Transaction,
)

logger = logging.getLogger("finops")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s finops %(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)
logger.propagate = False


class Filters(BaseModel):
    start: date | None = None
    end: date | None = None
    account_id: int | None = Field(default=None, ge=1)
    channel_id: int | None = Field(default=None, ge=1)


class AutomationRequest(BaseModel):
    anomaly_ids: list[Annotated[int, Field(ge=1)]] | None = Field(default=None, max_length=100)


Approach = Literal["rules", "isolation_forest", "combined"]


def by_approach(query, approach: Approach):
    if approach == "rules":
        return query.where(Anomaly.rule_detected.is_(True))
    if approach == "isolation_forest":
        return query.where(Anomaly.ml_detected.is_(True))
    return query


def filtered(query, model, filters: Filters):
    if filters.start and filters.end and filters.start > filters.end:
        raise HTTPException(422, "A data inicial deve preceder a data final.")
    column = model.occurred_at if model is Transaction else model.day
    if filters.start:
        query = query.where(column >= filters.start)
    if filters.end:
        if filters.end == date.max:
            upper = datetime.combine(filters.end, daytime.max) if model is Transaction else filters.end
            query = query.where(column <= upper)
        else:
            query = query.where(column < filters.end + timedelta(days=1))
    if filters.account_id:
        query = query.where(model.account_id == filters.account_id)
    if filters.channel_id:
        query = query.where(model.channel_id == filters.channel_id)
    return query


def serialize(obj):
    return {column.name: getattr(obj, column.name) for column in obj.__table__.columns}


def create_app(settings: Settings | None = None, engine=None) -> FastAPI:
    settings = settings or Settings()
    if settings.public_demo and (settings.gemini_api_key or settings.notification_mode != "simulated"):
        raise ValueError("A demonstração pública exige Gemini desativado e notificações simuladas.")
    if settings.finops_admin_key and len(settings.finops_admin_key) < 24:
        raise ValueError("FINOPS_ADMIN_KEY deve ter pelo menos 24 caracteres.")
    owned_engine = engine is None
    engine = engine or make_engine(settings.database_url)
    sessions = session_factory(engine)
    locks = {name: threading.Lock() for name in ["pipeline", "analysis", "automation"]}
    requests: dict[str, deque] = defaultdict(deque)
    rate_lock = threading.Lock()

    @asynccontextmanager
    async def lifespan(_):
        yield
        if owned_engine:
            engine.dispose()

    app = FastAPI(
        title="FinOps AI",
        version="1.0.0",
        description=(
            "Monitoramento de dados sintéticos. Anomalias não comprovam fraude. "
            + (
                "Demonstração pública somente de leitura."
                if settings.public_demo
                else "Leituras públicas; gravações exigem X-Admin-Key."
            )
        ),
        lifespan=lifespan,
    )
    app.state.engine = engine

    @app.middleware("http")
    async def headers_and_logging(request: Request, call_next):
        started = time.monotonic()
        request_id = secrets.token_hex(6)
        try:
            response = await call_next(request)
        except Exception:
            # Never log URLs, request bodies or exception strings containing credentials.
            logger.error("request_failed id=%s method=%s", request_id, request.method)
            response = JSONResponse(
                status_code=500,
                content={
                    "detail": "Erro interno. Consulte o identificador da requisição.",
                    "request_id": request_id,
                },
            )
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        if not request.url.path.startswith(("/docs", "/redoc")):
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
            )
        if request.url.path.startswith("/api"):
            response.headers["Cache-Control"] = "no-store"
        logger.info(
            "request id=%s method=%s status=%s duration_ms=%.1f",
            request_id,
            request.method,
            response.status_code,
            (time.monotonic() - started) * 1000,
        )
        return response

    def db():
        with sessions() as session:
            yield session

    DB = Annotated[Session, Depends(db)]

    def admin(request: Request, x_admin_key: Annotated[str | None, Header()] = None):
        identity = request.client.host if request.client else "unknown"
        now = time.monotonic()
        with rate_lock:
            # Bound memory even if a public reverse proxy supplies many clients.
            for key in list(requests):
                if not requests[key] or now - requests[key][-1] > 60:
                    del requests[key]
            if len(requests) >= 1024 and identity not in requests:
                raise HTTPException(429, "Limite de requisições. Aguarde um minuto.")
            queue = requests[identity]
            while queue and now - queue[0] > 60:
                queue.popleft()
            if len(queue) >= 12:
                raise HTTPException(429, "Limite de operações administrativas. Aguarde um minuto.")
            queue.append(now)
        if not settings.finops_admin_key:
            raise HTTPException(503, "Configure FINOPS_ADMIN_KEY no servidor para habilitar gravações.")
        if not x_admin_key or not secrets.compare_digest(
            x_admin_key.encode(), settings.finops_admin_key.encode()
        ):
            raise HTTPException(401, "Chave administrativa ausente ou inválida.")

    def get_anomaly(session: Session, anomaly_id: int) -> Anomaly:
        anomaly = session.get(Anomaly, anomaly_id)
        if anomaly is None:
            raise HTTPException(404, "Alerta não encontrado.")
        return anomaly

    @app.get("/api/health")
    def health(session: DB):
        session.execute(select(1))
        return {
            "status": "ok",
            "synthetic": True,
            "gemini_available": bool(settings.gemini_api_key),
            "notification_mode": settings.notification_mode,
            "public_demo": settings.public_demo,
        }

    @app.get("/api/options")
    def options(session: DB):
        lower, upper = session.execute(
            select(func.min(Transaction.occurred_at), func.max(Transaction.occurred_at))
        ).one()
        return {
            "accounts": [serialize(item) for item in session.scalars(select(Account).order_by(Account.id))],
            "channels": [serialize(item) for item in session.scalars(select(Channel).order_by(Channel.id))],
            "range": {"start": lower.date() if lower else None, "end": upper.date() if upper else None},
        }

    @app.get("/api/summary")
    def summary(session: DB, filters: Annotated[Filters, Query()], approach: Approach = "rules"):
        approved = Transaction.status == "approved"
        inflow = case((approved & (Transaction.direction == "inflow"), Transaction.amount_cents), else_=0)
        outflow = case((approved & (Transaction.direction == "outflow"), Transaction.amount_cents), else_=0)
        query = select(
            func.count(),
            func.coalesce(func.sum(inflow), 0),
            func.coalesce(func.sum(outflow), 0),
            func.coalesce(func.sum(case((approved, 1), else_=0)), 0),
        ).select_from(Transaction)
        count, incoming, outgoing, accepted = session.execute(filtered(query, Transaction, filters)).one()
        alerts, critical = session.execute(
            by_approach(
                filtered(
                    select(
                        func.count(),
                        func.coalesce(func.sum(case((Anomaly.severity == "critical", 1), else_=0)), 0),
                    ).select_from(Anomaly),
                    Anomaly,
                    filters,
                ),
                approach,
            )
        ).one()
        latest = session.scalar(select(PipelineRun).order_by(PipelineRun.id.desc()).limit(1))
        return {
            "transaction_count": count,
            "inflow_cents": incoming,
            "outflow_cents": outgoing,
            "net_cents": incoming - outgoing,
            "approval_rate": accepted / count if count else 0,
            "anomaly_count": alerts,
            "critical_count": critical,
            "pipeline": serialize(latest) if latest else None,
        }

    @app.get("/api/series")
    def series(session: DB, filters: Annotated[Filters, Query()]):
        day = func.date(Transaction.occurred_at)
        approved = Transaction.status == "approved"
        query = select(
            day.label("day"),
            func.count().label("count"),
            func.sum(
                case((approved & (Transaction.direction == "inflow"), Transaction.amount_cents), else_=0)
            ).label("inflow_cents"),
            func.sum(
                case((approved & (Transaction.direction == "outflow"), Transaction.amount_cents), else_=0)
            ).label("outflow_cents"),
        )
        return [
            dict(row)
            for row in session.execute(
                filtered(query, Transaction, filters).group_by(day).order_by(day)
            ).mappings()
        ]

    @app.get("/api/channels")
    def channels(session: DB, filters: Annotated[Filters, Query()]):
        query = select(
            Channel.name,
            func.count().label("count"),
            func.sum(Transaction.amount_cents).label("amount_cents"),
        ).join(Transaction, Transaction.channel_id == Channel.id)
        return [
            dict(row)
            for row in session.execute(
                filtered(query, Transaction, filters).group_by(Channel.name).order_by(func.count().desc())
            ).mappings()
        ]

    @app.get("/api/transactions")
    def transactions(
        session: DB,
        filters: Annotated[Filters, Depends()],
        page: int = Query(1, ge=1, le=100_000),
        page_size: int = Query(25, ge=1, le=100),
        status: Literal["approved", "declined"] | None = None,
        search: str = Query("", max_length=60),
    ):
        query = filtered(
            select(Transaction, Account.name.label("account"), Channel.name.label("channel"))
            .join(Account)
            .join(Channel),
            Transaction,
            filters,
        )
        if status:
            query = query.where(Transaction.status == status)
        if search:
            query = query.where(Transaction.payment_ref.contains(search, autoescape=True))
        count = session.scalar(select(func.count()).select_from(query.subquery()))
        rows = session.execute(
            query.order_by(Transaction.occurred_at.desc(), Transaction.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return {
            "items": [{**serialize(row[0]), "account": row.account, "channel": row.channel} for row in rows],
            "total": count,
            "page": page,
            "page_size": page_size,
        }

    @app.get("/api/anomalies")
    def anomalies(
        session: DB,
        filters: Annotated[Filters, Depends()],
        page: int = Query(1, ge=1, le=100_000),
        page_size: int = Query(25, ge=1, le=100),
        severity: Literal["critical", "high", "medium"] | None = None,
        detector: Literal["ml", "rules"] | None = None,
        approach: Approach = "rules",
    ):
        query = filtered(
            select(Anomaly, Account.name.label("account"), Channel.name.label("channel"))
            .join(Account)
            .join(Channel),
            Anomaly,
            filters,
        )
        if severity:
            query = query.where(Anomaly.severity == severity)
        if detector:
            # Preserve the older detector filter as an explicit override.
            approach = "isolation_forest" if detector == "ml" else "rules"
        query = by_approach(query, approach)
        count = session.scalar(select(func.count()).select_from(query.subquery()))
        rows = session.execute(
            query.order_by(Anomaly.day.desc(), Anomaly.score.desc(), Anomaly.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return {
            "items": [{**serialize(row[0]), "account": row.account, "channel": row.channel} for row in rows],
            "total": count,
            "page": page,
            "page_size": page_size,
        }

    @app.get("/api/anomalies/{anomaly_id}")
    def anomaly_detail(anomaly_id: int, session: DB):
        anomaly = get_anomaly(session, anomaly_id)
        start = datetime.combine(anomaly.day, daytime.min)
        rows = session.scalars(
            select(Transaction)
            .where(
                Transaction.account_id == anomaly.account_id,
                Transaction.channel_id == anomaly.channel_id,
                Transaction.occurred_at >= start,
                Transaction.occurred_at < start + timedelta(days=1),
            )
            .order_by(Transaction.amount_cents.desc())
            .limit(20)
        )
        return {
            **serialize(anomaly),
            "account": session.get(Account, anomaly.account_id).name,
            "channel": session.get(Channel, anomaly.channel_id).name,
            "transactions": [serialize(row) for row in rows],
            "analyses": [serialize(row) for row in history(session, anomaly_id)],
        }

    @app.get("/api/anomalies/{anomaly_id}/analyses")
    def analyses(anomaly_id: int, session: DB):
        get_anomaly(session, anomaly_id)
        return [serialize(row) for row in history(session, anomaly_id)]

    @app.get("/api/anomalies/{anomaly_id}/analysis-preview")
    def analysis_preview(anomaly_id: int, session: DB):
        anomaly = get_anomaly(session, anomaly_id)
        return {
            "source": "rules",
            "content": deterministic(anomaly).model_dump(),
            "fallback_reason": None,
        }

    if not settings.public_demo:

        @app.post("/api/anomalies/{anomaly_id}/investigate", dependencies=[Depends(admin)])
        def investigation(anomaly_id: int, body: InvestigationRequest, session: DB):
            anomaly = get_anomaly(session, anomaly_id)
            if not locks["analysis"].acquire(blocking=False):
                raise HTTPException(409, "Uma investigação está em andamento. Aguarde.")
            try:
                return serialize(investigate(session, anomaly, settings, body.provider))
            finally:
                locks["analysis"].release()

        @app.post("/api/pipeline/run", dependencies=[Depends(admin)])
        def pipeline(session: DB):
            if not locks["pipeline"].acquire(blocking=False):
                raise HTTPException(409, "Pipeline em execução.")
            try:
                return serialize(run_pipeline(session))
            except ValueError as error:
                raise HTTPException(409, str(error)) from None
            finally:
                locks["pipeline"].release()

    @app.get("/api/pipeline/runs")
    def pipeline_runs(session: DB):
        return [
            serialize(row)
            for row in session.scalars(select(PipelineRun).order_by(PipelineRun.id.desc()).limit(20))
        ]

    if not settings.public_demo:

        @app.get("/api/automations/pending")
        def pending_automations(session: DB):
            return {
                "mode": settings.notification_mode,
                "items": [
                    serialize(row)
                    for row in session.scalars(pending_query(settings.notification_mode).limit(100))
                ],
            }

    @app.get("/api/automations")
    def automations(session: DB, page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100)):
        total = session.scalar(select(func.count()).select_from(AutomationRun))
        runs = session.scalars(
            select(AutomationRun)
            .order_by(AutomationRun.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        attempts = session.execute(
            select(NotificationAttempt, Notification.anomaly_id, Notification.mode)
            .join(Notification)
            .order_by(NotificationAttempt.id.desc())
            .limit(50)
        )
        return {
            "mode": settings.notification_mode,
            "items": [serialize(row) for row in runs],
            "total": total,
            "page": page,
            "page_size": page_size,
            "attempts": [
                {**serialize(row[0]), "anomaly_id": row.anomaly_id, "mode": row.mode} for row in attempts
            ],
        }

    if not settings.public_demo:

        @app.post("/api/automations/run", dependencies=[Depends(admin)])
        def automate(body: AutomationRequest, session: DB):
            if not locks["automation"].acquire(blocking=False):
                raise HTTPException(409, "Automação em execução.")
            try:
                return serialize(run_automation(session, settings, body.anomaly_ids))
            finally:
                locks["automation"].release()

    frontend = PROJECT_ROOT / "frontend" / "dist"
    if frontend.is_dir():
        app.mount("/", StaticFiles(directory=frontend, html=True), name="frontend")
    return app


app = create_app()
