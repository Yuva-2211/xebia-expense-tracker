# Master Prompt — SPENT. (Brutalist Expense Tracker)

> This is the single master prompt/spec for this project. It documents exactly what was
> asked for, the design system derived from it, and the technical plan used to build and
> deploy the app — so the whole build is reproducible from this one file.

## 1. Project Brief

Build a working expense tracker web app with:

- A **brutalist UI** with a **Gen Z sensibility** — raw borders, hard offset shadows,
  no rounded corners, no soft gradients — but **without neon colors**. The palette should
  feel like paper, ink, and stamped receipts rather than a cyberpunk dashboard.
- A **Python-based tech stack** end to end (backend, templating, no separate JS framework
  build step).
- **Fast, low-friction deployment** — must be deployable to a free host with a git push
  and near-zero configuration.
- **Full multi-user accounts** — sign up, log in, log out — with each user's data
  completely isolated from every other user's.

## 2. Functional Requirements

The app must let a signed-in user:

1. Add an expense with: title, amount, category, date, optional note.
2. Edit an existing expense (form switches into an "edit mode" pre-filled with its data).
3. See all expenses in a list, newest first.
4. Delete any expense (with a confirmation prompt first).
5. Filter the list by category and/or a date range.
6. Export all expenses to a CSV file, or a full JSON backup (expenses + budgets +
   recurring rules).
7. See a running total of all-time spend and current-month spend.
8. See month-over-month and week-over-week percentage change.
9. See a spend breakdown by category, plus "biggest single spend" and "top category"
   callouts.
10. See a spend trend across the last 6 months.
11. Set a **monthly budget per category**, and see a bar + stamp signal when a category
    goes over.
12. Define **recurring expenses** (rent, subscriptions) that auto-log once per month on a
    chosen day, without manual re-entry.
13. Toggle **dark mode**, persisted in the browser.
14. Sign up, log in, and log out; only ever see their own expenses, budgets, and
    recurring rules.

Non-goals (kept out to stay focused): password reset via email, OAuth/social login,
currency conversion, real-time multi-device sync, automated (as opposed to manual)
scheduled backups.

## 3. Design System (brutalist, Gen Z, non-neon)

**Palette (light / dark)**

| Token     | Light     | Dark      | Role                                |
|-----------|-----------|-----------|--------------------------------------|
| `paper`   | `#EDE7DA` | `#17140F` | page background                      |
| `ink`     | `#1B1B1B` | `#EDE7DA` | text, borders, shadows               |
| `card`    | `#FAF6EC` | `#211D16` | panel/receipt surface                |
| `brick`   | `#B5432F` | `#E2694F` | accent — over-budget, delete, errors |
| `mustard` | `#E4B73B` | `#E4B73B` | accent — primary action, tape        |
| `sage`    | `#6E7F5C` | `#9AB084` | accent — on-track / positive state   |

Dark mode is implemented by simply swapping the `paper`/`ink`/`card`/`brick`/`sage` CSS
variables under a `[data-theme="dark"]` selector — since every border, shadow, and text
color already derives from `--ink`, the whole UI inverts correctly with no markup changes.
No pure black-on-neon, no acid green, no electric blue — deliberately muted, "paper-stock"
brutalism rather than a rave-flyer look.

**Type**

- Display: `Space Grotesk` (700), bold uppercase headers.
- Body/data: `Space Mono`, monospace for the utilitarian, receipt/ledger feel.

**Layout language**

- 3–4px solid ink borders everywhere, zero border-radius.
- Hard offset drop shadows (`8px 8px 0 ink`), not blurred.
- Buttons physically "press" on click (`translate(5px,5px)` + shadow collapses to 0).
- Dashed lines used like perforation/receipt-tear edges between rows.
- Small pieces of "washi tape" (rotated rectangles) as a decorative Gen Z collage touch.
- Login/signup screens use a "ticket stub" card with a circular notch, echoing the
  receipt metaphor.

**Signature element**

A torn-receipt-style summary card ("RECEIPT #000n") with: total + monthly spend, week/
month % change, category breakdown bars, biggest-spend/top-category callouts, and a
rotated rubber-stamp badge (`ON TRACK` / `OVER BUDGET`) driven by whether any category
budget is currently exceeded.

## 4. Tech Stack

- **Backend:** Python 3, Flask
- **Auth:** Flask-Login (session-based), passwords hashed with Werkzeug's
  `generate_password_hash` / `check_password_hash` — never stored in plain text
- **ORM / storage:** Flask-SQLAlchemy — **SQLite** by default (zero external services),
  automatically switches to **Postgres** if a `DATABASE_URL` environment variable is
  present (e.g. Render/Railway managed Postgres), with no code changes required
- **Frontend:** Server-rendered Jinja2 templates + vanilla CSS/JS (no build step, no node
  toolchain — keeps deployment fast and dependency-free)
- **Prod server:** Gunicorn
- **Deployment target:** Render (free tier) via `render.yaml`, with Railway as a
  zero-config fallback (`Procfile` alone is enough)

