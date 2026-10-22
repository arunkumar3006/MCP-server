# 🌐 Free Deployment Guide: Email MCP Studio

This guide shows you **where** and **how** to host your Email MCP Server & Web Dashboard for **100% free** with continuous 24/7 background email scheduling.

---

## 🏆 Top 3 Free Hosting Platforms Compared

| Platform | Free Plan Details | Sleep Policy | Best For |
| :--- | :--- | :--- | :--- |
| **[Render.com](https://render.com)** *(Top Choice)* | 750 free instance hrs/month, free HTTPS, auto-git deploys | Sleeps after 15m idle *(preventable with free keepalive ping)* | Easiest setup directly from GitHub |
| **[Koyeb.com](https://koyeb.com)** | 1 Free Nano service, 512MB RAM, global edge | **Does not sleep** | Fast containerized hosting with zero sleep |
| **[Oracle Cloud Always Free](https://www.oracle.com/cloud/free/)** | 24GB RAM (ARM) or 1GB (AMD), 50GB SSD, Ubuntu VM | **Never sleeps (Full Linux VM)** | True 24/7 production server forever |

---

## 🚀 Option 1: Deploy on Render.com (Easiest — 3 Steps)

### Step 1: Push your code to a private GitHub Repository
1. In your project directory:
   ```bash
   git init
   git add .
   git commit -m "Initial commit for Email MCP Studio"
   ```
2. Create a new repository on [github.com](https://github.com) (make it **Private** so your `.env` isn't public, or ensure `.env` is listed in [`.gitignore`](file:///d:/mcp%20server/.gitignore)).
3. Push your code:
   ```bash
   git remote add origin https://github.com/YOUR_USERNAME/email-mcp-studio.git
   git branch -M main
   git push -u origin main
   ```

### Step 2: Create a Web Service on Render
1. Sign up / Log in to [render.com](https://render.com).
2. Click **New +** → **Web Service**.
3. Connect your GitHub repository.
4. Fill in the deployment settings:
   - **Name**: `email-mcp-studio`
   - **Language**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app:app --host 0.0.0.0 --port $PORT`
   - **Instance Type**: **Free**

### Step 3: Add your Environment Variables
Under the **Environment Variables** section on Render, add:
- `DEFAULT_PROVIDER`: `smtp`
- `SMTP_HOST`: `smtp.gmail.com`
- `SMTP_PORT`: `587`
- `SMTP_USER`: `arunraghav3006@gmail.com`
- `SMTP_PASSWORD`: `your_16_char_gmail_app_password`
- `SMTP_USE_TLS`: `true`
- `SMTP_DEFAULT_FROM`: `arunraghav3006@gmail.com`
- `RESEND_API_KEY`: `re_...`
- `RESEND_DEFAULT_FROM`: `onboarding@resend.dev`

Click **Create Web Service**. Your live dashboard will be live at `https://email-mcp-studio.onrender.com` in ~2 minutes!

> [!TIP]
> ### ⏰ How to Keep Render Awake 24/7 (Preventing Sleep)
> Free Render web services go to sleep if no HTTP request arrives for 15 minutes. 
> To keep the background scheduler running 24/7:
> 1. Go to [cron-job.org](https://cron-job.org) or [uptimerobot.com](https://uptimerobot.com) (both 100% free).
> 2. Create a free HTTP monitor to ping: `https://your-app-name.onrender.com/api/stats` every **10 minutes**.
> 3. Render will stay awake 24/7, and scheduled emails will fire on time!

---

## ⚡ Option 2: Deploy on Koyeb (No Sleeping)

1. Sign up at [koyeb.com](https://www.koyeb.com).
2. Click **Create App** → **GitHub**.
3. Select your repository. Koyeb will automatically detect the [`Dockerfile`](file:///d:/mcp%20server/Dockerfile) we created.
4. Add the same Environment Variables (`SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`, etc.).
5. Choose the **Free Nano** tier.
6. Click **Deploy**. Koyeb runs containers continuously without sleeping.

---

## 💻 Option 3: Run Locally 24/7 on Windows (Zero Cloud Needed)

If your laptop/desktop is usually turned on, you can make this run silently in the background at startup without any cloud accounts:

1. Create a lightweight Windows startup shortcut:
   - Press `Win + R`, type `shell:startup` and hit Enter.
2. In that folder, create a file named `StartEmailMCP.vbs`:
   ```vbscript
   Set WshShell = CreateObject("WScript.Shell")
   WshShell.Run "d:\mcp server\.venv\Scripts\python.exe d:\mcp server\app.py", 0, False
   ```
3. Whenever you turn on your PC, the server and scheduler will start silently in the background on port `5000` with zero CPU overhead!
