const form = document.getElementById('expenseForm');
const listEl = document.getElementById('expenseList');
const emptyState = document.getElementById('emptyState');
const totalEl = document.getElementById('totalAmount');
const monthEl = document.getElementById('monthAmount');
const catBreakdown = document.getElementById('categoryBreakdown');
const stampEl = document.getElementById('stamp');
const receiptNo = document.getElementById('receiptNo');
const formError = document.getElementById('formError');
const trendChart = document.getElementById('trendChart');
const monthChangeRow = document.getElementById('monthChangeRow');
const weekChangeRow = document.getElementById('weekChangeRow');
const biggestSpendCallout = document.getElementById('biggestSpendCallout');
const topCategoryCallout = document.getElementById('topCategoryCallout');
const toastStack = document.getElementById('toastStack');

const addPanel = document.getElementById('addPanel');
const formTitle = document.getElementById('formTitle');
const editIdInput = document.getElementById('editId');
const submitBtn = document.getElementById('submitBtn');
const cancelEditBtn = document.getElementById('cancelEditBtn');

const filterCategory = document.getElementById('filterCategory');
const filterStart = document.getElementById('filterStart');
const filterEnd = document.getElementById('filterEnd');
const clearFiltersBtn = document.getElementById('clearFiltersBtn');
const exportBtn = document.getElementById('exportBtn');
const backupBtn = document.getElementById('backupBtn');
const themeToggle = document.getElementById('themeToggle');

const budgetsList = document.getElementById('budgetsList');
const recurringForm = document.getElementById('recurringForm');
const recurringList = document.getElementById('recurringList');
const recurringEmpty = document.getElementById('recurringEmpty');

const dateInput = document.getElementById('date');
dateInput.valueAsDate = new Date();

const CATEGORIES = Array.from(document.getElementById('category').options).map(o => o.value);

// ---------------------------------------------------------------- Utils --

function money(n) { return '₹' + Number(n).toFixed(2); }
function tagClass(cat) { return 'tag tag-' + cat.toLowerCase(); }

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function showToast(message, type = 'success') {
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.textContent = message;
  toastStack.appendChild(el);
  setTimeout(() => el.remove(), 3200);
}

// ------------------------------------------------------------ Dark mode --

const THEME_KEY = 'spent-theme';
function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  themeToggle.textContent = theme === 'dark' ? '◑' : '◐';
}
applyTheme(localStorage.getItem(THEME_KEY) || 'light');

themeToggle.addEventListener('click', () => {
  const next = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
  localStorage.setItem(THEME_KEY, next);
  applyTheme(next);
});

// --------------------------------------------------------- Keyboard nav --

document.addEventListener('keydown', (ev) => {
  if (ev.key !== '/') return;
  const tag = (ev.target.tagName || '').toLowerCase();
  if (tag === 'input' || tag === 'select' || tag === 'textarea') return;
  ev.preventDefault();
  document.getElementById('title').focus();
});

// ------------------------------------------------------------- Expenses --

function buildQuery() {
  const params = new URLSearchParams();
  if (filterCategory.value && filterCategory.value !== 'All') params.set('category', filterCategory.value);
  if (filterStart.value) params.set('start', filterStart.value);
  if (filterEnd.value) params.set('end', filterEnd.value);
  const qs = params.toString();
  return qs ? `?${qs}` : '';
}

async function loadExpenses() {
  const res = await fetch('/api/expenses' + buildQuery());
  if (res.status === 401) { window.location.href = '/login'; return; }
  const data = await res.json();
  render(data);
}

function changeLine(label, pct) {
  if (pct === null || pct === undefined) return `<span>${label}</span><span>–</span>`;
  const arrow = pct > 0 ? '▲' : pct < 0 ? '▼' : '·';
  const sign = pct > 0 ? '+' : '';
  return `<span>${label}</span><span>${arrow} ${sign}${pct}%</span>`;
}

