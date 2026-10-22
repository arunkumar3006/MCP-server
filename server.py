"""
Email Scheduling MCP Server.
Provides MCP tools to schedule, list, cancel, and immediately send emails.
"""

import sys
import json
import argparse
import signal
from datetime import datetime, timezone

from mcp.server.mcpserver import MCPServer
from config import Config, logger
from database import (
    init_db,
    add_scheduled_email,
    get_email,
    list_emails,
    cancel_email
)
from time_parser import parse_scheduled_time
from email_sender import dispatch_email
from scheduler import (
    start_scheduler,
    stop_scheduler,
    register_exact_job,
    remove_exact_job
)

# Initialize the MCP Server instance
server = MCPServer(
    name="email-scheduler",
    instructions=(
        "You are an automated email assistant. You can schedule emails to be sent at specific future times, "
        "send emails immediately, list pending/sent emails, and cancel scheduled emails. "
        "Supports natural time expressions (e.g. 'in 15 minutes', 'tomorrow at 9:00am') and ISO timestamps."
    )
)


@server.tool()
def schedule_email(
    recipient: str,
    subject: str,
    body: str,
    scheduled_time: str,
    is_html: bool = False,
    provider: str = "auto"
) -> str:
    """
    Schedules an email to be sent automatically at a specific time.

    Args:
        recipient: Email address or comma-separated list of addresses (e.g., 'user@example.com' or 'alice@test.com, bob@test.com').
        subject: The subject line of the email.
        body: The plain text or HTML body of the email.
        scheduled_time: When to send the email. Supports natural expressions like 'in 15 minutes', 'in 2 hours', 'tomorrow at 9am', or ISO strings like '2026-10-21 17:30:00'.
        is_html: Set to True if the body contains HTML markup, False for plain text.
        provider: Email provider to use ('auto', 'smtp', 'resend', 'sendgrid', or 'mock'). Default is 'auto'.

    Returns:
        JSON string confirming the scheduled email job ID, execution times, and status.
    """
    logger.info(f"Received request to schedule email to '{recipient}' with subject '{subject}' at '{scheduled_time}'")

    try:
        parsed_dt, explanation = parse_scheduled_time(scheduled_time)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"Invalid scheduled_time: {str(e)}"
        }, indent=2)

    # Check if scheduled time is in the past
    now = datetime.now(parsed_dt.tzinfo)
    if parsed_dt < now:
        diff_seconds = (now - parsed_dt).total_seconds()
        if diff_seconds > 60:
            return json.dumps({
                "success": False,
                "error": f"Scheduled time '{scheduled_time}' ({explanation}) is in the past by {int(diff_seconds)} seconds."
            }, indent=2)

    record = add_scheduled_email(
        recipient=recipient,
        subject=subject,
        body=body,
        scheduled_time=parsed_dt,
        is_html=is_html,
        provider=provider
    )

    # Register exact trigger with the scheduler for precision
    register_exact_job(record["id"], parsed_dt)

    response = {
        "success": True,
        "message": f"Email successfully scheduled for delivery: {explanation}",
        "job_id": record["id"],
        "recipient": record["recipient"],
        "subject": record["subject"],
        "scheduled_time_utc": record["scheduled_time_utc"],
        "scheduled_time_local": record["scheduled_time_local"],
        "status": record["status"],
        "provider": record["provider"]
    }
    return json.dumps(response, indent=2)


