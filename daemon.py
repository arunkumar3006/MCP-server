"""
Standalone background scheduler daemon.
Can be run independently to check and dispatch scheduled emails from emails.db
even when the MCP server stdio process is not active.
"""

import time
import signal
import sys
from config import Config, logger
from database import init_db
from scheduler import start_scheduler, stop_scheduler

running = True


def handle_exit(signum, frame):
    global running
    logger.info(f"Daemon received signal {signum}, stopping...")
    running = False


def main():
    logger.info("Starting Standalone Email Scheduler Daemon...")
    init_db()
    start_scheduler()

    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    logger.info(f"Daemon is active and polling every {Config.POLL_INTERVAL_SECONDS} seconds. Press Ctrl+C to stop.")

    try:
        while running:
            time.sleep(1)
    finally:
        stop_scheduler()
        logger.info("Daemon stopped successfully.")


if __name__ == "__main__":
    main()