function render(data) {
  const {
    expenses, total, month_total, by_category, trend,
    biggest_spend, top_category, comparison, budget_status,
  } = data;

  totalEl.textContent = money(total);
  monthEl.textContent = money(month_total);
  receiptNo.textContent = String(expenses.length).padStart(4, '0');

  monthChangeRow.innerHTML = changeLine('VS LAST MONTH', comparison.month_change_pct);
  weekChangeRow.innerHTML = changeLine('VS LAST WEEK', comparison.week_change_pct);

  catBreakdown.innerHTML = '';
  const maxCat = Math.max(1, ...Object.values(by_category));
  Object.entries(by_category).sort((a, b) => b[1] - a[1]).forEach(([cat, amt]) => {
    const row = document.createElement('div');
    row.className = 'cat-row';
    row.innerHTML = `
      <span>${cat}</span>
      <span class="cat-bar-track"><span class="cat-bar-fill" style="width:${(amt / maxCat) * 100}%"></span></span>
      <span>${money(amt)}</span>
    `;
    catBreakdown.appendChild(row);
  });

  biggestSpendCallout.innerHTML = biggest_spend
    ? `BIGGEST SPEND: <b>${escapeHtml(biggest_spend.title)}</b> — ${money(biggest_spend.amount)}`
    : 'BIGGEST SPEND: —';
  topCategoryCallout.innerHTML = top_category
    ? `TOP CATEGORY: <b>${top_category.category}</b> — ${money(top_category.amount)}`
    : 'TOP CATEGORY: —';

  const anyOverBudget = (budget_status || []).some(b => b.over);
  if (anyOverBudget) {
    stampEl.textContent = 'OVER BUDGET';
    stampEl.className = 'stamp over';
  } else {
    stampEl.textContent = 'ON TRACK';
    stampEl.className = 'stamp ok';
  }

  renderTrend(trend);
  renderBudgets(budget_status || []);

  listEl.innerHTML = '';
  emptyState.style.display = expenses.length ? 'none' : 'block';

  expenses.forEach((e) => {
    const li = document.createElement('li');
    li.className = 'expense-row';
    li.dataset.id = e.id;
    li.innerHTML = `
      <span class="expense-title">${escapeHtml(e.title)}${e.is_recurring ? ' 🔁' : ''}${e.note ? `<span class="expense-note">${escapeHtml(e.note)}</span>` : ''}</span>
      <span><span class="${tagClass(e.category)}">${e.category}</span></span>
      <span>${e.date}</span>
      <span>${money(e.amount)}</span>
      <span class="row-actions">
        <button class="edit-btn" data-id="${e.id}" title="edit">✎</button>
        <button class="del-btn" data-id="${e.id}" title="delete">×</button>
      </span>
    `;
    listEl.appendChild(li);
  });

  document.querySelectorAll('.del-btn').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const row = btn.closest('.expense-row');
      const title = row.querySelector('.expense-title').childNodes[0].textContent.trim();
      if (!confirm(`Delete "${title}"? This can't be undone.`)) return;
      await fetch(`/api/expenses/${btn.dataset.id}`, { method: 'DELETE' });
      if (editIdInput.value === btn.dataset.id) exitEditMode();
      showToast('Expense deleted.', 'error');
      loadExpenses();
    });
  });

  document.querySelectorAll('.edit-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      const exp = expenses.find((e) => String(e.id) === btn.dataset.id);
      if (exp) enterEditMode(exp);
    });
  });
}

function renderTrend(trend) {
  trendChart.innerHTML = '';
  if (!trend || !trend.length) return;
  const max = Math.max(1, ...trend.map((t) => t.amount));
  const currentMonth = new Date().toISOString().slice(0, 7);

  trend.forEach((t) => {
    const wrap = document.createElement('div');
    wrap.className = 'trend-bar-wrap';
    const heightPct = Math.max(2, (t.amount / max) * 100);
    const isCurrent = t.month === currentMonth;
    const label = new Date(t.month + '-01').toLocaleDateString('en-US', { month: 'short' });
    wrap.innerHTML = `
      <span class="trend-amt">${t.amount > 0 ? Math.round(t.amount) : ''}</span>
      <div class="trend-bar ${isCurrent ? 'current' : ''}" style="height:${heightPct}%"></div>
      <span class="trend-label">${label}</span>
    `;
    trendChart.appendChild(wrap);
  });
}

function enterEditMode(exp) {
  editIdInput.value = exp.id;
  document.getElementById('title').value = exp.title;
  document.getElementById('amount').value = exp.amount;
  document.getElementById('category').value = exp.category;
  document.getElementById('date').value = exp.date;
  document.getElementById('note').value = exp.note || '';

  formTitle.textContent = 'EDIT SPEND';
  submitBtn.textContent = 'SAVE CHANGES';
  cancelEditBtn.style.display = 'inline-block';
  addPanel.classList.add('editing');
  formError.textContent = '';

  document.querySelectorAll('.expense-row').forEach((row) => {
    row.classList.toggle('editing-row', row.dataset.id === String(exp.id));
  });

  addPanel.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

function exitEditMode() {
  editIdInput.value = '';
  form.reset();
  dateInput.valueAsDate = new Date();
  formTitle.textContent = 'ADD A SPEND';
  submitBtn.textContent = 'LOG IT';
  cancelEditBtn.style.display = 'none';
  addPanel.classList.remove('editing');
  document.querySelectorAll('.expense-row').forEach((row) => row.classList.remove('editing-row'));
}

cancelEditBtn.addEventListener('click', exitEditMode);

form.addEventListener('submit', async (ev) => {
  ev.preventDefault();
  formError.textContent = '';

  const payload = {
    title: document.getElementById('title').value,
    amount: document.getElementById('amount').value,
    category: document.getElementById('category').value,
    date: document.getElementById('date').value,
    note: document.getElementById('note').value,
  };

  const editId = editIdInput.value;
  const url = editId ? `/api/expenses/${editId}` : '/api/expenses';
  const method = editId ? 'PUT' : 'POST';

  const res = await fetch(url, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const err = await res.json();
    formError.textContent = err.error || 'Something went wrong.';
    showToast(err.error || 'Something went wrong.', 'error');
    return;
  }

  showToast(editId ? 'Expense updated.' : 'Logged it.', 'success');
  exitEditMode();
  loadExpenses();
});

filterCategory.addEventListener('change', loadExpenses);
filterStart.addEventListener('change', loadExpenses);
filterEnd.addEventListener('change', loadExpenses);

clearFiltersBtn.addEventListener('click', () => {
  filterCategory.value = 'All';
  filterStart.value = '';
  filterEnd.value = '';
  loadExpenses();
});

exportBtn.addEventListener('click', () => { window.location.href = '/api/expenses/export'; });
backupBtn.addEventListener('click', () => { window.location.href = '/api/backup'; });

// -------------------------------------------------------------- Budgets --

async function loadBudgets() {
  const res = await fetch('/api/budgets');
  const budgets = await res.json();
  renderBudgetInputs(budgets);
}

function renderBudgetInputs(budgets) {
  budgetsList.innerHTML = '';
  CATEGORIES.forEach((cat) => {
    const row = document.createElement('div');
    row.className = 'budget-row';
    row.innerHTML = `
      <span>${cat}</span>
      <input type="number" min="0" step="1" placeholder="no limit" value="${budgets[cat] ?? ''}" data-cat="${cat}">
      <button class="btn-clear" data-cat="${cat}">SAVE</button>
    `;
    budgetsList.appendChild(row);
  });

  budgetsList.querySelectorAll('button').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const cat = btn.dataset.cat;
      const input = budgetsList.querySelector(`input[data-cat="${cat}"]`);
      const value = input.value === '' ? 0 : parseFloat(input.value);
      const res = await fetch('/api/budgets', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ category: cat, monthly_limit: value }),
      });
      if (res.ok) {
        showToast(value > 0 ? `${cat} budget set to ${money(value)}.` : `${cat} budget cleared.`, 'success');
        loadExpenses();
      } else {
        const err = await res.json();
        showToast(err.error || 'Could not save budget.', 'error');
      }
    });
  });
}

