"""
SQLite persistence layer for scheduled emails.
Thread-safe with WAL mode and atomic claim operations.
"""

import sqlite3
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from config import Config, logger

DB_PATH = Config.DATABASE_PATH


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    # Enable WAL mode for high concurrency
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


def init_db():
    """Initializes the database schema if it does not already exist."""
    with get_db_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS emails (
                id TEXT PRIMARY KEY,
                recipient TEXT NOT NULL,
                subject TEXT NOT NULL,
                body TEXT NOT NULL,
                is_html INTEGER DEFAULT 0,
                scheduled_time TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                provider TEXT NOT NULL DEFAULT 'auto',
                created_at TEXT NOT NULL,
                sent_at TEXT,
                error_message TEXT
            );
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_emails_status_time 
            ON emails (status, scheduled_time);
        """)
        conn.commit()
    logger.info(f"Database initialized at {DB_PATH}")


def add_scheduled_email(
    recipient: str,
    subject: str,
    body: str,
    scheduled_time: datetime,
    is_html: bool = False,
    provider: str = "auto",
    initial_status: str = "pending"
) -> Dict[str, Any]:
    """Adds a new email record to the database."""
    job_id = f"job_{uuid.uuid4().hex[:12]}"
    # Normalize to ISO UTC
    if scheduled_time.tzinfo is None:
        # Assumed local system time, convert to UTC
        scheduled_utc = scheduled_time.astimezone(timezone.utc)
    else:
        scheduled_utc = scheduled_time.astimezone(timezone.utc)

    scheduled_iso = scheduled_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    created_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    with get_db_connection() as conn:
        conn.execute("""
            INSERT INTO emails (
                id, recipient, subject, body, is_html, scheduled_time, 
                status, provider, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            job_id,
            recipient.strip(),
            subject.strip(),
            body,
            1 if is_html else 0,
            scheduled_iso,
            initial_status,
            provider.strip().lower(),
            created_iso
        ))
        conn.commit()

    return {
        "id": job_id,
        "recipient": recipient.strip(),
        "subject": subject.strip(),
        "scheduled_time_utc": scheduled_iso,
        "scheduled_time_local": scheduled_time.isoformat(),
        "status": initial_status,
        "provider": provider,
        "created_at": created_iso
    }


def get_email(job_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves an email job by its ID."""
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT * FROM emails WHERE id = ?", (job_id,))
        row = cursor.fetchone()
        if row:
            return dict(row)
    return None


def list_emails(status: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """Lists emails filtered by status, ordered by scheduled time."""
    with get_db_connection() as conn:
        if status and status.lower() != "all":
            cursor = conn.execute(
                "SELECT * FROM emails WHERE status = ? ORDER BY scheduled_time ASC LIMIT ?",
                (status.lower(), limit)
            )
        else:
            cursor = conn.execute(
                "SELECT * FROM emails ORDER BY created_at DESC LIMIT ?",
                (limit,)
            )
        return [dict(row) for row in cursor.fetchall()]


def cancel_email(job_id: str) -> Dict[str, Any]:
    """Cancels a pending email."""
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT status FROM emails WHERE id = ?", (job_id,))
        row = cursor.fetchone()
        if not row:
            return {"success": False, "message": f"Email job '{job_id}' not found."}

        current_status = row["status"]
        if current_status == "sent":
            return {"success": False, "message": f"Cannot cancel '{job_id}': Email has already been sent."}
        if current_status == "cancelled":
            return {"success": True, "message": f"Email job '{job_id}' was already cancelled."}
        if current_status == "processing":
            return {"success": False, "message": f"Cannot cancel '{job_id}': Email is currently being sent."}

        conn.execute("UPDATE emails SET status = 'cancelled' WHERE id = ?", (job_id,))
        conn.commit()
        return {"success": True, "message": f"Email job '{job_id}' successfully cancelled."}


def claim_due_emails(now_utc_iso: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Atomically claims all pending emails where scheduled_time <= now.
    Sets status to 'processing' to avoid concurrent double-sending.
    """
    if not now_utc_iso:
        now_utc_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    with get_db_connection() as conn:
        # Find candidates
        cursor = conn.execute("""
            SELECT id FROM emails 
            WHERE status = 'pending' AND scheduled_time <= ?
            ORDER BY scheduled_time ASC
        """, (now_utc_iso,))
        candidate_ids = [row["id"] for row in cursor.fetchall()]

        if not candidate_ids:
            return []

        # Claim them
        placeholders = ",".join("?" for _ in candidate_ids)
        conn.execute(
            f"UPDATE emails SET status = 'processing' WHERE id IN ({placeholders})",
            candidate_ids
        )
        conn.commit()

        # Return claimed rows
        cursor = conn.execute(
            f"SELECT * FROM emails WHERE id IN ({placeholders})",
            candidate_ids
        )
        return [dict(row) for row in cursor.fetchall()]


def mark_as_sent(job_id: str, provider: str = ""):
    """Marks an email as successfully sent."""
    sent_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with get_db_connection() as conn:
        conn.execute("""
            UPDATE emails 
            SET status = 'sent', sent_at = ?, error_message = NULL,
                provider = CASE WHEN ? != '' THEN ? ELSE provider END
            WHERE id = ?
        """, (sent_iso, provider, provider, job_id))
        conn.commit()
    logger.info(f"Email {job_id} marked as SENT.")


def mark_as_failed(job_id: str, error_message: str):
    """Marks an email as failed with an error message."""
    with get_db_connection() as conn:
        conn.execute("""
            UPDATE emails 
            SET status = 'failed', error_message = ? 
            WHERE id = ?
        """, (error_message, job_id))
        conn.commit()
    logger.error(f"Email {job_id} marked as FAILED: {error_message}")
