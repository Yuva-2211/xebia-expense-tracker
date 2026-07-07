import csv
import io
import os
from datetime import datetime, date, timedelta

from dateutil.relativedelta import relativedelta
from flask import Flask, jsonify, request, render_template, Response, redirect, url_for, flash
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user,
    login_required, current_user
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CATEGORIES = ["Food", "Transport", "Shopping", "Bills", "Fun", "Other"]

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")

# --- Database: SQLite locally, Postgres in prod if DATABASE_URL is set ---
db_url = os.environ.get("DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'expenses.db')}")
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Log in to see your spending."


# ---------------------------------------------------------------- Models --

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    expenses = db.relationship("Expense", backref="user", lazy=True, cascade="all, delete-orphan")
    budgets = db.relationship("CategoryBudget", backref="user", lazy=True, cascade="all, delete-orphan")
    recurring = db.relationship("RecurringExpense", backref="user", lazy=True, cascade="all, delete-orphan")

    def set_password(self, raw):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw):
        return check_password_hash(self.password_hash, raw)


class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    note = db.Column(db.String(300))
    date = db.Column(db.String(10), nullable=False)  # ISO date string
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    recurring_id = db.Column(db.Integer, db.ForeignKey("recurring_expense.id"), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "amount": self.amount,
            "category": self.category,
            "note": self.note or "",
            "date": self.date,
            "is_recurring": self.recurring_id is not None,
        }


class CategoryBudget(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    monthly_limit = db.Column(db.Float, nullable=False)

    __table_args__ = (db.UniqueConstraint("user_id", "category", name="uq_user_category"),)


class RecurringExpense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    note = db.Column(db.String(300))
    day_of_month = db.Column(db.Integer, nullable=False, default=1)
    active = db.Column(db.Boolean, default=True)
    last_generated_month = db.Column(db.String(7))  # "YYYY-MM"

    generated = db.relationship("Expense", backref="recurring_source", lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "amount": self.amount,
            "category": self.category,
            "note": self.note or "",
            "day_of_month": self.day_of_month,
            "active": self.active,
        }


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


with app.app_context():
    db.create_all()


# ------------------------------------------------------------- Helpers ---

def generate_due_recurring(user):
    """Auto-log any recurring expense that's due and hasn't fired this month yet."""
    today = date.today()
    current_month = today.strftime("%Y-%m")
    due = RecurringExpense.query.filter_by(user_id=user.id, active=True).all()
    changed = False
    for r in due:
        if r.last_generated_month == current_month:
            continue
        if today.day < min(r.day_of_month, 28):
            continue
        exp_day = min(r.day_of_month, 28)
        exp_date = today.replace(day=exp_day).isoformat()
        db.session.add(Expense(
            user_id=user.id, title=r.title, amount=r.amount, category=r.category,
            note=(r.note or "recurring"), date=exp_date, recurring_id=r.id,
        ))
        r.last_generated_month = current_month
        changed = True
    if changed:
        db.session.commit()


def month_key(d):
    return d[:7]


def last_n_months(n):
    today = date.today().replace(day=1)
    return [(today - relativedelta(months=i)).strftime("%Y-%m") for i in range(n - 1, -1, -1)]


def validate_payload(data):
    title = (data.get("title") or "").strip()
    category = (data.get("category") or "Other").strip()
    note = (data.get("note") or "").strip()
    exp_date = (data.get("date") or "").strip() or date.today().isoformat()

    try:
        amount = float(data.get("amount"))
    except (TypeError, ValueError):
        return None, ("Amount must be a number.", 400)

    if not title:
        return None, ("Title is required.", 400)
    if amount <= 0:
        return None, ("Amount must be greater than zero.", 400)
    if category not in CATEGORIES:
        category = "Other"

    return {"title": title, "amount": amount, "category": category, "note": note, "date": exp_date}, None


# --------------------------------------------------------------- Auth ----

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm") or ""

        error = None
        if len(username) < 3:
            error = "Username needs at least 3 characters."
        elif len(password) < 6:
            error = "Password needs at least 6 characters."
        elif password != confirm:
            error = "Passwords don't match."
        elif User.query.filter_by(username=username).first():
            error = "That username is taken."

        if error:
            return render_template("signup.html", error=error, username=username)

        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        return redirect(url_for("index"))

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for("index"))

        return render_template("login.html", error="Wrong username or password.", username=username)

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


# --------------------------------------------------------------- Pages ---

@app.route("/")
@login_required
def index():
    return render_template("index.html", categories=CATEGORIES, username=current_user.username)


# ---------------------------------------------------------- Expenses API -