function renderBudgets(statusList) {
  // Overlay spend-vs-limit bars onto whichever budget rows currently have a limit set.
  statusList.forEach((b) => {
    const row = [...budgetsList.querySelectorAll('.budget-row')].find(
      (r) => r.querySelector('input').dataset.cat === b.category
    );
    if (!row) return;
    let track = row.querySelector('.budget-bar-track');
    if (!track) {
      track = document.createElement('div');
      track.className = 'budget-bar-track';
      track.innerHTML = '<div class="budget-bar-fill"></div>';
      row.appendChild(track);
    }
    const fill = track.querySelector('.budget-bar-fill');
    const pct = Math.min(100, (b.spent / b.limit) * 100);
    fill.style.width = pct + '%';
    fill.classList.toggle('over', b.over);
  });
}

// ------------------------------------------------------------ Recurring --

async function loadRecurring() {
  const res = await fetch('/api/recurring');
  const items = await res.json();
  renderRecurring(items);
}

function renderRecurring(items) {
  recurringList.innerHTML = '';
  recurringEmpty.style.display = items.length ? 'none' : 'block';

  items.forEach((r) => {
    const li = document.createElement('li');
    li.className = 'recurring-row' + (r.active ? '' : ' inactive');
    li.innerHTML = `
      <span>${escapeHtml(r.title)}</span>
      <span><span class="${tagClass(r.category)}">${r.category}</span></span>
      <span>day ${r.day_of_month} · ${money(r.amount)}</span>
      <button class="rec-toggle-btn" data-id="${r.id}" data-active="${r.active}" title="${r.active ? 'pause' : 'resume'}">${r.active ? '⏸' : '▶'}</button>
      <button class="rec-del-btn" data-id="${r.id}" title="delete">×</button>
    `;
    recurringList.appendChild(li);
  });

  recurringList.querySelectorAll('.rec-toggle-btn').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const active = btn.dataset.active !== 'true';
      await fetch(`/api/recurring/${btn.dataset.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ active }),
      });
      showToast(active ? 'Recurring spend resumed.' : 'Recurring spend paused.', 'success');
      loadRecurring();
    });
  });

  recurringList.querySelectorAll('.rec-del-btn').forEach((btn) => {
    btn.addEventListener('click', async () => {
      if (!confirm('Remove this recurring spend? Already-logged expenses stay.')) return;
      await fetch(`/api/recurring/${btn.dataset.id}`, { method: 'DELETE' });
      showToast('Recurring spend removed.', 'error');
      loadRecurring();
    });
  });
}

recurringForm.addEventListener('submit', async (ev) => {
  ev.preventDefault();
  const payload = {
    title: document.getElementById('recTitle').value,
    amount: document.getElementById('recAmount').value,
    category: document.getElementById('recCategory').value,
    day_of_month: document.getElementById('recDay').value,
  };
  const res = await fetch('/api/recurring', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json();
    showToast(err.error || 'Could not add recurring spend.', 'error');
    return;
  }
  recurringForm.reset();
  showToast('Recurring spend added.', 'success');
  loadRecurring();
  loadExpenses();
});

// ---------------------------------------------------------------- Init --

loadBudgets().then(loadExpenses);
loadRecurring();
