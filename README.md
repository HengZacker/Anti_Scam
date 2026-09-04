# 🛡️ Telegram File Guard

Telegram security bot that automatically detects and deletes
dangerous executable/script files from Telegram groups.

## Blocked extensions

- .exe
- .bat
- .vbs
- .ps1
- .sh
- .msi
- .scr

## Features

- Automatic file deletion
- Group monitoring
- Admin alerts
- PostgreSQL logging
- Statistics
- Web dashboard
- Telegram webhook
- Render support
- Health check
- Environment variable configuration

## Commands

/start

/help

/stats

## Dashboard

/dashboard?token=YOUR_DASHBOARD_TOKEN

## Local development

Create virtual environment:

python -m venv .venv

Activate on Windows:

.venv\Scripts\activate

Activate on macOS/Linux:

source .venv/bin/activate

Install:

pip install -r requirements.txt

Copy environment example:

cp .env.example .env

Run:

uvicorn app.main:app --reload --port 10000

## Render

Deploy as a Web Service.

Build:

pip install -r requirements.txt

Start:

uvicorn app.main:app --host 0.0.0.0 --port $PORT

Health check:

/health