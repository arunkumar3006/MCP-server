"""
Background scheduler service for checking and dispatching scheduled emails.
Combines exact date-based APScheduler triggers with periodic SQLite polling.
"""

from datetime import datetime, timezone
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.base import JobLookupError
from config import Config, logger
from database import claim_due_emails, mark_as_sent, mark_as_failed
from email_sender import dispatch_email

_scheduler: BackgroundScheduler = None


def check_and_send_due_emails():
    """
    Polls the database for any pending emails that have reached or passed their scheduled time.
    Dispatches each email and updates database state.
    """
    now_utc_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    due_emails = claim_due_emails(now_utc_iso)

    if not due_emails:
        return

    logger.info(f"Processing {len(due_emails)} due email(s)...")

    for email in due_emails:
        job_id = email["id"]
        recipient = email["recipient"]
        subject = email["subject"]
        body = email["body"]
        is_html = bool(email["is_html"])
        requested_provider = email.get("provider", "auto")

        try:
            logger.info(f"Dispatching scheduled email {job_id} to {recipient}...")
            result = dispatch_email(
                recipient=recipient,
                subject=subject,
                body=body,
                is_html=is_html,
                requested_provider=requested_provider
            )
            mark_as_sent(job_id, provider=result.get("provider", "unknown"))
            logger.info(f"Successfully processed scheduled email {job_id}.")
        except Exception as e:
            error_msg = f"Delivery failed: {str(e)}"
            logger.error(f"Error dispatching email {job_id}: {error_msg}")
            mark_as_failed(job_id, error_msg)


def register_exact_job(job_id: str, run_date: datetime):
    """
    Registers an exact-time date trigger with APScheduler for down-to-the-second execution.
    """
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        try:
            _scheduler.add_job(
                check_and_send_due_emails,
                trigger="date",
                run_date=run_date,
                id=f"exact_{job_id}",
                replace_existing=True
            )
            logger.info(f"Registered exact-time trigger for {job_id} at {run_date}")
        except Exception as e:
            logger.warning(f"Could not register in-memory exact job {job_id}: {e}")


def remove_exact_job(job_id: str):
    """Removes an in-memory job if registered."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        try:
            _scheduler.remove_job(f"exact_{job_id}")
            logger.info(f"Removed exact-time trigger for {job_id}")
        except JobLookupError:
            pass
        except Exception as e:
            logger.warning(f"Error removing in-memory job {job_id}: {e}")


def start_scheduler() -> BackgroundScheduler:
    """Starts the background polling scheduler and periodic worker."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        return _scheduler

    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(
        check_and_send_due_emails,
        trigger="interval",
        seconds=Config.POLL_INTERVAL_SECONDS,
        id="check_due_emails",
        replace_existing=True,
        max_instances=1,
        coalesce=True
    )
    _scheduler.start()
    logger.info(f"Background scheduler started (checking every {Config.POLL_INTERVAL_SECONDS}s).")

    # Run one immediate check on startup for any overdue emails
    try:
        check_and_send_due_emails()
    except Exception as e:
        logger.error(f"Initial due email check error: {e}")

    return _scheduler


def stop_scheduler():
    """Shuts down the background scheduler."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Background scheduler stopped.")
        _scheduler = None