## 5. File Structure

```
expense-tracker/
├── app.py                # Flask app, models, auth, and full REST API
├── requirements.txt       # Flask, Flask-Login, Flask-SQLAlchemy, psycopg2, gunicorn, dateutil
├── Procfile               # gunicorn start command (Railway/Heroku-style hosts)
├── render.yaml            # one-click Render service definition
├── templates/
│   ├── index.html         # main app shell (receipt, form, trend, budgets, recurring, list)
│   ├── login.html         # ticket-styled login page
│   └── signup.html        # ticket-styled signup page
├── static/
│   ├── style.css          # brutalist design system + dark mode variables
│   └── script.js           # fetch/render logic, no framework
├── README.md               # run + deploy + persistence instructions
└── PROMPT.md               # this file
```

## 6. Data Model

- **User** — `id, username (unique), password_hash, created_at`
- **Expense** — `id, user_id, title, amount, category, note, date, created_at, recurring_id`
- **CategoryBudget** — `id, user_id, category, monthly_limit` (unique per user+category)
- **RecurringExpense** — `id, user_id, title, amount, category, note, day_of_month, active, last_generated_month`

All expense/budget/recurring queries are scoped by `user_id = current_user.id`; ownership
is re-checked on every update/delete so one user can never read or modify another's data.

## 7. API Spec

| Method | Route                     | Body / Query                                     | Returns                                                                 |
|--------|---------------------------|-----------------------------------------------------|----------------------------------------------------------------------------|
| GET    | `/api/expenses`           | query: `category`, `start`, `end` (optional)         | `{expenses[], total, month_total, by_category, trend[], biggest_spend, top_category, comparison, budget_status[]}` |
| POST   | `/api/expenses`           | `{title, amount, category, date, note}`               | created expense row                                                        |
| PUT    | `/api/expenses/<id>`      | `{title, amount, category, date, note}`               | updated expense row                                                        |
| DELETE | `/api/expenses/<id>`      | –                                                      | `{ok: true}`                                                               |
| GET    | `/api/expenses/export`    | –                                                      | CSV file download                                                          |
| GET    | `/api/backup`             | –                                                      | JSON file download (expenses + budgets + recurring)                       |
| GET    | `/api/budgets`            | –                                                      | `{category: monthly_limit, ...}`                                          |
| POST   | `/api/budgets`            | `{category, monthly_limit}` (0 clears it)             | `{ok, category, monthly_limit}`                                            |
| GET    | `/api/recurring`          | –                                                      | list of recurring rules (also triggers due auto-logging)                  |
| POST   | `/api/recurring`          | `{title, amount, category, note, day_of_month}`       | created recurring rule                                                    |
| PUT    | `/api/recurring/<id>`     | `{active}`                                            | updated recurring rule (pause/resume)                                    |
| DELETE | `/api/recurring/<id>`     | –                                                      | `{ok: true}`                                                               |

`total`, `month_total`, `by_category`, `trend`, `biggest_spend`, `top_category`,
`comparison`, and `budget_status` are always computed from the **full** dataset,
regardless of the `category`/`start`/`end` filters applied to the returned `expenses`
list, so the receipt summary never gets out of sync with what the list is showing.

Auth routes: `GET/POST /signup`, `GET/POST /login`, `GET /logout`. All `/api/*` routes
and `/` require an active login session (`@login_required`); unauthenticated requests to
`/` redirect to `/login`.

## 8. Deployment Plan (fast path)

1. `git init` → push to GitHub.
2. Render → New Web Service → connect repo → auto-detected via `render.yaml`
   (`pip install -r requirements.txt` / `gunicorn app:app`).
3. Set a real `SECRET_KEY` environment variable (signs login sessions).
4. (Recommended) Add a free Render Postgres database and set its URL as `DATABASE_URL` so
   accounts/data survive redeploys — otherwise SQLite is used and resets on redeploy.
5. Live in ~2 minutes on a free `.onrender.com` URL.
6. Railway is the fallback: detects `Procfile` + `requirements.txt` with no manual config,
   and can auto-inject `DATABASE_URL` from its own Postgres plugin.

## 9. Acceptance Checklist

- [x] Sign up / log in / log out; per-user data isolation enforced on every query.
- [x] Add / edit / list / delete expenses works end to end, with confirm-before-delete.
- [x] Filter by category and date range; CSV export; full JSON backup.
- [x] Totals, month-over-month / week-over-week change, category breakdown, biggest
      spend, and top category are all correct and derived from the full dataset.
- [x] Per-category monthly budgets with over/under bars and a budget-driven stamp.
- [x] Recurring expenses auto-log once per month on their configured day.
- [x] UI uses brutalist conventions (hard shadows, thick borders, no radius) with a
      non-neon, paper/ink/mustard/brick/sage palette, in both light and dark mode.
- [x] Pure Python backend, no JS framework/build step.
- [x] Deployable via a single `render.yaml` / `Procfile`, with optional zero-code-change
      Postgres persistence via `DATABASE_URL`.
