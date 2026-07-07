# SPENT. — a brutalist expense tracker

A multi-user expense tracker with a raw, receipt-inspired brutalist UI (paper/ink/mustard/brick/sage palette — no neon), with a dark mode toggle. Built with Flask, Flask-Login, and SQLAlchemy (SQLite locally, Postgres in production).

## Features

- **Accounts:** sign up / log in / log out, each user only sees their own data
- Add, edit, and delete expenses (delete asks for confirmation first)
- Filter the list by category and/or date range
- Export expenses to CSV, or a full JSON backup (expenses + budgets + recurring rules)
- All-time total, this-month total, per-category breakdown
- Month-over-month and week-over-week % change
- "Biggest spend" and "top category" callouts
- Last-6-months spend trend chart
- **Per-category monthly budgets**, with over/under bars and a budget stamp
- **Recurring expenses** (rent, subscriptions) that auto-log once per month on a chosen day
- Dark mode toggle (saved in the browser)
- Toast notifications for every action
- Keyboard shortcut: press `/` anywhere to jump to the "add expense" field

## Run locally

```bash
pip install -r requirements.txt
python app.py
```

Open http://localhost:5000 — you'll be redirected to `/signup` the first time.

## Deploy (fastest: Render)

1. Push this folder to a GitHub repo.
2. Go to https://render.com → **New +** → **Web Service** → connect the repo.
3. Render auto-detects `render.yaml`. If asked manually, use:
   - Build command: `pip install -r requirements.txt`
   - Start command: `gunicorn app:app`
4. **Set a real `SECRET_KEY`** environment variable in Render's dashboard (used to sign login sessions) — don't rely on the `dev-secret-change-in-production` default.
5. Deploy. First build takes ~2 minutes. You get a live `.onrender.com` URL.

### Persisting data across deploys (recommended)

Render/Railway free-tier disks are ephemeral — a SQLite file gets wiped on redeploy. To keep
user accounts and expenses permanently:

1. Create a free Render **Postgres** database.
2. Copy its **Internal Database URL**.
3. Add it to your web service as an environment variable named `DATABASE_URL`.
4. Redeploy. The app automatically detects `DATABASE_URL` and uses Postgres instead of SQLite —
   no code changes needed.

If you don't set `DATABASE_URL`, the app just uses a local SQLite file, which is fine for a
demo/assignment but won't survive a redeploy.

### Alternative: Railway

1. https://railway.app → **New Project** → **Deploy from GitHub repo**.
2. Railway detects `Procfile` and `requirements.txt` automatically.
3. Add a Postgres plugin from the Railway dashboard and it will inject `DATABASE_URL` for you automatically.
4. Deploy, then generate a public domain from the service settings.

## Notes

- Monthly budget bars compare **this calendar month's** spend per category against the limit you set — not a rolling 30 days.
- Recurring expenses fire once per month, on or after the day you set (day is clamped 1–28 to avoid short-month issues), the first time the tracker is loaded on/after that day.
- The JSON "backup" button is a manual export — it is not an automated schedule. Real scheduled backups are best handled at the database level (Render's paid Postgres tiers include automatic backups) rather than in-app.
- `SECRET_KEY` should be set as a real, private environment variable in production — it signs login session cookies.
