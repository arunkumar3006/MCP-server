# ✉️ Email Scheduling MCP Server

An enterprise-ready **Model Context Protocol (MCP)** server that enables AI assistants (such as Google Antigravity, Claude Desktop, Cursor, and any MCP client) to automatically schedule, manage, and send emails at specific future times or relative intervals.

---

## ✨ Features

- ⏰ **Natural & Precise Scheduling**:
  - Relative expressions: `"in 15 minutes"`, `"in 2 hours"`, `"in 1 day"`, `"+30m"`.
  - Natural time-of-day: `"today at 5:00pm"`, `"tomorrow at 9:30am"`.
  - Exact ISO timestamps: `"2026-10-21 16:30:00"`, `"2026-10-22T10:00:00Z"`.
- 📬 **Multi-Provider Email Dispatch**:
  - **Standard SMTP**: Works with **Gmail (App Passwords)**, **Outlook / Office 365**, iCloud, Yahoo, or private SMTP servers.
  - **Resend API**: High-deliverability modern email API.
  - **SendGrid API**: Robust transactional email service.
  - **Safe Dry-Run / Mock Mode**: Logs emails locally to `email_deliveries.log` if credentials are not configured yet, making testing completely seamless.
- 💾 **Persistent SQLite Storage**:
  - Scheduled jobs are stored in `emails.db` with atomic SQLite row locks (`processing` status transition) to ensure **zero duplicate sends**.
  - **Offline Resilience**: If your computer or MCP client shuts down, missed jobs are automatically caught and processed as soon as the server or daemon starts.
- ⚡ **Down-to-the-Second Precision**:
  - Combines **APScheduler** exact date triggers with periodic database polling.
- 🛡️ **Clean Protocol Design**:
  - Strict separation of logging: All diagnostics stream to `sys.stderr` and `email_mcp.log`, keeping `sys.stdout` clean for JSON-RPC MCP messages.

---

## 🛠️ MCP Tools Exposed

| Tool | Parameters | Description |
| :--- | :--- | :--- |
| **`schedule_email`** | `recipient`, `subject`, `body`, `scheduled_time`, `is_html` (opt), `provider` (opt) | Schedules an email to be sent automatically at a future time. |
| **`send_email_now`** | `recipient`, `subject`, `body`, `is_html` (opt), `provider` (opt) | Immediately sends an email without waiting for a schedule. |
| **`list_scheduled_emails`** | `status` (`'all'`, `'pending'`, `'sent'`, `'cancelled'`, `'failed'`), `limit` | Lists recorded emails with their ID, recipient, time, and status. |
| **`cancel_scheduled_email`** | `job_id` | Cancels a pending scheduled email before it is sent. |
| **`get_email_details`** | `job_id` | Retrieves full email metadata, body, timestamps, and error history. |

---

## 🚀 Quick Start

### 1. Environment Setup

The virtual environment and dependencies are already configured in this workspace. If setting up from scratch:

```bash
# Create virtual environment
python -m venv .venv

# Activate (Windows PowerShell)
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Email Credentials (`.env`)

Edit [`.env`](file:///d:/mcp%20server/.env) with your preferred sending method:

#### Option A: Gmail (Recommended for personal use)
1. Go to your [Google Account App Passwords](https://myaccount.google.com/apppasswords).
2. Generate an App Password for **Mail**.
3. In [`.env`](file:///d:/mcp%20server/.env), fill in:
   ```env
   DEFAULT_PROVIDER=smtp
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USER=your_email@gmail.com
   SMTP_PASSWORD=your_16_char_app_password
   SMTP_USE_TLS=true
   SMTP_DEFAULT_FROM=your_email@gmail.com
   ```

#### Option B: Resend (Recommended for developers & domains)
1. Sign up at [Resend.com](https://resend.com) and generate an API key.
2. In [`.env`](file:///d:/mcp%20server/.env):
   ```env
   DEFAULT_PROVIDER=resend
   RESEND_API_KEY=re_123456789...
   RESEND_DEFAULT_FROM=onboarding@resend.dev
   ```

#### Option C: Mock / Dry-Run (No credentials required)
If you leave `.env` empty or set `EMAIL_DRY_RUN=true`, emails are automatically recorded to [`email_deliveries.log`](file:///d:/mcp%20server/email_deliveries.log) for testing.

---

## 🔌 Connecting to MCP Clients

### Antigravity IDE / Claude Desktop / Cursor

Add the server to your `mcp_config.json` (or `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "email-scheduler": {
      "command": "d:\\mcp server\\.venv\\Scripts\\python.exe",
      "args": [
        "d:\\mcp server\\server.py"
      ]
    }
  }
}
```

---

## 🏃 Running the Server

### Mode 1: Interactive MCP Stdio Mode (Default)
When connected to an MCP client like Antigravity or Claude Desktop, the client automatically launches and manages `server.py` via `stdio`.

### Mode 2: Standalone 24/7 Daemon
If you want scheduled emails to continue sending in the background even when your AI editor is closed:

```powershell
.\.venv\Scripts\python daemon.py
```

### Mode 3: HTTP / SSE Remote Mode
To run as a network service for remote clients:

```powershell
.\.venv\Scripts\python server.py --transport sse --port 8000
```

### Mode 4: Interactive Web Dashboard (UI)
To launch the real-time web dashboard and monitor email delivery graphically:

```powershell
.\.venv\Scripts\python -m uvicorn app:app --host 127.0.0.1 --port 5000
```
Open **`http://127.0.0.1:5000`** in your browser to view real-time countdowns, compose emails, and manage scheduled jobs.

---

## 💬 Example Prompts to Use with your AI Assistant

Once connected, you can converse naturally:

- *"Please schedule an email to boss@company.com with the subject 'Weekly Update' and body 'Attached is the summary for review' tomorrow morning at 9am."*
- *"Schedule an email to team@startup.io in 45 minutes saying the deployment is complete."*
- *"Show me all pending scheduled emails."*
- *"Cancel scheduled email job_abc123."*
- *"Send an email right now to client@example.com welcoming them to the platform."*

---

## 🧪 Running Verification Tests

Run the included automated test suite anytime:

```powershell
.\.venv\Scripts\python test_server.py
```