@server.tool()
def send_email_now(
    recipient: str,
    subject: str,
    body: str,
    is_html: bool = False,
    provider: str = "auto"
) -> str:
    """
    Sends an email immediately without waiting for a schedule.

    Args:
        recipient: Email address or comma-separated list of addresses.
        subject: The subject line of the email.
        body: The plain text or HTML body of the email.
        is_html: Set to True if the body contains HTML markup, False for plain text.
        provider: Email provider to use ('auto', 'smtp', 'resend', 'sendgrid', or 'mock').

    Returns:
        JSON string with immediate delivery results.
    """
    logger.info(f"Sending email now to '{recipient}': '{subject}'")

    now_dt = datetime.now(timezone.utc)
    # Add record to DB for auditing
    record = add_scheduled_email(
        recipient=recipient,
        subject=subject,
        body=body,
        scheduled_time=now_dt,
        is_html=is_html,
        provider=provider,
        initial_status="processing"
    )

    try:
        result = dispatch_email(
            recipient=recipient,
            subject=subject,
            body=body,
            is_html=is_html,
            requested_provider=provider
        )
        from database import mark_as_sent
        mark_as_sent(record["id"], provider=result.get("provider", "unknown"))

        return json.dumps({
            "success": True,
            "job_id": record["id"],
            "recipient": recipient,
            "subject": subject,
            "provider_used": result.get("provider"),
            "message": result.get("message", "Email sent successfully.")
        }, indent=2)

    except Exception as e:
        from database import mark_as_failed
        mark_as_failed(record["id"], str(e))
        return json.dumps({
            "success": False,
            "job_id": record["id"],
            "recipient": recipient,
            "subject": subject,
            "error": str(e)
        }, indent=2)


@server.tool()
def list_scheduled_emails(
    status: str = "all",
    limit: int = 20
) -> str:
    """
    Lists scheduled emails, optionally filtered by status.

    Args:
        status: Filter by status ('all', 'pending', 'sent', 'cancelled', 'failed'). Default is 'all'.
        limit: Maximum number of records to return (default 20).

    Returns:
        JSON list of email jobs matching the criteria.
    """
    logger.info(f"Listing scheduled emails (status='{status}', limit={limit})")
    records = list_emails(status=status, limit=limit)

    summary = []
    for r in records:
        summary.append({
            "id": r["id"],
            "recipient": r["recipient"],
            "subject": r["subject"],
            "scheduled_time_utc": r["scheduled_time"],
            "status": r["status"],
            "provider": r["provider"],
            "sent_at": r.get("sent_at"),
            "error": r.get("error_message")
        })

    return json.dumps({
        "count": len(summary),
        "status_filter": status,
        "emails": summary
    }, indent=2)


@server.tool()
def cancel_scheduled_email(job_id: str) -> str:
    """
    Cancels a pending scheduled email before it is sent.

    Args:
        job_id: The ID of the email job (e.g., 'job_123456789abc').

    Returns:
        JSON string indicating whether cancellation succeeded.
    """
    logger.info(f"Request to cancel email job: '{job_id}'")
    clean_id = job_id.strip()
    result = cancel_email(clean_id)
    if result.get("success"):
        remove_exact_job(clean_id)
    return json.dumps(result, indent=2)


@server.tool()
def get_email_details(job_id: str) -> str:
    """
    Retrieves full details and message body for a specific email job.

    Args:
        job_id: The ID of the email job.

    Returns:
        JSON string containing the complete email record.
    """
    record = get_email(job_id.strip())
    if not record:
        return json.dumps({
            "found": False,
            "message": f"Email job '{job_id}' not found."
        }, indent=2)

    return json.dumps({
        "found": True,
        "email": record
    }, indent=2)


def handle_shutdown(signum, frame):
    logger.info(f"Received signal {signum}, shutting down server gracefully...")
    stop_scheduler()
    sys.exit(0)


def main():
    parser = argparse.ArgumentParser(description="Email Scheduling MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default="stdio",
        help="MCP transport to use (default: stdio)"
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind for SSE or HTTP transport (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind for SSE or HTTP transport (default: 8000)"
    )

    args = parser.parse_args()

    # Register signal handlers for clean exit
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    # Initialize SQLite database schema
    init_db()

    # Start background polling scheduler
    start_scheduler()

    logger.info(f"Starting Email MCP Server with transport='{args.transport}'")

    try:
        if args.transport == "stdio":
            server.run(transport="stdio")
        elif args.transport == "sse":
            server.run(transport="sse", host=args.host, port=args.port)
        elif args.transport == "streamable-http":
            server.run(transport="streamable-http", host=args.host, port=args.port)
    finally:
        stop_scheduler()


if __name__ == "__main__":
    main()