@app.route("/api/expenses", methods=["GET"])
@login_required
def list_expenses():
    generate_due_recurring(current_user)

    category = request.args.get("category")
    start = request.args.get("start")
    end = request.args.get("end")

    q = Expense.query.filter_by(user_id=current_user.id)
    if category and category != "All":
        q = q.filter_by(category=category)
    if start:
        q = q.filter(Expense.date >= start)
    if end:
        q = q.filter(Expense.date <= end)
    filtered = [e.to_dict() for e in q.order_by(Expense.date.desc(), Expense.id.desc()).all()]

    all_expenses = Expense.query.filter_by(user_id=current_user.id).all()
    total = sum(e.amount for e in all_expenses)

    by_category = {}
    for e in all_expenses:
        by_category[e.category] = by_category.get(e.category, 0) + e.amount

    today = date.today()
    month_prefix = today.strftime("%Y-%m")
    last_month_prefix = (today.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")

    month_total = sum(e.amount for e in all_expenses if e.date.startswith(month_prefix))
    last_month_total = sum(e.amount for e in all_expenses if e.date.startswith(last_month_prefix))

    week_start = today - timedelta(days=6)
    prev_week_start = today - timedelta(days=13)
    prev_week_end = today - timedelta(days=7)
    this_week_total = sum(e.amount for e in all_expenses if week_start.isoformat() <= e.date <= today.isoformat())
    last_week_total = sum(e.amount for e in all_expenses if prev_week_start.isoformat() <= e.date <= prev_week_end.isoformat())

    months = last_n_months(6)
    trend = {m: 0.0 for m in months}
    for e in all_expenses:
        mk = month_key(e.date)
        if mk in trend:
            trend[mk] += e.amount

    this_month_expenses = [e for e in all_expenses if e.date.startswith(month_prefix)]
    pool = this_month_expenses or all_expenses
    biggest = max(pool, key=lambda e: e.amount, default=None)

    month_by_category = {}
    for e in this_month_expenses:
        month_by_category[e.category] = month_by_category.get(e.category, 0) + e.amount
    top_category = max(month_by_category.items(), key=lambda kv: kv[1], default=(None, 0))

    budgets = CategoryBudget.query.filter_by(user_id=current_user.id).all()
    budget_status = []
    for b in budgets:
        spent = month_by_category.get(b.category, 0)
        budget_status.append({
            "category": b.category,
            "limit": b.monthly_limit,
            "spent": round(spent, 2),
            "over": spent > b.monthly_limit,
        })

    def pct_change(curr, prev):
        if prev == 0:
            return None
        return round(((curr - prev) / prev) * 100, 1)

    return jsonify({
        "expenses": filtered,
        "total": round(total, 2),
        "month_total": round(month_total, 2),
        "by_category": {k: round(v, 2) for k, v in by_category.items()},
        "trend": [{"month": m, "amount": round(v, 2)} for m, v in trend.items()],
        "biggest_spend": {"title": biggest.title, "amount": round(biggest.amount, 2)} if biggest else None,
        "top_category": {"category": top_category[0], "amount": round(top_category[1], 2)} if top_category[0] else None,
        "comparison": {
            "month_change_pct": pct_change(month_total, last_month_total),
            "week_change_pct": pct_change(this_week_total, last_week_total),
            "this_week": round(this_week_total, 2),
            "last_week": round(last_week_total, 2),
            "last_month": round(last_month_total, 2),
        },
        "budget_status": budget_status,
    })


@app.route("/api/expenses", methods=["POST"])
@login_required
def add_expense():
    clean, error = validate_payload(request.get_json(force=True))
    if error:
        return jsonify({"error": error[0]}), error[1]

    e = Expense(user_id=current_user.id, **clean)
    db.session.add(e)
    db.session.commit()
    return jsonify(e.to_dict()), 201


@app.route("/api/expenses/<int:expense_id>", methods=["PUT"])
@login_required
def update_expense(expense_id):
    clean, error = validate_payload(request.get_json(force=True))
    if error:
        return jsonify({"error": error[0]}), error[1]

    e = Expense.query.filter_by(id=expense_id, user_id=current_user.id).first()
    if not e:
        return jsonify({"error": "Expense not found."}), 404

    for k, v in clean.items():
        setattr(e, k, v)
    db.session.commit()
    return jsonify(e.to_dict())


@app.route("/api/expenses/<int:expense_id>", methods=["DELETE"])
@login_required
def delete_expense(expense_id):
    e = Expense.query.filter_by(id=expense_id, user_id=current_user.id).first()
    if e:
        db.session.delete(e)
        db.session.commit()
    return jsonify({"ok": True})


@app.route("/api/expenses/export", methods=["GET"])
@login_required
def export_expenses():
    rows = Expense.query.filter_by(user_id=current_user.id).order_by(Expense.date.desc(), Expense.id.desc()).all()
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["id", "title", "amount", "category", "note", "date"])
    for r in rows:
        writer.writerow([r.id, r.title, r.amount, r.category, r.note, r.date])
    filename = f"spent-export-{date.today().isoformat()}.csv"
    return Response(buffer.getvalue(), mimetype="text/csv",
                     headers={"Content-Disposition": f"attachment; filename={filename}"})


