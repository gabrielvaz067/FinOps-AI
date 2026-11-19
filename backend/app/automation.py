import smtplib
import ssl
from email.message import EmailMessage

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.config import Settings
from backend.app.models import Anomaly, AutomationRun, Notification, NotificationAttempt


class SMTPPreSendError(Exception):
    """Connection, TLS, or authentication failed before a message was submitted."""


def deliver_smtp(anomaly: Anomaly, settings: Settings):
    message = EmailMessage()
    message["Subject"] = f"[FinOps AI · sintético] Alerta crítico #{anomaly.id}"
    message["From"] = settings.smtp_from
    message["To"] = settings.smtp_to
    message["Message-ID"] = f"<finops-anomaly-{anomaly.id}@finops.local>"
    message.set_content(
        f"Dados sintéticos. Anomalia não comprova fraude.\nData: {anomaly.day}\n" + "\n".join(anomaly.reasons)
    )
    smtp = None
    try:
        smtp = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15)
        smtp.ehlo()
        smtp.starttls(context=ssl.create_default_context())
        smtp.ehlo()
        if settings.smtp_user:
            smtp.login(settings.smtp_user, settings.smtp_password)
    except (OSError, smtplib.SMTPException, ValueError) as error:
        if smtp is not None:
            smtp.close()
        raise SMTPPreSendError from error
    try:
        smtp.send_message(message)
    finally:
        try:
            smtp.quit()
        except (OSError, smtplib.SMTPException):
            smtp.close()


def pending_query(mode: str):
    delivered = select(Notification.anomaly_id).where(
        Notification.mode == mode, Notification.status.in_(["sent", "simulated", "sending", "unknown"])
    )
    exhausted = select(Notification.anomaly_id).where(Notification.mode == mode, Notification.attempts >= 3)
    return (
        select(Anomaly)
        .where(
            Anomaly.severity == "critical",
            Anomaly.rule_detected.is_(True),
            Anomaly.id.not_in(delivered),
            Anomaly.id.not_in(exhausted),
        )
        .order_by(Anomaly.day.desc(), Anomaly.id)
    )


def run_automation(
    session: Session, settings: Settings, anomaly_ids: list[int] | None = None
) -> AutomationRun:
    run = AutomationRun(mode=settings.notification_mode)
    session.add(run)
    session.commit()
    query = pending_query(settings.notification_mode)
    if anomaly_ids is not None:
        query = query.where(Anomaly.id.in_(anomaly_ids))
    # Exclude successful/uncertain deliveries before limiting, so later batches are not starved.
    candidates = list(session.scalars(query.limit(100)))
    for anomaly in candidates:
        notification = session.scalar(
            select(Notification).where(
                Notification.anomaly_id == anomaly.id, Notification.mode == settings.notification_mode
            )
        )
        if notification is None:
            try:
                with session.begin_nested():
                    notification = Notification(anomaly_id=anomaly.id, mode=settings.notification_mode)
                    session.add(notification)
                    session.flush()
            except IntegrityError:
                run.skipped += 1
                continue
        # Atomic claim also prevents two workers from delivering the same notification.
        claim = session.execute(
            update(Notification)
            .where(
                Notification.id == notification.id,
                Notification.status.in_(["pending", "failed"]),
                Notification.attempts < 3,
            )
            .values(status="sending", attempts=Notification.attempts + 1)
        )
        if claim.rowcount != 1:
            run.skipped += 1
            continue
        session.commit()
        if settings.notification_mode == "simulated":
            status, message = "simulated", "Notificação simulada localmente; nenhum e-mail enviado."
        elif not all([settings.smtp_host, settings.smtp_from, settings.smtp_to]):
            status, message = "failed", "SMTP incompleto; envio não iniciado. Máximo de três tentativas."
        else:
            try:
                deliver_smtp(anomaly, settings)
                status, message = "sent", "Mensagem aceita pelo servidor SMTP."
            except SMTPPreSendError:
                status, message = "failed", "Falha antes do envio SMTP; tentativa futura permitida."
            except (OSError, smtplib.SMTPException, ValueError):
                # SMTP cannot provide exactly-once delivery. Never auto-retry an ambiguous send.
                status, message = (
                    "unknown",
                    "Falha SMTP; entrega incerta. Revisão manual necessária antes de reenviar.",
                )
        notification.status = status
        session.add(
            NotificationAttempt(
                notification_id=notification.id, run_id=run.id, status=status, message=message
            )
        )
        if status in {"simulated", "sent"}:
            run.processed += 1
        else:
            run.failed += 1
        session.commit()
    run.status = "partial_failure" if run.failed else "completed"
    session.commit()
    return run
