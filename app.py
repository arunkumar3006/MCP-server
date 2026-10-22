"""
FastAPI Web Dashboard Backend for Email MCP Server.
Provides REST endpoints for web client and serves interactive frontend.
"""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional, List
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from config import Config, logger, BASE_DIR
from database import (
    init_db,
    add_scheduled_email,
    get_email,
    list_emails,
    cancel_email,
    get_db_connection
)
from scheduler import (
    start_scheduler,
    stop_scheduler,
    register_exact_job,
    remove_exact_job
)
from time_parser import parse_scheduled_time
from email_sender import dispatch_email


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure database initialized and scheduler running
    init_db()
    start_scheduler()
    logger.info("Web Dashboard backend started with background scheduler active.")
    yield
    # Shutdown: stop scheduler
    stop_scheduler()
    logger.info("Web Dashboard backend shut down.")


app = FastAPI(title="Email Scheduler Web Dashboard", lifespan=lifespan)

# Allow CORS for local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ScheduleRequest(BaseModel):
    recipient: str = Field(..., description="Recipient email address")
    subject: str = Field(..., description="Email subject")
    body: str = Field(..., description="Email body content")
    scheduled_time: str = Field(..., description="Natural or ISO timestamp, e.g. 'in 15 minutes' or '2026-10-22 15:00:00'")
    is_html: bool = Field(False, description="Whether the body is HTML")
    provider: str = Field("auto", description="Provider to use: auto | smtp | resend | sendgrid | mock")


class SendNowRequest(BaseModel):
    recipient: str = Field(..., description="Recipient email address")
    subject: str = Field(..., description="Email subject")
    body: str = Field(..., description="Email body content")
    is_html: bool = Field(False, description="Whether the body is HTML")
    provider: str = Field("auto", description="Provider to use: auto | smtp | resend | sendgrid | mock")


@app.get("/api/stats")
def get_stats():
    """Returns email summary counts and active provider statuses."""
    with get_db_connection() as conn:
        counts = conn.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'sent' THEN 1 ELSE 0 END) as sent,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) as cancelled
            FROM emails;
        """).fetchone()

    return {
        "total": counts["total"] or 0,
        "sent": counts["sent"] or 0,
        "pending": counts["pending"] or 0,
        "failed": counts["failed"] or 0,
        "cancelled": counts["cancelled"] or 0,
        "providers": {
            "default": Config.DEFAULT_PROVIDER,
            "smtp": {
                "configured": Config.is_smtp_configured(),
                "host": Config.SMTP_HOST,
                "user": Config.SMTP_USER,
                "from": Config.SMTP_DEFAULT_FROM
            },
            "resend": {
                "configured": Config.is_resend_configured(),
                "from": Config.RESEND_DEFAULT_FROM
            },
            "sendgrid": {
                "configured": Config.is_sendgrid_configured(),
                "from": Config.SENDGRID_DEFAULT_FROM
            }
        }
    }


@app.get("/api/emails")
def get_emails(
    status: Optional[str] = Query("all", description="Filter by status"),
    search: Optional[str] = Query("", description="Search term for recipient or subject"),
    limit: int = Query(50, ge=1, le=200)
):
    """Retrieves list of emails with optional filtering and search."""
    with get_db_connection() as conn:
        query = "SELECT * FROM emails WHERE 1=1"
        params = []

        if status and status.lower() != "all":
            query += " AND status = ?"
            params.append(status.lower())

        if search:
            query += " AND (recipient LIKE ? OR subject LIKE ?)"
            term = f"%{search.strip()}%"
            params.extend([term, term])

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]


@app.get("/api/emails/{job_id}")
def get_single_email(job_id: str):
    """Retrieves full details for a single email."""
    record = get_email(job_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Email job '{job_id}' not found")
    return record


@app.post("/api/schedule")
def schedule_email_endpoint(payload: ScheduleRequest):
    """Schedules an email for delivery."""
    try:
        parsed_dt, explanation = parse_scheduled_time(payload.scheduled_time)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid scheduled_time: {str(e)}")

    now = datetime.now(parsed_dt.tzinfo)
    if parsed_dt < now:
        diff_sec = (now - parsed_dt).total_seconds()
        if diff_sec > 60:
            raise HTTPException(
                status_code=400,
                detail=f"Scheduled time ({explanation}) is in the past by {int(diff_sec)} seconds."
            )

    record = add_scheduled_email(
        recipient=payload.recipient,
        subject=payload.subject,
        body=payload.body,
        scheduled_time=parsed_dt,
        is_html=payload.is_html,
        provider=payload.provider
    )

    register_exact_job(record["id"], parsed_dt)

    return {
        "success": True,
        "message": f"Email successfully scheduled: {explanation}",
        "job": record
    }


@app.post("/api/send-now")
def send_now_endpoint(payload: SendNowRequest):
    """Sends an email immediately."""
    now_dt = datetime.now(timezone.utc)
    record = add_scheduled_email(
        recipient=payload.recipient,
        subject=payload.subject,
        body=payload.body,
        scheduled_time=now_dt,
        is_html=payload.is_html,
        provider=payload.provider,
        initial_status="processing"
    )

    try:
        result = dispatch_email(
            recipient=payload.recipient,
            subject=payload.subject,
            body=payload.body,
            is_html=payload.is_html,
            requested_provider=payload.provider
        )
        from database import mark_as_sent
        mark_as_sent(record["id"], provider=result.get("provider", "unknown"))

        return {
            "success": True,
            "job_id": record["id"],
            "provider_used": result.get("provider"),
            "message": result.get("message", "Email sent successfully.")
        }
    except Exception as e:
        from database import mark_as_failed
        mark_as_failed(record["id"], str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/cancel/{job_id}")
def cancel_email_endpoint(job_id: str):
    """Cancels a pending scheduled email."""
    result = cancel_email(job_id.strip())
    if result.get("success"):
        remove_exact_job(job_id.strip())
        return result
    raise HTTPException(status_code=400, detail=result.get("message"))


# Serve frontend static assets
STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")


def main():
    import uvicorn
    import os
    port = int(os.getenv("PORT", "5000"))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)


if __name__ == "__main__":
    main()