@app.route("/api/backup", methods=["GET"])
@login_required
def backup_all():
    """Manual full-data JSON backup (expenses + budgets + recurring rules)."""
    import json
    payload = {
        "username": current_user.username,
        "exported_at": datetime.utcnow().isoformat(),
        "expenses": [e.to_dict() for e in Expense.query.filter_by(user_id=current_user.id).all()],
        "budgets": [{"category": b.category, "monthly_limit": b.monthly_limit}
                     for b in CategoryBudget.query.filter_by(user_id=current_user.id).all()],
        "recurring": [r.to_dict() for r in RecurringExpense.query.filter_by(user_id=current_user.id).all()],
    }
    filename = f"spent-backup-{date.today().isoformat()}.json"
    return Response(json.dumps(payload, indent=2), mimetype="application/json",
                     headers={"Content-Disposition": f"attachment; filename={filename}"})


# ---------------------------------------------------------- Budgets API --

@app.route("/api/budgets", methods=["GET"])
@login_required
def list_budgets():
    budgets = CategoryBudget.query.filter_by(user_id=current_user.id).all()
    return jsonify({b.category: b.monthly_limit for b in budgets})


@app.route("/api/budgets", methods=["POST"])
@login_required
def set_budget():
    data = request.get_json(force=True)
    category = (data.get("category") or "").strip()
    if category not in CATEGORIES:
        return jsonify({"error": "Unknown category."}), 400
    try:
        limit = float(data.get("monthly_limit"))
    except (TypeError, ValueError):
        return jsonify({"error": "Limit must be a number."}), 400
    if limit < 0:
        return jsonify({"error": "Limit can't be negative."}), 400

    existing = CategoryBudget.query.filter_by(user_id=current_user.id, category=category).first()
    if limit == 0:
        if existing:
            db.session.delete(existing)
            db.session.commit()
        return jsonify({"ok": True, "removed": True})

    if existing:
        existing.monthly_limit = limit
    else:
        db.session.add(CategoryBudget(user_id=current_user.id, category=category, monthly_limit=limit))
    db.session.commit()
    return jsonify({"ok": True, "category": category, "monthly_limit": limit})


# -------------------------------------------------------- Recurring API --

@app.route("/api/recurring", methods=["GET"])
@login_required
def list_recurring():
    generate_due_recurring(current_user)
    rows = RecurringExpense.query.filter_by(user_id=current_user.id).order_by(RecurringExpense.day_of_month).all()
    return jsonify([r.to_dict() for r in rows])


@app.route("/api/recurring", methods=["POST"])
@login_required
def add_recurring():
    data = request.get_json(force=True)
    clean, error = validate_payload({**data, "date": date.today().isoformat()})
    if error:
        return jsonify({"error": error[0]}), error[1]

    try:
        day = int(data.get("day_of_month", 1))
    except (TypeError, ValueError):
        return jsonify({"error": "Day of month must be a number."}), 400
    day = max(1, min(day, 28))

    r = RecurringExpense(
        user_id=current_user.id, title=clean["title"], amount=clean["amount"],
        category=clean["category"], note=clean["note"], day_of_month=day, active=True,
    )
    db.session.add(r)
    db.session.commit()
    return jsonify(r.to_dict()), 201


@app.route("/api/recurring/<int:rec_id>", methods=["PUT"])
@login_required
def toggle_recurring(rec_id):
    r = RecurringExpense.query.filter_by(id=rec_id, user_id=current_user.id).first()
    if not r:
        return jsonify({"error": "Not found."}), 404
    data = request.get_json(force=True)
    if "active" in data:
        r.active = bool(data["active"])
    db.session.commit()
    return jsonify(r.to_dict())


@app.route("/api/recurring/<int:rec_id>", methods=["DELETE"])
@login_required
def delete_recurring(rec_id):
    r = RecurringExpense.query.filter_by(id=rec_id, user_id=current_user.id).first()
    if r:
        db.session.delete(r)
        db.session.commit()
    return jsonify({"ok": True})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
