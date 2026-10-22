"""
End-to-End Test Suite for Email MCP Server.
Tests scheduling, automatic background delivery, immediate sending, and cancellation.
"""

import time
import json
import os
from datetime import datetime, timezone
from config import Config, logger
from database import init_db, list_emails, get_email
from server import (
    schedule_email,
    send_email_now,
    list_scheduled_emails,
    cancel_scheduled_email,
    get_email_details
)
from scheduler import start_scheduler, stop_scheduler


def run_tests():
    print("=" * 60)
    print("RUNNING EMAIL MCP SERVER VERIFICATION TESTS")
    print("=" * 60)

    # 1. Initialize Database & Scheduler
    init_db()
    start_scheduler()
    print("[PASS] Database and Scheduler initialized successfully.")

    # 2. Test Immediate Send
    print("\n--- Test 1: Immediate Send (send_email_now) ---")
    send_res_str = send_email_now(
        recipient="test-immediate@example.com",
        subject="Test Immediate Email",
        body="This is an immediate test email."
    )
    send_res = json.loads(send_res_str)
    print("Response:", json.dumps(send_res, indent=2))
    assert send_res.get("success") is True, "send_email_now failed"
    print("[PASS] Immediate send succeeded.")

    # 3. Test Schedule & Cancel
    print("\n--- Test 2: Schedule & Cancel Email ---")
    sched_res_str = schedule_email(
        recipient="test-cancel@example.com",
        subject="Test Cancel Email",
        body="This email will be cancelled.",
        scheduled_time="in 10 minutes"
    )
    sched_res = json.loads(sched_res_str)
    job_id = sched_res.get("job_id")
    print(f"Scheduled Job ID: {job_id}")
    assert sched_res.get("success") is True, "schedule_email failed"

    cancel_res_str = cancel_scheduled_email(job_id)
    cancel_res = json.loads(cancel_res_str)
    print("Cancel Response:", cancel_res)
    assert cancel_res.get("success") is True, "cancel_scheduled_email failed"

    details_res = json.loads(get_email_details(job_id))
    assert details_res["email"]["status"] == "cancelled", "Status is not cancelled"
    print("[PASS] Schedule and cancel succeeded.")

    # 4. Test Automated Background Dispatch
    print("\n--- Test 3: Automated Background Scheduled Dispatch ---")
    sched_bg_str = schedule_email(
        recipient="test-automated@example.com",
        subject="Automated Time-based Email",
        body="<b>Hello!</b> This email was sent automatically on schedule.",
        scheduled_time="in 2 seconds",
        is_html=True
    )
    sched_bg = json.loads(sched_bg_str)
    bg_job_id = sched_bg["job_id"]
    print(f"Scheduled 2-second job: {bg_job_id}")

    # Wait for the exact date trigger to fire (2 seconds + 1s buffer)
    print("Waiting 3.5 seconds for exact trigger to dispatch...")
    time.sleep(3.5)

    # Verify status changed to 'sent'
    bg_details = json.loads(get_email_details(bg_job_id))
    status = bg_details["email"]["status"]
    print(f"Job status after wait: {status}")
    assert status == "sent", f"Expected status 'sent', got '{status}'"
    print("[PASS] Automated background execution succeeded!")

    stop_scheduler()

    # 5. Test List Tool
    print("\n--- Test 4: List Scheduled Emails Tool ---")
    list_res_str = list_scheduled_emails(status="all", limit=10)
    list_res = json.loads(list_res_str)
    print(f"Total emails recorded: {list_res['count']}")
    assert list_res["count"] >= 3, "Expected at least 3 emails in list"
    print("[PASS] List emails tool succeeded.")

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED SUCCESSFULLY! The MCP server is ready for production.")
    print("=" * 60)


if __name__ == "__main__":
    run_tests()
