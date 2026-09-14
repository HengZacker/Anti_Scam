# Telegram File Guard

Telegram security bot that automatically detects and deletes
blocked file extensions from Telegram groups.

## Features

- Automatic file deletion
- Dangerous extension detection
- Double-extension detection
- Admin alerts
- Neon PostgreSQL
- Statistics
- Protected group tracking
- Automatic group removal when bot leaves
- Render webhook
- Local polling
- FastAPI health endpoint
- Dashboard endpoint

## Commands

/start
/help
/stats
/groups
/id

## Local

Create virtual environment:

python -m venv .venv

Activate:

macOS/Linux:

source .venv/bin/activate

Windows:

.venv\Scripts\activate

Install:

pip install -r requirements.txt

Run:

uvicorn app.main:app --reload

## Render

Build:

pip install -r requirements.txt

Start:

uvicorn app.main:app --host 0.0.0.0 --port $PORT