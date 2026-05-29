from pathlib import Path
import re
import uuid
import json

import altair as alt
import pandas as pd
import streamlit as st

PAGE_TITLE = "STACK Project Cloud"
DATA_FILE = Path(__file__).parent / "projects.csv"
TEAM_MEMBERS_FILE = Path(__file__).parent / "team_members.csv"
TASKS_FILE = Path(__file__).parent / "tasks.csv"
TIMESHEETS_FILE = Path(__file__).parent / "timesheets.csv"
ROLES_FILE = Path(__file__).parent / "roles.csv"
ESTIMATES_FILE = Path(__file__).parent / "estimates.csv"
ESTIMATE_LINES_FILE = Path(__file__).parent / "estimate_lines.csv"
ESTIMATE_DISB_FILE = Path(__file__).parent / "estimate_disbursements.csv"
COMPANIES_FILE = Path(__file__).parent / "companies.csv"
CONTACTS_FILE = Path(__file__).parent / "contacts.csv"

STAGES = ["Concept", "Design Development", "Tender", "Construction", "Handover", "Code of Compliance"]
STATUSES = ["On track", "At risk", "Delayed", "Complete"]
COMPLIANCE_TASKS = ["Fire safety sign-off", "Electrical certificate", "Plumbing certificate", "OHS inspection", "Code compliance certificate"]
COLUMNS = ["Project ID", "Project name", "Client", "Company ID", "Location", "Project manager",
           "Start date", "Target completion", "Stage", "Status", "Budget", "Fee", "Phase fees",
           "Weekly hours allocated", "Member hours allocation", "Phase schedule", "Milestones",
           "Team members", "Compliance checklist", "Notes", "Last updated"]
TASK_COLUMNS = ["Task ID", "Project ID", "Project name", "Task name", "Team", "Assigned to", "Status", "Notes", "Last updated"]
TIMESHEET_COLUMNS = ["Entry ID", "Project ID", "Project name", "Phase", "Team member", "Role", "Date", "Hours", "Rate", "Notes", "Invoiced"]
ESTIMATE_COLUMNS = ["Estimate ID", "Estimate name", "Client", "Company ID", "Project ID", "Project name", "Margin %", "Notes", "Created", "Last updated"]
ESTIMATE_LINE_COLUMNS = ["Line ID", "Estimate ID", "Phase", "Role", "Hours", "Rate"]
ESTIMATE_DISB_COLUMNS = ["Disb ID", "Estimate ID", "Description", "Type", "Value"]
COMPANY_COLUMNS = ["Company ID", "Name", "Status", "Industry", "Website", "Phone", "Billing address", "Postal address", "Referral source", "Notes", "Tags", "Custom fields", "Created", "Last updated"]
CONTACT_COLUMNS = ["Contact ID", "Company ID", "Company name", "First name", "Last name", "Title", "Email", "Phone", "Mobile", "Address", "Notes", "Tags", "Custom fields", "Is primary", "Created", "Last updated"]
INVOICE_COLUMNS = ["Invoice ID", "Company ID", "Project ID", "Project name", "Invoice number", "Issue date", "Due date", "Status", "Payment details", "Notes"]
INVOICE_LINE_COLUMNS = ["Line ID", "Invoice ID", "Description", "Quantity", "Unit price", "Amount"]
TIMESHEET_LOCK_PASSWORD = "test"

TASK_TEAMS = ["Design", "Project Management"]
TASK_STATUSES = ["Not started", "Ongoing", "Completed"]
TASK_STATUS_COLOURS = {"Not started": "#aaaaaa", "Ongoing": "#f39c12", "Completed": "#2ecc71"}
CLIENT_STATUSES = ["Active", "Prospect", "Lead", "Inactive"]
CLIENT_STATUS_COLOURS = {"Active": "#2ecc71", "Prospect": "#3498db", "Lead": "#f39c12", "Inactive": "#aaaaaa"}
INDUSTRIES = ["Architecture", "Interior Design", "Construction", "Engineering", "Property Development", "Retail", "Hospitality", "Education", "Healthcare", "Government", "Other"]
REFERRAL_SOURCES = ["Word of mouth", "Website", "Social media", "Returning client", "Referral", "Directory", "Other"]
DEFAULT_ROLES = {"Technician": 85.0, "Graduate": 95.0, "Intermediate Designer": 120.0, "Senior Designer": 150.0, "Project Manager": 140.0, "Site Manager": 130.0, "Director": 200.0}

PAGES = ["Project Tracker", "Task Tracker", "Timesheets", "Fee Estimator", "Clients", "Resourcing"]
RESOURCE_ALLOC_FILE = Path(__file__).parent / "resource_allocations.csv"
RESOURCE_ALLOC_COLUMNS = ["Alloc ID", "Team member", "Project ID", "Project name", "Week start", "Projected hours", "Last updated"]
HOLIDAYS_FILE = Path(__file__).parent / "holidays.csv"
HOLIDAY_COLUMNS = ["Date", "Name"]
LEAVE_FILE = Path(__file__).parent / "leave.csv"
LEAVE_COLUMNS = ["Leave ID", "Team member", "Date", "Type", "Notes"]
LEAVE_TYPES = ["Annual leave", "Sick leave", "Unpaid leave", "Public holiday (personal)", "Other"]

# ── helpers ───────────────────────────────────────────────────────────────────

def parse_budget(value):
    if pd.isna(value) or value == "": return 0.0
    try: return float(str(value).replace(",", "").replace("$", "").strip())
    except: return 0.0

def format_budget(value): return f"${parse_budget(value):,.2f}"

def parse_weekly_hours(value):
    if pd.isna(value) or value == "": return 0.0
    try: return float(str(value).replace(",", "").strip())
    except: return 0.0

def parse_team_members(value):
    if not value or pd.isna(value): return []
    return [i.strip() for i in str(value).split(";") if i.strip()]

def normalize_team_members(values): return "; ".join(sorted(values))

def parse_member_hours(value):
    if not value or pd.isna(value): return {}
    out = {}
    for line in str(value).splitlines():
        if ":" not in line: continue
        m, h = [p.strip() for p in line.split(":", 1)]
        h2 = parse_weekly_hours(h)
        if m and h2 > 0: out[m] = h2
    return out

def normalize_member_hours(d): return "\n".join(f"{m}: {h}" for m, h in sorted(d.items()))

def compliance_to_list(value):
    if not value or pd.isna(value): return []
    return [i.strip() for i in str(value).split(";") if i.strip()]

def normalize_checklist(values): return "; ".join(sorted(values))

def compliance_progress(value):
    done = len([t for t in compliance_to_list(value) if t in COMPLIANCE_TASKS])
    return int((done / len(COMPLIANCE_TASKS)) * 100) if COMPLIANCE_TASKS else 0

def stage_progress(stage): return int(((STAGES.index(stage) + 1) / len(STAGES)) * 100) if stage in STAGES else 0

def parse_milestones(value):
    if not value or pd.isna(value): return []
    return [l.strip() for l in str(value).splitlines() if l.strip()]

def normalize_milestones(value): return "\n".join(parse_milestones(value))

def milestone_progress(value):
    ms = parse_milestones(value)
    if not ms: return 0
    done = sum(1 for m in ms if m.endswith("✓") or m.startswith("[x]") or m.startswith("[X]") or m.lower().endswith("complete"))
    return int((done / len(ms)) * 100)

def parse_phase_schedule(value):
    phases = []
    if not value or pd.isna(value): return phases
    for line in str(value).splitlines():
        c = line.strip()
        if not c or ":" not in c: continue
        stage, rest = [p.strip() for p in c.split(":", 1)]
        match = re.search(r"(\d{4}-\d{2}-\d{2})\s*(?:to|\-|–|—)\s*(\d{4}-\d{2}-\d{2})", rest)
        if not match: continue
        s = pd.to_datetime(match.group(1), errors="coerce")
        e = pd.to_datetime(match.group(2), errors="coerce")
        if pd.isna(s) or pd.isna(e): continue
        phases.append({"Stage": stage, "Start date": s, "Target completion": e, "Duration weeks": round((e - s).days / 7, 1)})
    return phases

def normalize_phase_schedule(value): return "\n".join(l.strip() for l in str(value).splitlines() if l.strip())

def parse_date(value, fallback=None):
    p = pd.to_datetime(value, errors="coerce")
    return fallback if pd.isna(p) else p.date()

def create_id(): return uuid.uuid4().hex[:8]

def parse_custom_fields(value):
    if not value or pd.isna(value) or value == "": return []
    try: return json.loads(value)
    except: return []

def serialize_custom_fields(fields): return json.dumps(fields)

def parse_tags(value):
    if not value or pd.isna(value): return []
    return [t.strip() for t in str(value).split(",") if t.strip()]

def normalize_tags(tags): return ", ".join(sorted(set(tags)))

# ── data loaders ──────────────────────────────────────────────────────────────

def ensure_file(path, columns):
    if not path.exists(): pd.DataFrame(columns=columns).to_csv(path, index=False)

def load_df(path, columns):
    ensure_file(path, columns)
    df = pd.read_csv(path, dtype=str).fillna("")
    for c in columns:
        if c not in df.columns: df[c] = ""
    return df[columns]

def load_projects(): return load_df(DATA_FILE, COLUMNS)
def save_projects(df): df.to_csv(DATA_FILE, index=False)

def load_team_members():
    ensure_file(TEAM_MEMBERS_FILE, ["Team member", "Role"])
    df = pd.read_csv(TEAM_MEMBERS_FILE, dtype=str).fillna("")
    for c in ["Team member", "Role"]:
        if c not in df.columns: df[c] = ""
    return df

def save_team_members_df(df): df.to_csv(TEAM_MEMBERS_FILE, index=False)

def load_roles():
    ensure_file(ROLES_FILE, ["Role", "Hourly rate"])
    df = pd.read_csv(ROLES_FILE, dtype=str).fillna("")
    if df.empty:
        df = pd.DataFrame([{"Role": r, "Hourly rate": str(rate)} for r, rate in DEFAULT_ROLES.items()])
        df.to_csv(ROLES_FILE, index=False)
    else:
        existing = set(df["Role"].tolist())
        missing = [{"Role": r, "Hourly rate": str(rate)} for r, rate in DEFAULT_ROLES.items() if r not in existing]
        if missing:
            df = pd.concat([df, pd.DataFrame(missing)], ignore_index=True)
            df.to_csv(ROLES_FILE, index=False)
    return df

def save_roles(df): df.to_csv(ROLES_FILE, index=False)

def get_role_rates(roles_df):
    out = {}
    for _, row in roles_df.iterrows():
        try: out[row["Role"]] = float(row["Hourly rate"])
        except: pass
    return out

def load_tasks(): return load_df(TASKS_FILE, TASK_COLUMNS)
def save_tasks(df): df.to_csv(TASKS_FILE, index=False)

def load_timesheets():
    ensure_file(TIMESHEETS_FILE, TIMESHEET_COLUMNS)
    df = pd.read_csv(TIMESHEETS_FILE, dtype=str).fillna("")
    for c in TIMESHEET_COLUMNS:
        if c not in df.columns: df[c] = ""
    return df[TIMESHEET_COLUMNS]

def save_timesheets(df): df.to_csv(TIMESHEETS_FILE, index=False)

def load_estimates(): return load_df(ESTIMATES_FILE, ESTIMATE_COLUMNS)
def save_estimates(df): df.to_csv(ESTIMATES_FILE, index=False)

def load_estimate_lines(): return load_df(ESTIMATE_LINES_FILE, ESTIMATE_LINE_COLUMNS)
def save_estimate_lines(df): df.to_csv(ESTIMATE_LINES_FILE, index=False)

def load_estimate_disb(): return load_df(ESTIMATE_DISB_FILE, ESTIMATE_DISB_COLUMNS)
def save_estimate_disb(df): df.to_csv(ESTIMATE_DISB_FILE, index=False)

def load_companies(): return load_df(COMPANIES_FILE, COMPANY_COLUMNS)
def save_companies(df): df.to_csv(COMPANIES_FILE, index=False)

def load_contacts(): return load_df(CONTACTS_FILE, CONTACT_COLUMNS)
def save_contacts(df): df.to_csv(CONTACTS_FILE, index=False)

def load_resource_allocs(): return load_df(RESOURCE_ALLOC_FILE, RESOURCE_ALLOC_COLUMNS)
def save_resource_allocs(df): df.to_csv(RESOURCE_ALLOC_FILE, index=False)

def load_holidays(): return load_df(HOLIDAYS_FILE, HOLIDAY_COLUMNS)
def save_holidays(df): df.to_csv(HOLIDAYS_FILE, index=False)

def load_leave(): return load_df(LEAVE_FILE, LEAVE_COLUMNS)
def save_leave(df): df.to_csv(LEAVE_FILE, index=False)

def holiday_dates_set(holidays_df):
    out = set()
    if holidays_df.empty: return out
    for _, r in holidays_df.iterrows():
        d = pd.to_datetime(r["Date"], errors="coerce")
        if not pd.isna(d): out.add(d.date())
    return out

def leave_dates_for_member(member, leave_df):
    out = set()
    if leave_df.empty: return out
    for _, r in leave_df[leave_df["Team member"] == member].iterrows():
        d = pd.to_datetime(r["Date"], errors="coerce")
        if not pd.isna(d): out.add(d.date())
    return out

# ── public holiday generation (NZ) ────────────────────────────────────────────

def easter_sunday(year):
    """Anonymous Gregorian algorithm (Computus)."""
    a = year % 19; b = year // 100; c = year % 100; d = b // 4; e = b % 4
    f = (b + 8) // 25; g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30; i = c // 4; k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7; m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31; day = ((h + l - 7 * m + 114) % 31) + 1
    return pd.Timestamp(year=year, month=month, day=day)

def nth_weekday(year, month, weekday, n):
    """nth occurrence of a weekday (0=Mon) in a month."""
    d = pd.Timestamp(year=year, month=month, day=1)
    first = d + pd.Timedelta(days=(weekday - d.weekday()) % 7)
    return first + pd.Timedelta(weeks=n - 1)

# Official NZ Matariki public holiday dates (government-set)
MATARIKI_DATES = {2022: "06-24", 2023: "07-14", 2024: "06-28", 2025: "06-20",
                  2026: "07-10", 2027: "06-25", 2028: "07-14", 2029: "07-06", 2030: "06-21"}

def nz_public_holidays(year):
    """Return a list of (date_str, name) for NZ public holidays in the given year."""
    easter = easter_sunday(year)
    good_friday = easter - pd.Timedelta(days=2)
    easter_monday = easter + pd.Timedelta(days=1)
    kings_birthday = nth_weekday(year, 6, 0, 1)   # 1st Monday June
    labour_day = nth_weekday(year, 10, 0, 4)      # 4th Monday October
    hols = [
        (f"{year}-01-01", "New Year's Day"),
        (f"{year}-01-02", "Day after New Year's Day"),
        (f"{year}-02-06", "Waitangi Day"),
        (good_friday.strftime("%Y-%m-%d"), "Good Friday"),
        (easter_monday.strftime("%Y-%m-%d"), "Easter Monday"),
        (f"{year}-04-25", "ANZAC Day"),
        (kings_birthday.strftime("%Y-%m-%d"), "King's Birthday"),
        (labour_day.strftime("%Y-%m-%d"), "Labour Day"),
        (f"{year}-12-25", "Christmas Day"),
        (f"{year}-12-26", "Boxing Day"),
    ]
    if year in MATARIKI_DATES:
        hols.append((f"{year}-{MATARIKI_DATES[year]}", "Matariki"))
    return sorted(hols, key=lambda x: x[0])

# ── resourcing helpers ────────────────────────────────────────────────────────

def week_workdays(week_start, holiday_dates):
    """Count Mon–Fri days in the week that aren't public holidays."""
    count = 0
    for i in range(5):
        d = (week_start + pd.Timedelta(days=i)).date()
        if d not in holiday_dates: count += 1
    return count

def get_week_starts(offset=0, count=17, holiday_dates=None):
    """Return a list of week-info dicts, each starting on a Monday.
    Months are grouped by the Wednesday (midpoint) of the week to match Caperity."""
    holiday_dates = holiday_dates or set()
    today = pd.Timestamp.now().normalize()
    monday = today - pd.Timedelta(days=today.weekday())
    weeks = []
    for i in range(count):
        ws = monday + pd.Timedelta(weeks=(offset + i))
        wed = ws + pd.Timedelta(days=2)
        weeks.append({
            "start": ws,
            "start_str": ws.strftime("%Y-%m-%d"),
            "label": f"W{ws.isocalendar()[1]}",
            "date_label": ws.strftime("%d/%m/%Y"),
            "month": wed.strftime("%B %Y"),
            "workdays": week_workdays(ws, holiday_dates),
            "is_current": (ws == monday),
        })
    return weeks

def member_week_leave_days(member, week_start, leave_dates, holiday_dates):
    """Weekdays in the week the member is on personal leave (not already public holidays)."""
    count = 0
    for i in range(5):
        d = (week_start + pd.Timedelta(days=i)).date()
        if d in holiday_dates: continue
        if d in leave_dates: count += 1
    return count

def member_week_capacity(week, base_capacity, member_leave_dates, holiday_dates):
    """A member's capacity for a week = base × (company workdays − their leave days) / 5."""
    leave_days = member_week_leave_days(None, week["start"], member_leave_dates, holiday_dates)
    eff_workdays = max(0, week["workdays"] - leave_days)
    return base_capacity * (eff_workdays / 5.0), eff_workdays, leave_days

def avail_color(hours, capacity=40.0):
    """Traffic-light colour for remaining available hours, relative to that week's capacity."""
    if hours < 0:        return ("#c0392b", "#ffffff")   # overallocated — dark red
    if hours == 0:       return ("#f4f6f7", "#888888")   # exactly full — light grey
    pct = (hours / capacity) if capacity > 0 else 0
    if pct > 0.75:       return ("#27ae60", "#ffffff")   # plenty free — dark green
    if pct > 0.5:        return ("#52be80", "#ffffff")   # comfortable — green
    if pct > 0.25:       return ("#f39c12", "#ffffff")   # getting full — amber
    return ("#e74c3c", "#ffffff")                        # nearly full — red

def member_week_planned(member, week_str, allocs_df):
    if allocs_df.empty: return 0.0
    rows = allocs_df[(allocs_df["Team member"] == member) & (allocs_df["Week start"] == week_str)]
    return round(rows["Projected hours"].apply(parse_budget).sum(), 2)

def member_week_actual(member, week_str, timesheets_df):
    """Sum of logged timesheet hours for a member within the week beginning week_str."""
    if timesheets_df is None or timesheets_df.empty: return 0.0
    rows = timesheets_df[timesheets_df["Team member"] == member].copy()
    if rows.empty: return 0.0
    ws = pd.Timestamp(week_str); we = ws + pd.Timedelta(days=6)
    dt = pd.to_datetime(rows["Date"], errors="coerce")
    mask = ((dt >= ws) & (dt <= we)).fillna(False).astype(bool)
    sel = rows[mask]
    if sel.empty: return 0.0
    return round(sel["Hours"].apply(parse_budget).sum(), 2)

def fmt_hours(x):
    return str(int(x)) if float(x) == int(x) else str(round(float(x), 1))

def build_availability_table_html(member_names, weeks, allocs_df, leave_df, holiday_dates, capacity=40.0):
    if not member_names: return "<p style='color:#888'>No team members set up yet.</p>"
    if not weeks: return "<p style='color:#888'>No weeks to display.</p>"

    months = {}
    for w in weeks:
        months[w["month"]] = months.get(w["month"], 0) + 1

    th = "color:#fff;padding:6px 8px;text-align:center;border:1px solid #3d3d3d;white-space:nowrap;font-weight:600"
    dark = "background:#2c2c2c"
    cur = "background:#e8a87c;color:#1a1a1a"
    name_td = "padding:6px 10px;font-weight:500;color:#1a1a1a;background:#ffffff;border:1px solid #e0e0e0;white-space:nowrap;text-align:left"

    html = "<div style='overflow-x:auto;border:1px solid #d8d6d2;border-radius:6px'>"
    html += "<table style='border-collapse:collapse;font-family:Inter,sans-serif;font-size:12px;min-width:100%'>"

    # Month header row
    html += "<tr>"
    html += f"<th style='{th};{dark};min-width:140px;text-align:left'>Resource Availability</th>"
    for month, cnt in months.items():
        html += f"<th colspan='{cnt}' style='{th};{dark}'>{month}</th>"
    html += "</tr>"

    # Week label row
    html += "<tr>"
    html += f"<th style='{th};background:#3d3d3d'></th>"
    for w in weeks:
        style = cur if w["is_current"] else dark
        html += f"<th style='{th};{style};min-width:64px'>{w['label']}</th>"
    html += "</tr>"

    # Date row
    html += "<tr>"
    html += f"<th style='{th};background:#3d3d3d'></th>"
    for w in weeks:
        style = cur if w["is_current"] else dark
        html += f"<th style='{th};{style};font-weight:400;font-size:10px'>{w['date_label']}</th>"
    html += "</tr>"

    # Workdays row
    html += "<tr>"
    html += f"<td style='{name_td};color:#888;font-size:11px;background:#f4f4f4'># workdays</td>"
    for w in weeks:
        flag = "background:#fde7d7" if w["workdays"] < 5 else "background:#f4f4f4"
        html += f"<td style='padding:4px;text-align:center;border:1px solid #e0e0e0;color:#888;font-size:11px;{flag}'>{w['workdays']}</td>"
    html += "</tr>"

    # Spacer
    html += f"<tr><td colspan='{len(weeks)+1}' style='height:10px;background:#f6f5f3;border:none'></td></tr>"

    # Member rows
    for member in member_names:
        m_leave = leave_dates_for_member(member, leave_df)
        disp = member if len(member) <= 20 else member[:18] + "…"
        html += "<tr>"
        html += f"<td style='{name_td}'>{disp}</td>"
        for w in weeks:
            wcap, eff_wd, leave_days = member_week_capacity(w, capacity, m_leave, holiday_dates)
            planned = member_week_planned(member, w["start_str"], allocs_df)
            available = round(wcap - planned, 2)
            bg, fg = avail_color(available, wcap if wcap > 0 else capacity)
            border = "border:2px solid #e8a87c" if w["is_current"] else "border:1px solid #e0e0e0"
            leave_marker = "<span style='position:absolute;top:1px;right:3px;font-size:8px;opacity:0.85'>🌴</span>" if leave_days > 0 else ""
            html += f"<td style='position:relative;padding:5px 8px;text-align:center;{border};background:{bg};color:{fg};font-weight:600'>{leave_marker}{fmt_hours(available)}</td>"
        html += "</tr>"

    html += "</table></div>"
    return html

# ── mutators ──────────────────────────────────────────────────────────────────

def add_or_update_project(data, df):
    data["Last updated"] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
    existing = df[df["Project name"] == data["Project name"]]
    if not existing.empty:
        for k, v in data.items(): df.at[existing.index[0], k] = v
    else:
        data["Project ID"] = data.get("Project ID") or create_id()
        df = pd.concat([df, pd.DataFrame([data])], ignore_index=True)
    return df

def add_or_update_task(data, df):
    data["Last updated"] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
    if not data.get("Task ID"):
        data["Task ID"] = create_id()
        df = pd.concat([df, pd.DataFrame([data])], ignore_index=True)
    else:
        existing = df[df["Task ID"] == data["Task ID"]]
        if not existing.empty:
            for k, v in data.items(): df.at[existing.index[0], k] = v
        else:
            df = pd.concat([df, pd.DataFrame([data])], ignore_index=True)
    return df

def add_timesheet_entry(data, df):
    data["Entry ID"] = create_id()
    data.setdefault("Invoiced", "False")
    return pd.concat([df, pd.DataFrame([data])], ignore_index=True)

# ── invoice helpers ───────────────────────────────────────────────────────────

def invoice_total(inv_id, lines_df):
    if lines_df.empty: return 0.0
    lines = lines_df[lines_df["Invoice ID"] == inv_id]
    return round(lines["Amount"].apply(parse_budget).sum(), 2)

def client_billing_summary(company_id, invoices_df, lines_df):
    if invoices_df.empty:
        return {"total_invoiced": 0.0, "paid": 0.0, "outstanding": 0.0}
    inv = invoices_df[invoices_df["Company ID"] == company_id]
    total_invoiced = sum(invoice_total(r["Invoice ID"], lines_df) for _, r in inv.iterrows())
    paid = sum(invoice_total(r["Invoice ID"], lines_df) for _, r in inv.iterrows() if r["Status"] == "Paid")
    outstanding = total_invoiced - paid
    return {"total_invoiced": round(total_invoiced, 2), "paid": round(paid, 2), "outstanding": round(outstanding, 2)}

def generate_invoice_html(inv_row, lines_df, company_name):
    inv_id = inv_row["Invoice ID"]
    lines = lines_df[lines_df["Invoice ID"] == inv_id]
    total = invoice_total(inv_id, lines_df)
    line_rows = "".join(
        f"<tr><td style='padding:8px'>{l['Description']}</td>"
        f"<td style='text-align:center;padding:8px'>{l['Quantity']}</td>"
        f"<td style='text-align:right;padding:8px'>${parse_budget(l['Unit price']):,.2f}</td>"
        f"<td style='text-align:right;padding:8px;font-weight:600'>${parse_budget(l['Amount']):,.2f}</td></tr>"
        for _, l in lines.iterrows()
    )
    return f"""<html><head><style>
    body{{font-family:Arial,sans-serif;font-size:12px;color:#222;margin:40px}}
    h1,h2{{color:#2c3e50}} table{{border-collapse:collapse;width:100%;margin-bottom:20px}}
    td,th{{border:1px solid #ddd}} .total{{font-size:15px;font-weight:700;color:#2c3e50}}
    </style></head><body>
    <h1>INVOICE</h1>
    <table style='border:none;width:100%'><tr>
    <td style='border:none;vertical-align:top'>
      <strong>Bill to:</strong><br>{company_name}<br>
    </td>
    <td style='border:none;text-align:right;vertical-align:top'>
      <strong>Invoice #:</strong> {inv_row['Invoice number']}<br>
      <strong>Issue date:</strong> {inv_row['Issue date']}<br>
      <strong>Due date:</strong> {inv_row['Due date']}<br>
      <strong>Status:</strong> {inv_row['Status']}<br>
    </td></tr></table>
    {"<p><strong>Project:</strong> " + inv_row['Project name'] + "</p>" if inv_row.get('Project name') else ""}
    <h2>Line Items</h2>
    <table><thead><tr>
      <th style='padding:8px;background:#2c3e50;color:white;text-align:left'>Description</th>
      <th style='padding:8px;background:#2c3e50;color:white;text-align:center'>Qty</th>
      <th style='padding:8px;background:#2c3e50;color:white;text-align:right'>Unit Price</th>
      <th style='padding:8px;background:#2c3e50;color:white;text-align:right'>Amount</th>
    </tr></thead><tbody>{line_rows}</tbody></table>
    <table style='width:300px;margin-left:auto'>
      <tr class='total'><td style='padding:8px'>TOTAL</td><td style='text-align:right;padding:8px'>${total:,.2f}</td></tr>
    </table>
    {"<p><strong>Payment details:</strong><br>" + inv_row['Payment details'].replace(chr(10),'<br>') + "</p>" if inv_row.get('Payment details') else ""}
    {"<p><strong>Notes:</strong> " + inv_row['Notes'] + "</p>" if inv_row.get('Notes') else ""}
    </body></html>"""

# ── fee helpers ───────────────────────────────────────────────────────────────

def estimate_totals(est_id, lines_df, disb_df, margin_pct, role_rates):
    lines = lines_df[lines_df["Estimate ID"] == est_id]
    hours_cost = sum(parse_budget(r["Hours"]) * (parse_budget(r["Rate"]) if r["Rate"] else role_rates.get(r["Role"], 0.0)) for _, r in lines.iterrows())
    disbs = disb_df[disb_df["Estimate ID"] == est_id]
    fixed_disb = sum(parse_budget(d["Value"]) for _, d in disbs.iterrows() if d["Type"] == "Fixed ($)")
    pct_disb = sum(parse_budget(d["Value"]) for _, d in disbs.iterrows() if d["Type"] != "Fixed ($)")
    pct_disb_amt = hours_cost * (pct_disb / 100)
    total_disb = fixed_disb + pct_disb_amt
    subtotal = hours_cost + total_disb
    margin_amt = subtotal * (parse_budget(margin_pct) / 100)
    total = subtotal + margin_amt
    return {"hours_cost": round(hours_cost, 2), "fixed_disb": round(fixed_disb, 2),
            "pct_disb_amt": round(pct_disb_amt, 2), "total_disb": round(total_disb, 2),
            "subtotal": round(subtotal, 2), "margin_amt": round(margin_amt, 2), "total": round(total, 2)}

def project_fee_consumed(project_id, timesheets_df, role_rates):
    entries = timesheets_df[timesheets_df["Project ID"] == project_id]
    return round(sum(parse_budget(e["Hours"]) * (parse_budget(e["Rate"]) if e["Rate"] else role_rates.get(e["Role"], 0.0)) for _, e in entries.iterrows()), 2)

def project_hours_logged(project_id, timesheets_df):
    return round(sum(parse_budget(e["Hours"]) for _, e in timesheets_df[timesheets_df["Project ID"] == project_id].iterrows()), 1)

def generate_pdf_html(est_row, lines_df, disb_df, totals, role_rates):
    est_id = est_row["Estimate ID"]
    roles = list(DEFAULT_ROLES.keys())
    phase_rows = ""
    for phase in STAGES:
        pl = lines_df[(lines_df["Estimate ID"] == est_id) & (lines_df["Phase"] == phase)]
        if pl.empty: continue
        pt = 0.0; rc = ""
        for role in roles:
            rl = pl[pl["Role"] == role]; hrs = rl["Hours"].apply(parse_budget).sum(); cost = hrs * role_rates.get(role, 0.0); pt += cost
            rc += f"<td style='text-align:center;padding:4px 8px'>{hrs if hrs>0 else ''}</td><td style='text-align:right;padding:4px 8px'>{'${:,.0f}'.format(cost) if cost>0 else ''}</td>"
        phase_rows += f"<tr><td style='padding:4px 8px;font-weight:600'>{phase}</td>{rc}<td style='text-align:right;padding:4px 8px;font-weight:700'>${pt:,.2f}</td></tr>"
    rh = "".join(f"<th colspan='2' style='padding:6px 8px;background:#2c3e50;color:white'>{r}</th>" for r in roles)
    disbs = disb_df[disb_df["Estimate ID"] == est_id]
    dr = "".join(f"<tr><td style='padding:4px 8px'>{d['Description']}</td><td>{d['Type']}</td><td style='text-align:right;padding:4px 8px'>{'${:,.2f}'.format(parse_budget(d['Value'])) if d['Type']=='Fixed ($)' else d['Value']+'%'}</td></tr>" for _, d in disbs.iterrows())
    mp = parse_budget(est_row.get("Margin %", "0"))
    return f"""<html><head><style>body{{font-family:Arial,sans-serif;font-size:12px;color:#222;margin:40px}}h1,h2{{color:#2c3e50}}h2{{border-bottom:1px solid #ccc;padding-bottom:4px}}table{{border-collapse:collapse;width:100%;margin-bottom:20px}}td,th{{border:1px solid #ddd}}.summary td{{padding:6px 12px}}.total{{font-size:16px;font-weight:700;color:#2c3e50}}</style></head><body>
    <h1>Fee Estimate — {est_row['Estimate name']}</h1><p><strong>Client:</strong> {est_row['Client']} &nbsp;|&nbsp; <strong>Project:</strong> {est_row.get('Project name','—')} &nbsp;|&nbsp; <strong>Date:</strong> {est_row.get('Created','')}</p>
    <h2>Phase & Role Breakdown</h2><table><thead><tr><th style='padding:6px 8px;background:#2c3e50;color:white'>Phase</th>{rh}<th style='padding:6px 8px;background:#2c3e50;color:white'>Phase Total</th></tr>
    <tr style='background:#ecf0f1'><td></td>{"".join(f"<td style='text-align:center;font-size:10px;padding:4px'>Hrs</td><td style='text-align:center;font-size:10px;padding:4px'>Cost</td>" for _ in roles)}<td></td></tr></thead><tbody>{phase_rows}</tbody></table>
    <h2>Disbursements</h2><table><thead><tr><th style='padding:6px 8px;background:#2c3e50;color:white'>Description</th><th style='padding:6px 8px;background:#2c3e50;color:white'>Type</th><th style='padding:6px 8px;background:#2c3e50;color:white'>Value</th></tr></thead><tbody>{dr or "<tr><td colspan='3' style='padding:6px 8px;color:#888'>No disbursements</td></tr>"}</tbody></table>
    <h2>Summary</h2><table class='summary' style='width:350px'><tr><td>Hours subtotal</td><td style='text-align:right'>${totals['hours_cost']:,.2f}</td></tr><tr><td>Fixed disbursements</td><td style='text-align:right'>${totals['fixed_disb']:,.2f}</td></tr><tr><td>% disbursements</td><td style='text-align:right'>${totals['pct_disb_amt']:,.2f}</td></tr><tr><td>Subtotal</td><td style='text-align:right'>${totals['subtotal']:,.2f}</td></tr><tr><td>Margin ({mp:.1f}%)</td><td style='text-align:right'>${totals['margin_amt']:,.2f}</td></tr><tr class='total'><td>TOTAL FEE</td><td style='text-align:right'>${totals['total']:,.2f}</td></tr></table></body></html>"""

# ── workload ──────────────────────────────────────────────────────────────────

def compute_team_member_hours(df, members_df, weekly_capacity=40.0):
    workload = {m: {"Assigned hours": 0.0, "Projects assigned": 0} for m in members_df["Team member"].tolist()}
    for _, row in df.iterrows():
        members = parse_team_members(row.get("Team members", ""))
        member_hours = parse_member_hours(row.get("Member hours allocation", ""))
        if member_hours:
            for m, h in member_hours.items():
                if m not in workload: workload[m] = {"Assigned hours": 0.0, "Projects assigned": 0}
                workload[m]["Assigned hours"] += h; workload[m]["Projects assigned"] += 1
            continue
        wh = parse_weekly_hours(row.get("Weekly hours allocated", ""))
        if wh <= 0 or not members: continue
        share = wh / len(members)
        for m in members:
            if m not in workload: workload[m] = {"Assigned hours": 0.0, "Projects assigned": 0}
            workload[m]["Assigned hours"] += share; workload[m]["Projects assigned"] += 1
    records = []
    for m, data in workload.items():
        assigned = round(data["Assigned hours"], 1); available = round(max(0.0, weekly_capacity - assigned), 1)
        records.append({"Team member": m, "Projects assigned": data["Projects assigned"], "Assigned hours": assigned, "Available hours": available,
                        "Status": "Swamped" if available < 10 else ("Getting full" if available < 20 else "OK")})
    return pd.DataFrame(records).sort_values(["Assigned hours", "Team member"], ascending=[False, True])

def style_workload_table(row):
    a = row["Available hours"]; c = "#ff9999" if a < 10 else ("#ffcc99" if a < 20 else "#d4f4d4")
    return [f"background-color: {c}"] * len(row)

# ── custom field UI ───────────────────────────────────────────────────────────

def render_custom_fields_editor(existing_fields, key_prefix):
    st.markdown("**Custom fields**")
    updated = []
    for i, cf in enumerate(existing_fields):
        c1, c2, c3, c4 = st.columns([2, 2, 3, 1])
        label = c1.text_input("Label", value=cf.get("label", ""), key=f"{key_prefix}_cf_label_{i}", label_visibility="collapsed", placeholder="Label")
        ftype = c2.selectbox("Type", ["Text", "Dropdown"], index=0 if cf.get("type", "Text") == "Text" else 1, key=f"{key_prefix}_cf_type_{i}", label_visibility="collapsed")
        if ftype == "Text":
            val = c3.text_input("Value", value=cf.get("value", ""), key=f"{key_prefix}_cf_val_{i}", label_visibility="collapsed", placeholder="Value")
            opts = cf.get("options", [])
        else:
            opts_str = c3.text_input("Options (comma separated)", value=", ".join(cf.get("options", [])), key=f"{key_prefix}_cf_opts_{i}", label_visibility="collapsed", placeholder="Option 1, Option 2")
            opts = [o.strip() for o in opts_str.split(",") if o.strip()]
            val = cf.get("value", opts[0] if opts else "")
        remove = c4.checkbox("✕", key=f"{key_prefix}_cf_remove_{i}")
        if not remove: updated.append({"label": label, "type": ftype, "value": val, "options": opts})
    if st.button("＋ Add custom field", key=f"{key_prefix}_add_cf"):
        updated.append({"label": "", "type": "Text", "value": "", "options": []}); st.rerun()
    return updated

# ── dialogs ───────────────────────────────────────────────────────────────────

@st.dialog("Project Tasks", width="large")
def show_task_popup(proj_name):
    st.subheader(proj_name)
    proj_tasks = st.session_state.tasks[st.session_state.tasks["Project name"] == proj_name].copy()
    for status in TASK_STATUSES:
        status_tasks = proj_tasks[proj_tasks["Status"] == status]; colour = TASK_STATUS_COLOURS[status]
        st.markdown(f"<div style='font-weight:700;font-size:14px;color:{colour};border-bottom:2px solid {colour};padding-bottom:4px;margin:12px 0 8px'>{status} ({len(status_tasks)})</div>", unsafe_allow_html=True)
        if status_tasks.empty: st.caption("No tasks.")
        for _, task in status_tasks.iterrows():
            tid = task["Task ID"]
            c1, c2, c3 = st.columns([3, 2, 2])
            with c1:
                st.markdown(f"**{task['Task name']}**")
                if task.get("Notes"): st.caption(task["Notes"])
            with c2:
                assigned = [m.strip() for m in str(task["Assigned to"]).split(";") if m.strip()]
                new_assigned = st.multiselect("Assignee", st.session_state.members_df["Team member"].tolist(), default=assigned, key=f"popup_assign_{tid}", label_visibility="collapsed")
            with c3:
                new_status = st.selectbox("Status", TASK_STATUSES, index=TASK_STATUSES.index(task["Status"]) if task["Status"] in TASK_STATUSES else 0, key=f"popup_status_{tid}", label_visibility="collapsed")
            if new_assigned != assigned or new_status != task["Status"]:
                idx = st.session_state.tasks[st.session_state.tasks["Task ID"] == tid].index[0]
                st.session_state.tasks.at[idx, "Assigned to"] = "; ".join(new_assigned)
                st.session_state.tasks.at[idx, "Status"] = new_status
                st.session_state.tasks.at[idx, "Last updated"] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
                save_tasks(st.session_state.tasks)
            st.divider()
    st.markdown("### ＋ Add a task")
    with st.form(key=f"popup_new_task_{proj_name}"):
        nt_name = st.text_input("Task name"); nt_team = st.selectbox("Team", TASK_TEAMS)
        nt_assigned = st.multiselect("Assigned to", st.session_state.members_df["Team member"].tolist())
        nt_status = st.selectbox("Status", TASK_STATUSES); nt_notes = st.text_area("Notes", height=80)
        if st.form_submit_button("Create task", use_container_width=True):
            if not nt_name: st.warning("Please enter a task name.")
            else:
                proj_row = st.session_state.projects[st.session_state.projects["Project name"] == proj_name]
                pid = proj_row.iloc[0]["Project ID"] if not proj_row.empty else ""
                st.session_state.tasks = add_or_update_task({"Task ID": "", "Project ID": pid, "Project name": proj_name, "Task name": nt_name, "Team": nt_team, "Assigned to": "; ".join(nt_assigned), "Status": nt_status, "Notes": nt_notes}, st.session_state.tasks)
                save_tasks(st.session_state.tasks); st.rerun()


@st.dialog("Log Hours", width="large")
def show_log_hours_popup(proj_name, proj_id):
    st.subheader(f"Log hours — {proj_name}")
    role_rates = get_role_rates(st.session_state.roles_df)
    member_names = st.session_state.members_df["Team member"].tolist()
    with st.form("log_hours_form"):
        c1, c2 = st.columns(2)
        with c1:
            lh_member = st.selectbox("Team member", [""] + member_names)
            lh_phase = st.selectbox("Phase", [""] + STAGES)
            lh_date = st.date_input("Date", value=pd.Timestamp.now().date())
        with c2:
            member_row = st.session_state.members_df[st.session_state.members_df["Team member"] == lh_member]
            member_role = member_row.iloc[0]["Role"] if not member_row.empty else ""
            lh_role = st.selectbox("Role", list(DEFAULT_ROLES.keys()), index=list(DEFAULT_ROLES.keys()).index(member_role) if member_role in DEFAULT_ROLES else 0)
            lh_rate = st.number_input("Hourly rate ($)", min_value=0.0, value=role_rates.get(lh_role, 0.0), step=5.0)
            lh_hours = st.number_input("Hours", min_value=0.0, step=0.5, value=0.0)
        lh_notes = st.text_area("Notes", height=80)
        if st.form_submit_button("Save entry", use_container_width=True):
            if not lh_member or lh_hours <= 0: st.warning("Please select a team member and enter hours.")
            else:
                st.session_state.timesheets = add_timesheet_entry({"Project ID": proj_id, "Project name": proj_name, "Phase": lh_phase, "Team member": lh_member, "Role": lh_role, "Date": str(lh_date), "Hours": str(lh_hours), "Rate": str(lh_rate), "Notes": lh_notes, "Invoiced": "False"}, st.session_state.timesheets)
                save_timesheets(st.session_state.timesheets); st.success("Hours logged!"); st.rerun()
    proj_entries = st.session_state.timesheets[st.session_state.timesheets["Project ID"] == proj_id].copy()
    if not proj_entries.empty:
        st.markdown("---")
        proj_entries["Cost"] = proj_entries.apply(lambda r: round(parse_budget(r["Hours"]) * parse_budget(r["Rate"]), 2), axis=1)
        st.markdown(f"**Total: {proj_entries['Hours'].apply(parse_budget).sum():.1f} hrs &nbsp;|&nbsp; ${proj_entries['Cost'].sum():,.2f}**")
        if "expanded_ts_entry" not in st.session_state: st.session_state.expanded_ts_entry = None
        for _, e in proj_entries.sort_values("Date", ascending=False).iterrows():
            eid = e["Entry ID"]; is_exp = st.session_state.expanded_ts_entry == eid
            invoiced_badge = " 🧾" if e.get("Invoiced") == "True" else ""
            c1, c2, c3, c4, c5 = st.columns([2, 1, 1, 1, 1])
            c1.markdown(f"**{e['Team member']}** — {e['Phase'] or 'No phase'}{invoiced_badge}"); c1.caption(e["Notes"] or "")
            c2.markdown(f"{e['Date']}"); c3.markdown(f"{e['Hours']} hrs @ ${e['Rate']}/hr"); c4.markdown(f"**${e['Cost']:,.2f}**")
            if c5.button("✏️" if not is_exp else "▲", key=f"edit_ts_{eid}"): st.session_state.expanded_ts_entry = None if is_exp else eid; st.rerun()
            if c5.button("🗑", key=f"del_ts_{eid}"):
                st.session_state.timesheets = st.session_state.timesheets[st.session_state.timesheets["Entry ID"] != eid]
                save_timesheets(st.session_state.timesheets); st.rerun()
            if is_exp:
                with st.form(key=f"edit_ts_form_{eid}"):
                    ec1, ec2 = st.columns(2)
                    with ec1:
                        e_member = st.selectbox("Team member", [""] + member_names, index=([""] + member_names).index(e["Team member"]) if e["Team member"] in member_names else 0)
                        e_phase = st.selectbox("Phase", [""] + STAGES, index=([""] + STAGES).index(e["Phase"]) if e["Phase"] in STAGES else 0)
                        e_date = st.date_input("Date", value=parse_date(e["Date"], pd.Timestamp.now().date()))
                    with ec2:
                        e_role = st.selectbox("Role", list(DEFAULT_ROLES.keys()), index=list(DEFAULT_ROLES.keys()).index(e["Role"]) if e["Role"] in DEFAULT_ROLES else 0)
                        e_rate = st.number_input("Rate ($/hr)", min_value=0.0, step=5.0, value=parse_budget(e["Rate"]))
                        e_hours = st.number_input("Hours", min_value=0.0, step=0.5, value=parse_budget(e["Hours"]))
                    e_notes = st.text_area("Notes", value=e["Notes"], height=60)
                    if st.form_submit_button("Save changes", use_container_width=True):
                        idx = st.session_state.timesheets[st.session_state.timesheets["Entry ID"] == eid].index[0]
                        for k, v in [("Team member", e_member), ("Phase", e_phase), ("Role", e_role), ("Date", str(e_date)), ("Hours", str(e_hours)), ("Rate", str(e_rate)), ("Notes", e_notes)]:
                            st.session_state.timesheets.at[idx, k] = v
                        save_timesheets(st.session_state.timesheets); st.session_state.expanded_ts_entry = None; st.rerun()
            st.divider()

# ── Gantt chart ───────────────────────────────────────────────────────────────

def build_gantt_chart(df):
    if df.empty:
        st.info("No projects to display.")
        return

    STATUS_COLOURS = {
        "On track": "#2ecc71", "At risk": "#f39c12",
        "Delayed": "#e74c3c", "Complete": "#95a5a6"
    }
    today = pd.Timestamp.now().normalize()

    rows = []
    for _, proj in df.iterrows():
        phases = parse_phase_schedule(proj.get("Phase schedule", ""))
        if not phases: continue
        status = proj.get("Status", "On track")
        colour = STATUS_COLOURS.get(status, "#3498db")
        for p in phases:
            rows.append({
                "Project": proj["Project name"], "Phase": p["Stage"],
                "Start": p["Start date"], "End": p["Target completion"],
                "Status": status, "Colour": colour,
                "Label": f"{proj['Project name']} — {p['Stage']}",
            })

    if not rows:
        st.info("No phase schedules found. Add phase schedules to your projects to see the Gantt chart.")
        return

    gantt = pd.DataFrame(rows)
    gantt["Start"] = pd.to_datetime(gantt["Start"])
    gantt["End"] = pd.to_datetime(gantt["End"])
    gantt["Phase order"] = gantt["Phase"].apply(lambda x: STAGES.index(x) if x in STAGES else 99)
    gantt = gantt.sort_values(["Project", "Phase order"]).reset_index(drop=True)

    y_labels = []
    prev_proj = None
    display_rows = []
    for _, row in gantt.iterrows():
        if row["Project"] != prev_proj:
            header = f"▸ {row['Project']}"
            y_labels.append(header)
            prev_proj = row["Project"]
        phase_label = f"{row['Project']} | {row['Phase']}"
        y_labels.append(phase_label)
        display_rows.append({**row.to_dict(), "y_label": phase_label, "y_display": f"   {row['Phase']}"})

    disp_df = pd.DataFrame(display_rows)

    bars = alt.Chart(disp_df).mark_bar(height=16, cornerRadius=4).encode(
        x=alt.X("Start:T", title="", axis=alt.Axis(format="%b %Y", tickCount="month", grid=True, gridColor="#f0f0f0", labelFontSize=11)),
        x2=alt.X2("End:T"),
        y=alt.Y("y_label:N", sort=y_labels, title="",
                axis=alt.Axis(labelFontSize=12, labelLimit=220, ticks=False, domain=False)),
        color=alt.Color("Status:N",
            scale=alt.Scale(domain=list(STATUS_COLOURS.keys()), range=list(STATUS_COLOURS.values())),
            legend=alt.Legend(title="Status", orient="top", titleFontSize=11, labelFontSize=11)),
        tooltip=[
            alt.Tooltip("Project:N", title="Project"), alt.Tooltip("Phase:N", title="Phase"),
            alt.Tooltip("Start:T", title="Start", format="%d %b %Y"),
            alt.Tooltip("End:T", title="End", format="%d %b %Y"),
            alt.Tooltip("Status:N", title="Status"),
        ]
    )

    bar_labels = alt.Chart(disp_df).mark_text(align="left", dx=4, fontSize=10, color="#fff", fontWeight="bold").encode(
        x=alt.X("Start:T"), y=alt.Y("y_label:N", sort=y_labels), text=alt.Text("Phase:N"),
    )

    today_df = pd.DataFrame({"today": [today]})
    today_line = alt.Chart(today_df).mark_rule(color="#e74c3c", strokeWidth=2, strokeDash=[4, 3]).encode(x=alt.X("today:T"))
    today_label = alt.Chart(today_df).mark_text(text="Today", color="#e74c3c", fontSize=11, fontWeight="bold", align="center", dy=-6).encode(x=alt.X("today:T"), y=alt.value(0))

    header_rows = [r for r in y_labels if r.startswith("▸")]
    if header_rows:
        hdr_df = pd.DataFrame({"y_label": header_rows})
        header_bands = alt.Chart(hdr_df).mark_rect(color="#ece9e4", height=28).encode(y=alt.Y("y_label:N", sort=y_labels))
        header_text = alt.Chart(hdr_df).mark_text(align="left", dx=-220, fontSize=12, fontWeight="bold", color="#2c3e50").encode(
            y=alt.Y("y_label:N", sort=y_labels), text=alt.Text("y_label:N"))
        chart = alt.layer(header_bands, bars, bar_labels, today_line, today_label, header_text)
    else:
        chart = alt.layer(bars, bar_labels, today_line, today_label)

    n_rows = len(y_labels)
    chart_height = max(500, n_rows * 32 + 120)
    chart = chart.properties(width="container", height=chart_height, background="transparent").configure_view(
        strokeWidth=0, fill="transparent").configure_axis(
        labelColor="#2c2c2c", titleColor="#2c2c2c", domainColor="#c9c6c1", gridColor="#e3e1dd", tickColor="#c9c6c1"
    ).configure_legend(labelColor="#2c2c2c", titleColor="#1a1a1a").configure_title(color="#1a1a1a")

    st.altair_chart(chart, use_container_width=True)


# ── traffic light cards ───────────────────────────────────────────────────────

def build_traffic_light_cards(df):
    today = pd.Timestamp.now().normalize()
    role_rates = get_role_rates(st.session_state.roles_df)
    STATUS_COLOURS = {"On track": "#2ecc71", "At risk": "#f39c12", "Delayed": "#e74c3c", "Complete": "#aaaaaa"}
    def phase_colour(d):
        if d is None or d < 0: return "#aaaaaa"
        if d < 14: return "#e74c3c"
        if d <= 30: return "#f39c12"
        return "#2ecc71"
    def days_label(d):
        if d is None: return "Not set"
        if d < 0: return "Passed"
        if d == 0: return "Today"
        return f"In {d}d"
    cards = []
    for _, row in df.iterrows():
        phases = parse_phase_schedule(row.get("Phase schedule", ""))
        phase_map = {p["Stage"]: p["Start date"] for p in phases}
        phase_info, min_upcoming = [], None
        for stage in STAGES:
            start = phase_map.get(stage)
            days = int((pd.Timestamp(start).normalize() - today).days) if start is not None else None
            phase_info.append({"stage": stage, "days": days})
            if days is not None and days >= 0 and (min_upcoming is None or days < min_upcoming): min_upcoming = days
        proj_id = row.get("Project ID", "")
        fee = parse_budget(row.get("Fee", row.get("Budget", "0")))
        consumed = project_fee_consumed(proj_id, st.session_state.timesheets, role_rates)
        hours = project_hours_logged(proj_id, st.session_state.timesheets)
        pct = round((consumed / fee) * 100, 1) if fee > 0 else 0
        cards.append({"Project name": row["Project name"], "Project ID": proj_id, "Client": row["Client"], "Stage": row["Stage"], "Status": row["Status"], "phase_info": phase_info, "min_upcoming": min_upcoming if min_upcoming is not None else 9999, "fee": fee, "consumed": consumed, "hours": hours, "pct": pct})
    cards.sort(key=lambda c: c["min_upcoming"])
    if not cards: st.info("No projects to display."); return
    cols = st.columns(3)
    for i, card in enumerate(cards):
        proj, proj_id = card["Project name"], card["Project ID"]
        sc = STATUS_COLOURS.get(card["Status"], "#cccccc"); pct = card["pct"]
        fc = "#2ecc71" if pct < 75 else ("#f39c12" if pct <= 90 else "#e74c3c")
        dots = "".join(
            f"<div style='display:flex;flex-direction:column;align-items:center;gap:2px;min-width:60px'>"
            f"<div style='width:18px;height:18px;border-radius:50%;background:{phase_colour(p['days'])};border:{'2px solid #333' if p['stage']==card['Stage'] else '2px solid transparent'}'></div>"
            f"<span style='font-size:9px;color:#555;text-align:center'>{p['stage'][:6]}</span>"
            f"<span style='font-size:9px;color:#333;font-weight:500'>{days_label(p['days'])}</span></div>"
            for p in card["phase_info"])
        fee_bar = (f"<div style='margin-top:10px'><div style='font-size:11px;color:#555;margin-bottom:3px'>Fee: ${card['consumed']:,.0f} of ${card['fee']:,.0f} used ({pct}%) &nbsp;·&nbsp; {card['hours']} hrs logged</div>"
                   f"<div style='background:#e0e0e0;border-radius:6px;height:8px;overflow:hidden'><div style='width:{min(pct,100)}%;height:100%;background:{fc};border-radius:6px'></div></div></div>") if card["fee"] > 0 else ""
        html = (f"<div style='border:1px solid #e3e1dd;border-radius:6px;padding:14px 16px;margin-bottom:6px;background:#ffffff;border-left:4px solid {sc};box-shadow:0 1px 3px rgba(0,0,0,0.04)'>"
                f"<div style='font-weight:700;font-size:15px;margin-bottom:2px;color:#1a1a1a'>{proj}</div>"
                f"<div style='font-size:12px;color:#6b6b6b;margin-bottom:8px'>{card['Client']} &nbsp;&middot;&nbsp;<span style='color:{sc};font-weight:600'>{card['Status']}</span></div>"
                f"<div style='font-size:11px;color:#888;margin-bottom:10px'>Current stage: <strong style='color:#2c2c2c'>{card['Stage']}</strong></div>"
                f"<div style='display:flex;flex-wrap:wrap;gap:8px'>{dots}</div>{fee_bar}</div>")
        with cols[i % 3]:
            st.markdown(html, unsafe_allow_html=True)
            b1, b2, b3 = st.columns(3)
            with b1:
                if st.button("▲ Close" if st.session_state.expanded_card == proj else "✏️ Stage", key=f"toggle_{proj}", use_container_width=True):
                    st.session_state.expanded_card = None if st.session_state.expanded_card == proj else proj; st.rerun()
            with b2:
                if st.button("📋 Tasks", key=f"tasks_{proj}", use_container_width=True): show_task_popup(proj)
            with b3:
                if st.button("⏱ Hours", key=f"hours_{proj}", use_container_width=True): show_log_hours_popup(proj, proj_id)
            if st.session_state.expanded_card == proj:
                pidx = st.session_state.projects[st.session_state.projects["Project name"] == proj].index[0]
                cur = st.session_state.projects.loc[pidx].to_dict()
                with st.form(key=f"stage_form_{proj}"):
                    ns = st.selectbox("Stage", STAGES, index=STAGES.index(cur.get("Stage")) if cur.get("Stage") in STAGES else 0)
                    nst = st.selectbox("Status", STATUSES, index=STATUSES.index(cur.get("Status")) if cur.get("Status") in STATUSES else 0)
                    if st.form_submit_button("Save", use_container_width=True):
                        st.session_state.projects.at[pidx, "Stage"] = ns; st.session_state.projects.at[pidx, "Status"] = nst
                        st.session_state.projects.at[pidx, "Last updated"] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
                        save_projects(st.session_state.projects); st.session_state.expanded_card = None; st.session_state.message = f"Updated stage for '{proj}'."; st.rerun()

def filter_projects(df, stage_filter, status_filter, search_text):
    f = df.copy()
    if stage_filter: f = f[f["Stage"].isin(stage_filter)]
    if status_filter: f = f[f["Status"].isin(status_filter)]
    if search_text:
        s = search_text.lower()
        f = f[f["Project name"].str.lower().str.contains(s, na=False) | f["Client"].str.lower().str.contains(s, na=False) | f["Location"].str.lower().str.contains(s, na=False)]
    return f

# ── app setup ─────────────────────────────────────────────────────────────────

st.set_page_config(page_title=PAGE_TITLE, layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
html, body, [class*="css"], .stApp, .stMarkdown, p, div, span, label, input, select, textarea, button {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
}
[data-testid="stIconMaterial"], span[class*="material-icons"], .material-icons, .material-icons-outlined,
.material-symbols-outlined, [data-testid="stSidebarCollapseButton"] *, [data-testid="baseButton-headerNoPadding"] * {
    font-family: 'Material Symbols Outlined', 'Material Icons' !important;
}
.stApp { background-color: #f6f5f3; }
h1 { color: #1a1a1a !important; font-weight: 800 !important; letter-spacing: -0.02em !important; }
h2, h3 { color: #1a1a1a !important; font-weight: 700 !important; letter-spacing: -0.01em !important; }
h4, h5, h6 { color: #2c2c2c !important; font-weight: 600 !important; }
.stApp [data-testid="stSubheader"], .stApp h3 { border-bottom: 2px solid #1a1a1a; padding-bottom: 6px; display: inline-block; }
[data-testid="stSidebar"] { background-color: #1a1a1a; position: sticky !important; top: 0; height: 100vh; overflow-y: auto; }
[data-testid="stSidebar"] * { color: #f0f0f0 !important; }
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 { color: #F2C94C !important; border-bottom: 2px solid #F2C94C; padding-bottom: 4px; font-weight: 700 !important; }
[data-testid="stSidebar"] [data-testid="stMetricValue"] { color: #F2C94C !important; font-weight: 700 !important; }
[data-testid="stSidebar"] [data-testid="stMetricLabel"] { color: #b0b0b0 !important; }
[data-testid="stSidebar"] [data-testid="stMetricLabel"] * { color: #b0b0b0 !important; }
[data-testid="stSidebar"] label, [data-testid="stSidebar"] .stSelectbox label,
[data-testid="stSidebar"] .stMultiSelect label, [data-testid="stSidebar"] .stTextInput label { color: #e8e8e8 !important; font-weight: 500 !important; }
[data-testid="stSidebar"] .stSelectbox div[data-baseweb="select"] > div,
[data-testid="stSidebar"] .stMultiSelect div[data-baseweb="select"] > div,
[data-testid="stSidebar"] .stTextInput input, [data-testid="stSidebar"] .stNumberInput input { background-color: #2c2c2c !important; color: #f5f5f5 !important; border: 1px solid #3d3d3d !important; }
[data-testid="stSidebar"] .stSelectbox div[data-baseweb="select"] svg,
[data-testid="stSidebar"] .stMultiSelect div[data-baseweb="select"] svg { fill: #F2C94C !important; }
[data-testid="stSidebar"] span[data-baseweb="tag"] { background-color: #F2C94C !important; color: #1a1a1a !important; }
[data-testid="stSidebar"] span[data-baseweb="tag"] * { color: #1a1a1a !important; }
[data-testid="stSidebar"] .stMarkdown p, [data-testid="stSidebar"] .stMarkdown li { color: #d8d8d8 !important; }
[data-testid="stSidebar"] .stButton > button { background-color: #ffffff !important; color: #1a1a1a !important; border: none !important; border-radius: 4px !important; font-weight: 600 !important; transition: all 0.15s ease !important; }
[data-testid="stSidebar"] .stButton > button:hover { background-color: #F2C94C !important; color: #1a1a1a !important; }
[data-testid="stSidebar"] hr { border-color: #3d3d3d !important; }
[data-testid="stSidebarCollapseButton"], [data-testid="collapsedControl"],
[data-testid="stSidebarCollapsedControl"], button[kind="headerNoPadding"] { display: none !important; }
.stButton > button { border-radius: 4px !important; font-weight: 600 !important; letter-spacing: 0.01em !important; border: 1px solid #1a1a1a !important; transition: all 0.15s ease !important; }
.stButton > button:hover { background-color: #1a1a1a !important; color: #F2C94C !important; border-color: #1a1a1a !important; }
.stTabs [data-baseweb="tab-list"] { gap: 8px; border-bottom: 1px solid #d8d6d2; }
.stTabs [data-baseweb="tab"] { font-weight: 600 !important; color: #6b6b6b !important; letter-spacing: 0.01em; }
.stTabs [aria-selected="true"] { color: #1a1a1a !important; border-bottom-color: #1a1a1a !important; }
[data-testid="stMetricValue"] { color: #1a1a1a !important; font-weight: 700 !important; }
[data-testid="stDataFrame"] { border-radius: 6px; overflow: hidden; border: 1px solid #e3e1dd; }
[data-testid="stDataFrame"] [role="columnheader"] { background-color: #1a1a1a !important; color: #ffffff !important; font-weight: 600 !important; }
[data-testid="stDataFrame"] [role="gridcell"] { background-color: #ffffff !important; color: #2c2c2c !important; }
.stDownloadButton > button { border-radius: 4px !important; border: 1px solid #1a1a1a !important; font-weight: 600 !important; }
hr { border-color: #d8d6d2 !important; }
.stTextInput input, .stNumberInput input, .stDateInput input,
.stSelectbox div[data-baseweb="select"] > div, .stMultiSelect div[data-baseweb="select"] > div,
.stTextArea textarea { border-radius: 4px !important; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div style='display:flex;align-items:center;gap:16px;padding:8px 0 4px'>
    <div style='font-size:30px;font-weight:800;letter-spacing:0.18em;color:#1a1a1a'>STACK</div>
    <div style='width:4px;height:30px;background:#F2C94C'></div>
    <div style='font-size:15px;font-weight:400;letter-spacing:0.04em;color:#6b6b6b;padding-top:3px'>PROJECT CLOUD</div>
</div>
""", unsafe_allow_html=True)
st.markdown("<div style='color:#6b6b6b;font-size:14px;margin-bottom:8px'>Designing Workplace Brilliance — from concept through to code compliance.</div>", unsafe_allow_html=True)

# ── session state ─────────────────────────────────────────────────────────────

for key, loader in [("projects", load_projects), ("members_df", load_team_members), ("roles_df", load_roles),
                    ("tasks", load_tasks), ("timesheets", load_timesheets), ("estimates", load_estimates),
                    ("estimate_lines", load_estimate_lines), ("estimate_disb", load_estimate_disb),
                    ("companies", load_companies), ("contacts", load_contacts),
                    ("resource_allocs", load_resource_allocs), ("holidays", load_holidays),
                    ("leave", load_leave)]:
    if key not in st.session_state: st.session_state[key] = loader()

# Invoices — not yet persisted to disk; initialise as empty DataFrames
if "invoices" not in st.session_state:
    st.session_state.invoices = pd.DataFrame(columns=INVOICE_COLUMNS)
if "invoice_lines" not in st.session_state:
    st.session_state.invoice_lines = pd.DataFrame(columns=INVOICE_LINE_COLUMNS)

for key, default in [("message", ""), ("expanded_card", None), ("show_add_project", False),
                     ("show_team_management", False), ("selected_project", ""), ("selectbox_key", 0),
                     ("expanded_task", None), ("expanded_ts_entry", None), ("expanded_member", None),
                     ("active_estimate_id", None), ("active_company_id", None), ("active_contact_id", None),
                     ("client_tab", "Companies"), ("current_page", "Project Tracker"),
                     ("wt_unlock_member", None), ("wt_unlock_week", None), ("wt_show_unlock", False),
                     ("res_week_offset", 0), ("res_plan_offset", 0), ("res_capacity", 40.0)]:
    if key not in st.session_state: st.session_state[key] = default

member_names = st.session_state.members_df["Team member"].tolist()
role_rates = get_role_rates(st.session_state.roles_df)
company_names = st.session_state.companies["Name"].dropna().tolist()

# ── sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown(
        "<div style='text-align:center;padding:0 0 18px;margin:-8px -8px 8px'>"
        "<img src='https://www.stack.co.nz/assets/Uploads/Logo/logo.png' "
        "style='width:100%;display:block;filter:brightness(0) invert(1)' alt='STACK Interiors'/>"
        "</div>",
        unsafe_allow_html=True
    )
    page_index = PAGES.index(st.session_state.current_page) if st.session_state.current_page in PAGES else 0
    page = st.selectbox("Page", PAGES, index=page_index, key="page_selector")
    if page != st.session_state.current_page:
        st.session_state.current_page = page; st.rerun()

    if page == "Project Tracker":
        st.header("Filters")
        selected_stages = [s for s in st.multiselect("Stage", ["All"] + STAGES, default=["All"]) if s != "All"]
        selected_status = [s for s in st.multiselect("Status", ["All"] + STATUSES, default=["All"]) if s != "All"]
        search_query = st.text_input("Search")
        st.markdown("---"); st.write("**Insights**"); n = len(st.session_state.projects)
        st.metric("Total projects", n)
        st.metric("Total budget", format_budget(st.session_state.projects["Budget"].apply(parse_budget).sum()))
        st.metric("Avg compliance", f"{int(st.session_state.projects['Compliance checklist'].apply(compliance_progress).mean() if n else 0)}%")
        for s in STATUSES: st.write(f"- {s}: {st.session_state.projects['Status'].value_counts().to_dict().get(s, 0)}")
    elif page == "Task Tracker":
        st.header("Task filters")
        selected_task_project = st.selectbox("Project", ["All projects"] + st.session_state.projects["Project name"].dropna().unique().tolist(), key="task_project_select")
        task_team_filter = st.multiselect("Team", TASK_TEAMS, default=TASK_TEAMS, key="task_team_filter")
        task_status_filter = st.multiselect("Status", TASK_STATUSES, default=TASK_STATUSES, key="task_status_filter")
        st.markdown("---"); st.metric("Total tasks", len(st.session_state.tasks))
        for s in TASK_STATUSES: st.write(f"- {s}: {st.session_state.tasks['Status'].value_counts().to_dict().get(s, 0)}")
    elif page == "Timesheets":
        st.header("Timesheets")
        _wt_sel = st.session_state.get("wt_member_main", None)
        _ts_all = st.session_state.timesheets
        _ts_sidebar = _ts_all[_ts_all["Team member"] == _wt_sel] if _wt_sel and _wt_sel in member_names else _ts_all
        _label = _wt_sel if (_wt_sel and _wt_sel in member_names) else "All members"
        st.caption(f"Showing: **{_label}**")
        total_h = _ts_sidebar["Hours"].apply(parse_budget).sum()
        total_c = sum(parse_budget(r["Hours"]) * (parse_budget(r["Rate"]) if r["Rate"] else role_rates.get(r["Role"], 0)) for _, r in _ts_sidebar.iterrows())
        st.metric("Total hours logged", f"{total_h:.1f}")
        st.metric("Total cost", f"${total_c:,.2f}")
        st.metric("Entries", len(_ts_sidebar))
        st.markdown("---")
        if _wt_sel and _wt_sel in member_names:
            st.markdown("**By project**")
            proj_hrs = _ts_sidebar.groupby("Project name").apply(lambda g: round(g["Hours"].apply(parse_budget).sum(), 1)).sort_values(ascending=False)
            for pname, hrs in proj_hrs.items():
                if hrs > 0: st.write(f"- {pname}: **{hrs}h**")
    elif page == "Fee Estimator":
        st.header("Estimates")
        if not st.session_state.estimates.empty:
            for _, e in st.session_state.estimates.iterrows():
                t = estimate_totals(e["Estimate ID"], st.session_state.estimate_lines, st.session_state.estimate_disb, e.get("Margin %", "0"), role_rates)
                if st.button(f"{e['Estimate name']}\n${t['total']:,.0f}", key=f"sidebar_est_{e['Estimate ID']}", use_container_width=True):
                    st.session_state.active_estimate_id = e["Estimate ID"]; st.rerun()
        if st.button("＋ New estimate", use_container_width=True): st.session_state.active_estimate_id = "new"; st.rerun()
    elif page == "Clients":
        st.header("Clients")
        st.metric("Companies", len(st.session_state.companies)); st.metric("Contacts", len(st.session_state.contacts))
        st.markdown("---")
        for s in CLIENT_STATUSES: st.write(f"- {s}: {st.session_state.companies['Status'].value_counts().to_dict().get(s, 0)}")
        st.markdown("---")
        if st.button("＋ New company", use_container_width=True): st.session_state.active_company_id = "new"; st.rerun()
        if st.button("＋ New contact", use_container_width=True): st.session_state.active_contact_id = "new"; st.rerun()
    elif page == "Resourcing":
        st.header("Resourcing")
        cap = st.number_input("Weekly capacity (hrs)", min_value=1.0, max_value=80.0, value=float(st.session_state.res_capacity), step=1.0, key="res_cap_input")
        st.session_state.res_capacity = cap
        st.markdown("---")
        st.metric("Team members", len(member_names))
        today = pd.Timestamp.now().normalize()
        cur_monday = today - pd.Timedelta(days=today.weekday())
        cur_monday_str = cur_monday.strftime("%Y-%m-%d")
        _hol = holiday_dates_set(st.session_state.holidays)
        _wk = {"start": cur_monday, "workdays": week_workdays(cur_monday, _hol)}
        allocs = st.session_state.resource_allocs
        if not allocs.empty:
            over = []
            for m in member_names:
                m_leave = leave_dates_for_member(m, st.session_state.leave)
                wcap, _, _ = member_week_capacity(_wk, cap, m_leave, _hol)
                planned = member_week_planned(m, cur_monday_str, allocs)
                if planned > wcap: over.append(m)
            if over:
                st.warning("⚠️ Over capacity this week: " + ", ".join(over))
            else:
                st.caption("No one over capacity this week.")
        st.markdown("---")
        st.caption("🟩 plenty free  🟨 getting full  🟥 nearly full  ⬛ over capacity")

# ── PROJECT TRACKER ───────────────────────────────────────────────────────────

if page == "Project Tracker":
    filtered = filter_projects(st.session_state.projects, selected_stages, selected_status, search_query)
    display = filtered.copy()
    display["_sort"] = pd.to_datetime(display["Last updated"], errors="coerce")
    display = display.sort_values("_sort", ascending=False, na_position="last").drop(columns=["_sort"])
    display["Compliance %"] = display["Compliance checklist"].apply(compliance_progress)
    display["Milestone %"] = display["Milestones"].apply(milestone_progress)
    display["Budget"] = display["Budget"].apply(format_budget)
    show_cols = [c for c in COLUMNS if c != "Company ID"] + ["Compliance %", "Milestone %"]
    left, right = st.columns([2, 1])
    with left:
        st.subheader("Active projects")
        if display.empty: st.info("No projects match the filters.")
        else: st.dataframe(display[show_cols].fillna(""), use_container_width=True, hide_index=True)
    with right:
        st.subheader("Update an existing project")
        proj_options = [""] + st.session_state.projects["Project name"].dropna().unique().tolist()
        try: di = proj_options.index(st.session_state.selected_project)
        except ValueError: di = 0
        selected = st.selectbox("Select a project", proj_options, index=di, key=f"project_edit_select_{st.session_state.selectbox_key}")
        if selected != st.session_state.selected_project: st.session_state.selected_project = selected; st.rerun()
        if st.session_state.selected_project:
            selected = st.session_state.selected_project
            if st.button("✕ Cancel", key="cancel_edit"): st.session_state.selected_project = ""; st.session_state.selectbox_key += 1; st.rerun()
            pidx = st.session_state.projects[st.session_state.projects["Project name"] == selected].index[0]
            cur = st.session_state.projects.loc[pidx].to_dict()
            with st.form("edit_project_form"):
                st.text_input("Project ID", value=cur.get("Project ID", ""), disabled=True)
                comp_opts = ["(none)"] + company_names; cur_comp = cur.get("Client", "")
                e_company = st.selectbox("Client (company)", comp_opts, index=comp_opts.index(cur_comp) if cur_comp in comp_opts else 0)
                e_location = st.text_input("Location", value=cur.get("Location", ""))
                e_manager = st.text_input("Project manager", value=cur.get("Project manager", ""))
                e_members = st.multiselect("Team members", member_names, default=parse_team_members(cur.get("Team members", "")))
                c1, c2 = st.columns(2)
                with c1: e_start = st.date_input("Start date", value=parse_date(cur.get("Start date"), pd.Timestamp.now().date()))
                with c2: e_target = st.date_input("Target completion", value=parse_date(cur.get("Target completion"), pd.Timestamp.now().date()))
                e_stage = st.selectbox("Stage", STAGES, index=STAGES.index(cur.get("Stage")) if cur.get("Stage") in STAGES else 0)
                e_status = st.selectbox("Status", STATUSES, index=STATUSES.index(cur.get("Status")) if cur.get("Status") in STATUSES else 0)
                e_budget = st.number_input("Budget", min_value=0.0, step=100.0, value=parse_budget(cur.get("Budget", "0")), format="%f")
                e_fee = st.number_input("Total fee ($)", min_value=0.0, step=100.0, value=parse_budget(cur.get("Fee", "0")), format="%f")
                e_phase_fees = st.text_area("Phase fees", value=cur.get("Phase fees", ""), height=80)
                e_weekly_hours = st.number_input("Weekly hours allocated", min_value=0.0, step=1.0, value=parse_weekly_hours(cur.get("Weekly hours allocated", "0")))
                e_member_hours = st.text_area("Member hours allocation", value=cur.get("Member hours allocation", ""), height=80)
                e_phase_schedule = st.text_area("Phase schedule", value=cur.get("Phase schedule", ""), height=80)
                e_milestones = st.text_area("Milestones", value=cur.get("Milestones", ""), height=100)
                e_compliance = st.multiselect("Compliance checklist", COMPLIANCE_TASKS, default=compliance_to_list(cur.get("Compliance checklist", "")))
                e_notes = st.text_area("Notes", value=cur.get("Notes", ""), height=80)
                st.progress(stage_progress(cur.get("Stage")))
                comp_row = st.session_state.companies[st.session_state.companies["Name"] == e_company]
                comp_id = comp_row.iloc[0]["Company ID"] if not comp_row.empty else ""
                upd = st.form_submit_button("Update project"); dlt = st.form_submit_button("Delete project")
                if upd:
                    st.session_state.projects = add_or_update_project({"Project ID": cur.get("Project ID", ""), "Project name": selected, "Client": e_company if e_company != "(none)" else "", "Company ID": comp_id, "Location": e_location, "Project manager": e_manager, "Start date": e_start.strftime("%Y-%m-%d"), "Target completion": e_target.strftime("%Y-%m-%d"), "Stage": e_stage, "Status": e_status, "Budget": str(e_budget), "Fee": str(e_fee), "Phase fees": e_phase_fees, "Weekly hours allocated": str(e_weekly_hours), "Member hours allocation": normalize_member_hours(parse_member_hours(e_member_hours)), "Phase schedule": normalize_phase_schedule(e_phase_schedule), "Milestones": normalize_milestones(e_milestones), "Team members": normalize_team_members(e_members), "Compliance checklist": normalize_checklist(e_compliance), "Notes": e_notes}, st.session_state.projects)
                    save_projects(st.session_state.projects); st.session_state.message = f"Updated '{selected}'."; st.session_state.selected_project = ""; st.session_state.selectbox_key += 1; st.rerun()
                if dlt:
                    st.session_state.projects = st.session_state.projects[st.session_state.projects["Project name"] != selected]
                    save_projects(st.session_state.projects); st.session_state.message = f"Deleted '{selected}'."; st.session_state.selected_project = ""; st.session_state.selectbox_key += 1; st.rerun()
    st.markdown("---")
    st.subheader("Project Timelines")
    view_tab1, view_tab2 = st.tabs(["📊 Gantt", "🟦 Cards"])
    with view_tab1: build_gantt_chart(filtered)
    with view_tab2:
        st.caption("🔴 < 14 days  |  🟡 14–30 days  |  🟢 30+ days  |  ⚫ Not scheduled / passed")
        build_traffic_light_cards(filtered)
    st.markdown("---")
    col_add = st.container()
    with col_add:
        if st.button("▲ Close" if st.session_state.show_add_project else "＋ Add a new project", key="toggle_add_project", use_container_width=True):
            st.session_state.show_add_project = not st.session_state.show_add_project; st.rerun()
        if st.session_state.show_add_project:
            with st.form("new_project_form"):
                n_id = st.text_input("Project ID (leave blank to auto-generate)"); n_name = st.text_input("Project name")
                comp_opts2 = ["(none)"] + company_names; n_company = st.selectbox("Client (company)", comp_opts2)
                n_location = st.text_input("Location"); n_manager = st.text_input("Project manager")
                c1, c2 = st.columns(2)
                with c1: n_start = st.date_input("Start date")
                with c2: n_target = st.date_input("Target completion")
                n_stage = st.selectbox("Stage", STAGES); n_status = st.selectbox("Status", STATUSES)
                n_budget = st.number_input("Budget", min_value=0.0, step=100.0, format="%f")
                n_fee = st.number_input("Total fee ($)", min_value=0.0, step=100.0, format="%f")
                n_phase_fees = st.text_area("Phase fees", height=80); n_weekly_hours = st.number_input("Weekly hours allocated", min_value=0.0, step=1.0)
                n_member_hours = st.text_area("Member hours allocation", height=80); n_phase_schedule = st.text_area("Phase schedule", height=80)
                n_milestones = st.text_area("Milestones", height=80); n_members = st.multiselect("Team members", member_names)
                n_compliance = st.multiselect("Compliance checklist", COMPLIANCE_TASKS); n_notes = st.text_area("Notes", height=80)
                if st.form_submit_button("Save project", use_container_width=True):
                    if not n_name: st.warning("Please enter a project name.")
                    else:
                        comp_row2 = st.session_state.companies[st.session_state.companies["Name"] == n_company]
                        st.session_state.projects = add_or_update_project({"Project ID": n_id, "Project name": n_name, "Client": n_company if n_company != "(none)" else "", "Company ID": comp_row2.iloc[0]["Company ID"] if not comp_row2.empty else "", "Location": n_location, "Project manager": n_manager, "Start date": n_start.strftime("%Y-%m-%d"), "Target completion": n_target.strftime("%Y-%m-%d"), "Stage": n_stage, "Status": n_status, "Budget": str(n_budget), "Fee": str(n_fee), "Phase fees": n_phase_fees, "Weekly hours allocated": str(n_weekly_hours), "Member hours allocation": normalize_member_hours(parse_member_hours(n_member_hours)), "Phase schedule": normalize_phase_schedule(n_phase_schedule), "Milestones": normalize_milestones(n_milestones), "Team members": normalize_team_members(n_members), "Compliance checklist": normalize_checklist(n_compliance), "Notes": n_notes}, st.session_state.projects)
                        save_projects(st.session_state.projects); st.session_state.message = f"Saved '{n_name}'."; st.session_state.show_add_project = False; st.rerun()

# ── TASK TRACKER ──────────────────────────────────────────────────────────────

elif page == "Task Tracker":
    sel_proj = st.session_state.get("task_project_select", "All projects")
    sel_teams = st.session_state.get("task_team_filter", TASK_TEAMS)
    sel_statuses = st.session_state.get("task_status_filter", TASK_STATUSES)
    task_query = st.text_input("Search tasks")
    task_df = st.session_state.tasks.copy()
    if sel_proj and sel_proj != "All projects": task_df = task_df[task_df["Project name"] == sel_proj]
    if sel_teams: task_df = task_df[task_df["Team"].isin(sel_teams)]
    if sel_statuses: task_df = task_df[task_df["Status"].isin(sel_statuses)]
    if task_query:
        q = task_query.lower()
        task_df = task_df[task_df["Task name"].str.lower().str.contains(q, na=False) | task_df["Project name"].str.lower().str.contains(q, na=False) | task_df["Assigned to"].str.lower().str.contains(q, na=False)]
    st.subheader("Project task tracker")
    if task_df.empty: st.info("No tasks match the filters.")
    else:
        cols = st.columns(3)
        for i, (_, task) in enumerate(task_df.iterrows()):
            tid = task["Task ID"]; colour = TASK_STATUS_COLOURS.get(task["Status"], "#aaaaaa"); is_exp = st.session_state.expanded_task == tid
            with cols[i % 3]:
                st.markdown(f"<div style='border:1px solid #e3e1dd;border-radius:6px;padding:14px 16px;margin-bottom:6px;background:#ffffff;border-left:4px solid {colour};box-shadow:0 1px 3px rgba(0,0,0,0.04)'><div style='font-weight:700;font-size:14px;margin-bottom:4px;color:#1a1a1a'>{task['Task name']}</div><div style='font-size:11px;color:#6b6b6b;margin-bottom:4px'>📁 {task['Project name']}</div><div style='font-size:11px;color:#6b6b6b;margin-bottom:4px'>👤 {task['Assigned to'] or 'Unassigned'}</div><div style='display:inline-block;padding:2px 10px;border-radius:12px;background:{colour};color:white;font-size:11px;font-weight:600'>{task['Status']}</div>" + (f"<div style='font-size:11px;color:#888;margin-top:8px'>{task['Notes']}</div>" if task["Notes"] else "") + "</div>", unsafe_allow_html=True)
                if st.button("▲ Close" if is_exp else "✏️ Edit", key=f"task_toggle_{tid}", use_container_width=True):
                    st.session_state.expanded_task = None if is_exp else tid; st.rerun()
                if is_exp:
                    with st.form(key=f"edit_task_tile_{tid}"):
                        et_name = st.text_input("Task name", value=task["Task name"])
                        et_team = st.selectbox("Team", TASK_TEAMS, index=TASK_TEAMS.index(task["Team"]) if task["Team"] in TASK_TEAMS else 0)
                        et_assigned = st.multiselect("Assigned to", member_names, default=[m.strip() for m in str(task["Assigned to"]).split(";") if m.strip()])
                        et_status = st.selectbox("Status", TASK_STATUSES, index=TASK_STATUSES.index(task["Status"]) if task["Status"] in TASK_STATUSES else 0)
                        et_notes = st.text_area("Notes", value=task["Notes"], height=80)
                        sv = st.form_submit_button("Save", use_container_width=True); dl = st.form_submit_button("Delete", use_container_width=True)
                        if sv:
                            st.session_state.tasks = add_or_update_task({"Task ID": tid, "Project ID": task["Project ID"], "Project name": task["Project name"], "Task name": et_name, "Team": et_team, "Assigned to": "; ".join(et_assigned), "Status": et_status, "Notes": et_notes}, st.session_state.tasks)
                            save_tasks(st.session_state.tasks); st.session_state.expanded_task = None; st.rerun()
                        if dl:
                            st.session_state.tasks = st.session_state.tasks[st.session_state.tasks["Task ID"] != tid]
                            save_tasks(st.session_state.tasks); st.session_state.expanded_task = None; st.rerun()
    st.markdown("---"); st.subheader("Add a new task")
    with st.form("new_task_form"):
        tp = st.selectbox("Project", [""] + st.session_state.projects["Project name"].dropna().unique().tolist())
        tn = st.text_input("Task name"); tt = st.selectbox("Team", TASK_TEAMS)
        ta = st.multiselect("Assigned to", member_names); ts2 = st.selectbox("Status", TASK_STATUSES); tno = st.text_area("Notes", height=80)
        if st.form_submit_button("Create task"):
            if not tp or not tn: st.warning("Please select a project and enter a task name.")
            else:
                pr = st.session_state.projects[st.session_state.projects["Project name"] == tp]
                st.session_state.tasks = add_or_update_task({"Task ID": "", "Project ID": pr.iloc[0]["Project ID"] if not pr.empty else "", "Project name": tp, "Task name": tn, "Team": tt, "Assigned to": "; ".join(ta), "Status": ts2, "Notes": tno}, st.session_state.tasks)
                save_tasks(st.session_state.tasks); st.rerun()

# ── TIMESHEETS ────────────────────────────────────────────────────────────────

elif page == "Timesheets":
    st.subheader("Timesheets")
    tab_weekly, tab_history = st.tabs(["📅 Weekly Entry", "📋 Log & History"])

    with tab_weekly:
        if not member_names:
            st.warning("No team members set up yet. Add team members in the Project Tracker page first.")
        else:
            col_m, col_prev, col_week, col_next = st.columns([2, 1, 3, 1])
            wt_member = col_m.selectbox("Team member", member_names, key="wt_member_main")

            if "wt_week_offset" not in st.session_state: st.session_state.wt_week_offset = 0
            if col_prev.button("◀", key="wt_prev"): st.session_state.wt_week_offset -= 1; st.rerun()
            if col_next.button("▶", key="wt_next"): st.session_state.wt_week_offset += 1; st.rerun()

            today = pd.Timestamp.now().normalize()
            week_start = today - pd.Timedelta(days=today.weekday()) + pd.Timedelta(weeks=st.session_state.wt_week_offset)
            week_days = [week_start + pd.Timedelta(days=i) for i in range(7)]
            day_labels = [d.strftime("%a %b %-d") for d in week_days]
            day_keys   = [d.strftime("%Y-%m-%d") for d in week_days]
            col_week.markdown(f"<div style='text-align:center;font-weight:600;padding-top:6px'>Weekly Summary — {week_start.strftime('%-d %b')} to {(week_start + pd.Timedelta(days=6)).strftime('%-d %b %Y')}</div>", unsafe_allow_html=True)

            mem_row = st.session_state.members_df[st.session_state.members_df["Team member"] == wt_member]
            mem_role = mem_row.iloc[0]["Role"] if not mem_row.empty else list(DEFAULT_ROLES.keys())[0]
            mem_rate = role_rates.get(mem_role, 0.0)

            ts = st.session_state.timesheets
            week_entries = ts[(ts["Team member"] == wt_member) & (ts["Date"].isin(day_keys))].copy()

            existing_rows = set()
            for _, e in week_entries.iterrows():
                existing_rows.add((e["Project ID"], e["Project name"], e["Phase"]))

            wt_rows_key = f"wt_rows_{wt_member}_{week_start.strftime('%Y%m%d')}"
            if wt_rows_key not in st.session_state:
                st.session_state[wt_rows_key] = list(existing_rows)
            else:
                for r in existing_rows:
                    if r not in st.session_state[wt_rows_key]:
                        st.session_state[wt_rows_key].append(r)

            rows = st.session_state[wt_rows_key]

            add_key = f"wt_add_{wt_member}_{week_start.strftime('%Y%m%d')}"
            if st.session_state.get(add_key, False):
                with st.form(f"wt_add_form_{wt_member}_{week_start.strftime('%Y%m%d')}"):
                    proj_opts = [""] + st.session_state.projects["Project name"].dropna().unique().tolist()
                    ap = st.selectbox("Project", proj_opts, key="wt_add_proj")
                    af = st.selectbox("Phase / Task", [""] + STAGES + ["Project Meetings", "Project Set Up", "ACTIVITY", "General"], key="wt_add_phase")
                    c1, c2 = st.columns(2)
                    if c1.form_submit_button("Add row", use_container_width=True):
                        if ap and af:
                            pr = st.session_state.projects[st.session_state.projects["Project name"] == ap]
                            pid = pr.iloc[0]["Project ID"] if not pr.empty else ""
                            new_row = (pid, ap, af)
                            if new_row not in rows:
                                st.session_state[wt_rows_key].append(new_row)
                            st.session_state[add_key] = False; st.rerun()
                    if c2.form_submit_button("Cancel", use_container_width=True):
                        st.session_state[add_key] = False; st.rerun()

            lock_key = f"wt_locked_{wt_member}_{week_start.strftime('%Y%m%d')}"
            is_locked = st.session_state.get(lock_key, False)

            st.markdown("---")
            header_cols = st.columns([4, 1] + [1]*7 + [1])
            header_cols[0].markdown("**Job / Task**")
            for j, lbl in enumerate(day_labels):
                header_cols[j+2].markdown(f"<div style='font-size:11px;font-weight:600;text-align:center'>{lbl}</div>", unsafe_allow_html=True)
            header_cols[-1].markdown("<div style='font-size:11px;font-weight:600;text-align:center'>Total</div>", unsafe_allow_html=True)

            FIXED_ROWS = [
                ("", "Admin", "Admin"), ("", "WIP", "WIP"),
                ("", "Design Team Meeting", "Design Team Meeting"), ("", "Red Dot Projects", "Red Dot Projects"),
            ]
            for fixed in reversed(FIXED_ROWS):
                if fixed not in rows:
                    st.session_state[wt_rows_key].insert(0, fixed)
            fixed_set = set(FIXED_ROWS)
            project_rows = [r for r in st.session_state[wt_rows_key] if r not in fixed_set]
            st.session_state[wt_rows_key] = FIXED_ROWS + project_rows
            rows = st.session_state[wt_rows_key]

            input_grid = {}
            for ri, (pid, pname, phase) in enumerate(rows):
                input_grid[ri] = {}
                for dk in day_keys:
                    match = week_entries[(week_entries["Project name"] == pname) & (week_entries["Phase"] == phase) & (week_entries["Date"] == dk)]
                    input_grid[ri][dk] = parse_budget(match.iloc[0]["Hours"]) if not match.empty else 0.0

            day_totals = {dk: 0.0 for dk in day_keys}
            new_grid = {}
            for ri, (pid, pname, phase) in enumerate(rows):
                new_grid[ri] = {}
                is_fixed = (pid == "" and pname in {r[1] for r in FIXED_ROWS})
                row_cols = st.columns([4, 1] + [1]*7 + [1])
                row_cols[0].markdown(
                    f"<div style='font-size:13px;font-weight:600;color:#2c3e50'>{pname}</div>"
                    f"<div style='font-size:11px;color:#888'>{phase if not is_fixed else ''}</div>",
                    unsafe_allow_html=True)
                if not is_fixed:
                    if row_cols[1].button("✕", key=f"wt_rm_{ri}_{wt_member}_{week_start.strftime('%Y%m%d')}", disabled=is_locked):
                        st.session_state[wt_rows_key].pop(ri); st.rerun()
                row_total = 0.0
                for j, dk in enumerate(day_keys):
                    val = row_cols[j+2].number_input("h", min_value=0.0, max_value=24.0, step=0.25, value=input_grid[ri][dk],
                        key=f"wt_cell_{ri}_{dk}_{wt_member}", label_visibility="collapsed", format="%.2f", disabled=is_locked)
                    new_grid[ri][dk] = val; row_total += val; day_totals[dk] += val
                row_cols[-1].markdown(f"<div style='text-align:center;font-weight:700;padding-top:6px'>{row_total:.2f}</div>", unsafe_allow_html=True)

            st.markdown("---")
            tot_cols = st.columns([4, 1] + [1]*7 + [1])
            tot_cols[0].markdown("**Daily Total**")
            grand_total = 0.0
            for j, dk in enumerate(day_keys):
                tot_cols[j+2].markdown(f"<div style='text-align:center;font-weight:700'>{day_totals[dk]:.2f}</div>", unsafe_allow_html=True)
                grand_total += day_totals[dk]
            tot_cols[-1].markdown(f"<div style='text-align:center;font-weight:700;color:#2ecc71'>{grand_total:.2f}</div>", unsafe_allow_html=True)

            st.markdown("")

            if is_locked:
                st.warning(f"✅ Timesheet submitted and locked for **{wt_member}** — {week_start.strftime('%-d %b')} to {(week_start + pd.Timedelta(days=6)).strftime('%-d %b %Y')}")
                if st.session_state.get("wt_show_unlock") and \
                   st.session_state.get("wt_unlock_member") == wt_member and \
                   st.session_state.get("wt_unlock_week") == week_start.strftime('%Y%m%d'):
                    with st.form(key=f"unlock_form_{lock_key}"):
                        st.markdown("**🔒 Enter password to unlock timesheet**")
                        pw = st.text_input("Password", type="password", key=f"unlock_pw_{lock_key}")
                        u1, u2 = st.columns(2)
                        if u1.form_submit_button("Unlock", use_container_width=True):
                            if pw == TIMESHEET_LOCK_PASSWORD:
                                st.session_state[lock_key] = False; st.session_state.wt_show_unlock = False; st.rerun()
                            else: st.error("Incorrect password.")
                        if u2.form_submit_button("Cancel", use_container_width=True):
                            st.session_state.wt_show_unlock = False; st.rerun()
                else:
                    if st.button("🔓 Unlock to edit", key=f"show_unlock_{lock_key}", use_container_width=False):
                        st.session_state.wt_show_unlock = True; st.session_state.wt_unlock_member = wt_member
                        st.session_state.wt_unlock_week = week_start.strftime('%Y%m%d'); st.rerun()
            else:
                btn1, btn2, btn3, _ = st.columns([2, 2, 2, 2])
                if btn1.button("＋ Add a Task", use_container_width=True, key=f"wt_add_btn_{wt_member}"):
                    st.session_state[add_key] = True; st.rerun()

                if btn2.button("💾 Save Timesheet", use_container_width=True, key=f"wt_save_{wt_member}"):
                    ts_df = st.session_state.timesheets.copy()
                    ts_df = ts_df[~((ts_df["Team member"] == wt_member) & (ts_df["Date"].isin(day_keys)))]
                    new_entries = []
                    for ri, (pid, pname, phase) in enumerate(rows):
                        for dk in day_keys:
                            hrs = new_grid[ri].get(dk, 0.0)
                            if hrs > 0:
                                is_fixed_row = (pid == "" and pname in {r[1] for r in FIXED_ROWS})
                                new_entries.append({"Entry ID": create_id(), "Project ID": pid, "Project name": pname, "Phase": phase, "Team member": wt_member, "Role": mem_role, "Date": dk, "Hours": str(hrs), "Rate": "0.0" if is_fixed_row else str(mem_rate), "Notes": "", "Invoiced": "False"})
                    if new_entries:
                        ts_df = pd.concat([ts_df, pd.DataFrame(new_entries)], ignore_index=True)
                    st.session_state.timesheets = ts_df
                    save_timesheets(st.session_state.timesheets)
                    st.success(f"Timesheet saved — {grand_total:.2f} hrs logged for {wt_member}."); st.rerun()

                if btn3.button("📤 Submit Timesheet", use_container_width=True, key=f"wt_submit_{wt_member}"):
                    ts_df = st.session_state.timesheets.copy()
                    ts_df = ts_df[~((ts_df["Team member"] == wt_member) & (ts_df["Date"].isin(day_keys)))]
                    new_entries = []
                    for ri, (pid, pname, phase) in enumerate(rows):
                        for dk in day_keys:
                            hrs = new_grid[ri].get(dk, 0.0)
                            if hrs > 0:
                                is_fixed_row = (pid == "" and pname in {r[1] for r in FIXED_ROWS})
                                new_entries.append({"Entry ID": create_id(), "Project ID": pid, "Project name": pname, "Phase": phase, "Team member": wt_member, "Role": mem_role, "Date": dk, "Hours": str(hrs), "Rate": "0.0" if is_fixed_row else str(mem_rate), "Notes": "", "Invoiced": "False"})
                    if new_entries:
                        ts_df = pd.concat([ts_df, pd.DataFrame(new_entries)], ignore_index=True)
                    st.session_state.timesheets = ts_df
                    save_timesheets(st.session_state.timesheets)
                    st.session_state[lock_key] = True; st.rerun()

    with tab_history:
        ts_df = st.session_state.timesheets.copy()
        f1, f2 = st.columns(2)
        hist_proj = f1.selectbox("Project", ["All projects"] + st.session_state.projects["Project name"].dropna().unique().tolist(), key="ts_proj_filter")
        hist_member = f2.selectbox("Team member", ["All members"] + member_names, key="ts_member_filter")
        if hist_proj != "All projects": ts_df = ts_df[ts_df["Project name"] == hist_proj]
        if hist_member != "All members": ts_df = ts_df[ts_df["Team member"] == hist_member]
        if ts_df.empty: st.info("No timesheet entries yet.")
        else:
            ts_df["Cost"] = ts_df.apply(lambda r: round(parse_budget(r["Hours"]) * (parse_budget(r["Rate"]) if r["Rate"] else role_rates.get(r["Role"], 0)), 2), axis=1)
            m1, m2, m3 = st.columns(3)
            m1.metric("Total hours", f"{ts_df['Hours'].apply(parse_budget).sum():.1f}")
            m2.metric("Total cost", f"${ts_df['Cost'].sum():,.2f}")
            m3.metric("Entries", len(ts_df))
            st.markdown("---")
            cols = st.columns(3)
            for i, (_, e) in enumerate(ts_df.sort_values("Date", ascending=False).iterrows()):
                eid = e["Entry ID"]; invoiced = e.get("Invoiced", "False") == "True"
                with cols[i % 3]:
                    border_col = "#2ecc71" if invoiced else "#1a1a1a"
                    badge = "<span style='background:#2ecc71;color:white;padding:2px 8px;border-radius:8px;font-size:10px'>🧾 Invoiced</span>" if invoiced else ""
                    st.markdown(f"<div style='border:1px solid #e3e1dd;border-radius:6px;padding:14px 16px;margin-bottom:6px;background:#ffffff;border-left:4px solid {border_col};box-shadow:0 1px 3px rgba(0,0,0,0.04)'><div style='font-weight:700;font-size:14px;color:#1a1a1a'>{e['Team member']} {badge}</div><div style='font-size:11px;color:#6b6b6b'>📁 {e['Project name']} — {e['Phase'] or 'No phase'}</div><div style='font-size:11px;color:#6b6b6b'>🗓 {e['Date']} &nbsp;·&nbsp; {e['Role']}</div><div style='font-size:13px;font-weight:600;margin-top:6px;color:#1a1a1a'>{e['Hours']} hrs @ ${e['Rate']}/hr = <span style='color:#2ecc71'>${e['Cost']:,.2f}</span></div>" + (f"<div style='font-size:11px;color:#888;margin-top:4px'>{e['Notes']}</div>" if e["Notes"] else "") + "</div>", unsafe_allow_html=True)
                    if st.button("🗑 Delete", key=f"del_ts_page_{eid}", use_container_width=True):
                        st.session_state.timesheets = st.session_state.timesheets[st.session_state.timesheets["Entry ID"] != eid]
                        save_timesheets(st.session_state.timesheets); st.rerun()
        st.markdown("---")
        st.subheader("Fee summary by project")
        if not st.session_state.projects.empty:
            rows_summary = []
            for _, row in st.session_state.projects.iterrows():
                pid = row["Project ID"]; fee = parse_budget(row.get("Fee", row.get("Budget", "0")))
                consumed = project_fee_consumed(pid, st.session_state.timesheets, role_rates)
                hours = project_hours_logged(pid, st.session_state.timesheets)
                pct = round((consumed / fee) * 100, 1) if fee > 0 else 0
                rows_summary.append({"Project": row["Project name"], "Client": row["Client"], "Total fee": f"${fee:,.2f}", "Hours logged": hours, "Fee consumed": f"${consumed:,.2f}", "% used": f"{pct}%"})
            st.dataframe(pd.DataFrame(rows_summary), use_container_width=True)

# ── FEE ESTIMATOR ─────────────────────────────────────────────────────────────

elif page == "Fee Estimator":
    st.subheader("Fee Estimator")
    act = st.session_state.active_estimate_id
    if act == "new":
        st.markdown("### New estimate")
        with st.form("new_estimate_form"):
            ne_name = st.text_input("Estimate name"); ne_client = st.text_input("Client")
            comp_opts3 = ["(none)"] + company_names; ne_comp = st.selectbox("Link to company", comp_opts3)
            proj_opts = ["(none)"] + st.session_state.projects["Project name"].dropna().unique().tolist()
            ne_proj = st.selectbox("Link to project (optional)", proj_opts)
            ne_margin = st.number_input("Margin %", min_value=0.0, max_value=100.0, step=0.5, value=15.0)
            ne_notes = st.text_area("Notes", height=80)
            if st.form_submit_button("Create estimate", use_container_width=True):
                if not ne_name: st.warning("Please enter an estimate name.")
                else:
                    proj_row = st.session_state.projects[st.session_state.projects["Project name"] == ne_proj]
                    comp_row3 = st.session_state.companies[st.session_state.companies["Name"] == ne_comp]
                    new_est = {"Estimate ID": create_id(), "Estimate name": ne_name, "Client": ne_comp if ne_comp != "(none)" else ne_client, "Company ID": comp_row3.iloc[0]["Company ID"] if not comp_row3.empty else "", "Project ID": proj_row.iloc[0]["Project ID"] if not proj_row.empty else "", "Project name": ne_proj if ne_proj != "(none)" else "", "Margin %": str(ne_margin), "Notes": ne_notes, "Created": pd.Timestamp.now().strftime("%Y-%m-%d"), "Last updated": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")}
                    st.session_state.estimates = pd.concat([st.session_state.estimates, pd.DataFrame([new_est])], ignore_index=True)
                    save_estimates(st.session_state.estimates); st.session_state.active_estimate_id = new_est["Estimate ID"]; st.rerun()
        if st.button("✕ Cancel", key="cancel_new_est"): st.session_state.active_estimate_id = None; st.rerun()
    elif act is not None:
        est_row = st.session_state.estimates[st.session_state.estimates["Estimate ID"] == act]
        if est_row.empty: st.warning("Estimate not found.")
        else:
            est = est_row.iloc[0].to_dict()
            totals = estimate_totals(act, st.session_state.estimate_lines, st.session_state.estimate_disb, est.get("Margin %", "0"), role_rates)
            hc1, hc2, hc3 = st.columns([3, 1, 1])
            hc1.markdown(f"## {est['Estimate name']}"); hc1.caption(f"{est['Client']} · {est.get('Project name','No project')} · Created {est.get('Created','')}")
            if hc2.button("✏️ Edit details", use_container_width=True): st.session_state[f"edit_est_{act}"] = not st.session_state.get(f"edit_est_{act}", False); st.rerun()
            if hc3.button("✕ Close", use_container_width=True): st.session_state.active_estimate_id = None; st.rerun()
            if st.session_state.get(f"edit_est_{act}", False):
                with st.form("edit_est_details"):
                    ee_name = st.text_input("Estimate name", value=est["Estimate name"]); ee_client = st.text_input("Client", value=est["Client"])
                    ee_margin = st.number_input("Margin %", min_value=0.0, max_value=100.0, step=0.5, value=parse_budget(est.get("Margin %", "15")))
                    ee_notes = st.text_area("Notes", value=est.get("Notes", ""), height=80)
                    proj_opts2 = ["(none)"] + st.session_state.projects["Project name"].dropna().unique().tolist()
                    curr_proj = est.get("Project name", "")
                    ee_proj = st.selectbox("Linked project", proj_opts2, index=proj_opts2.index(curr_proj) if curr_proj in proj_opts2 else 0)
                    s1, s2 = st.columns(2)
                    if s1.form_submit_button("Save", use_container_width=True):
                        eidx = st.session_state.estimates[st.session_state.estimates["Estimate ID"] == act].index[0]
                        proj_row2 = st.session_state.projects[st.session_state.projects["Project name"] == ee_proj]
                        for k, v in [("Estimate name", ee_name), ("Client", ee_client), ("Margin %", str(ee_margin)), ("Notes", ee_notes), ("Project name", ee_proj if ee_proj != "(none)" else ""), ("Project ID", proj_row2.iloc[0]["Project ID"] if not proj_row2.empty else ""), ("Last updated", pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"))]:
                            st.session_state.estimates.at[eidx, k] = v
                        save_estimates(st.session_state.estimates); st.session_state[f"edit_est_{act}"] = False; st.rerun()
                    if s2.form_submit_button("Delete estimate", use_container_width=True):
                        for df_key, save_fn in [("estimates", save_estimates), ("estimate_lines", save_estimate_lines), ("estimate_disb", save_estimate_disb)]:
                            st.session_state[df_key] = st.session_state[df_key][st.session_state[df_key]["Estimate ID"] != act]; save_fn(st.session_state[df_key])
                        st.session_state.active_estimate_id = None; st.rerun()
            st.markdown("---")
            mc1, mc2, mc3, mc4, mc5 = st.columns(5)
            mc1.metric("Hours cost", f"${totals['hours_cost']:,.2f}"); mc2.metric("Disbursements", f"${totals['total_disb']:,.2f}")
            mc3.metric("Subtotal", f"${totals['subtotal']:,.2f}"); mc4.metric(f"Margin ({est.get('Margin %','0')}%)", f"${totals['margin_amt']:,.2f}"); mc5.metric("TOTAL FEE", f"${totals['total']:,.2f}")
            st.markdown("---"); st.markdown("### Phase & Role Hours")
            for phase in STAGES:
                with st.expander(f"**{phase}**", expanded=True):
                    phase_lines = st.session_state.estimate_lines[(st.session_state.estimate_lines["Estimate ID"] == act) & (st.session_state.estimate_lines["Phase"] == phase)]
                    roles = list(DEFAULT_ROLES.keys())
                    with st.form(key=f"phase_form_{act}_{phase}"):
                        hour_inputs = {}; fcols = st.columns(len(roles) + 1); fcols[0].markdown("**Hrs / Cost**")
                        for j, role in enumerate(roles): fcols[j+1].markdown(f"**{role}**")
                        hr_cols = st.columns(len(roles) + 1); hr_cols[0].markdown("Hours")
                        for j, role in enumerate(roles):
                            existing = phase_lines[phase_lines["Role"] == role]
                            curr_hrs = parse_budget(existing.iloc[0]["Hours"]) if not existing.empty else 0.0
                            hour_inputs[role] = hr_cols[j+1].number_input(role, min_value=0.0, step=0.5, value=curr_hrs, key=f"hrs_{act}_{phase}_{role}", label_visibility="collapsed")
                        cost_cols = st.columns(len(roles) + 1); cost_cols[0].markdown("Cost"); phase_cost = 0.0
                        for j, role in enumerate(roles):
                            c = hour_inputs[role] * role_rates.get(role, 0); phase_cost += c; cost_cols[j+1].markdown(f"${c:,.0f}")
                        if st.form_submit_button(f"Save {phase}", use_container_width=True):
                            st.session_state.estimate_lines = st.session_state.estimate_lines[~((st.session_state.estimate_lines["Estimate ID"] == act) & (st.session_state.estimate_lines["Phase"] == phase))]
                            new_lines = [{"Line ID": create_id(), "Estimate ID": act, "Phase": phase, "Role": role, "Hours": str(hrs), "Rate": str(role_rates.get(role, 0.0))} for role, hrs in hour_inputs.items() if hrs > 0]
                            if new_lines: st.session_state.estimate_lines = pd.concat([st.session_state.estimate_lines, pd.DataFrame(new_lines)], ignore_index=True)
                            save_estimate_lines(st.session_state.estimate_lines); st.rerun()
                    st.caption(f"Phase subtotal: ${phase_cost:,.2f}")
            st.markdown("---"); st.markdown("### Disbursements")
            disb_df2 = st.session_state.estimate_disb[st.session_state.estimate_disb["Estimate ID"] == act]
            if not disb_df2.empty:
                for _, d in disb_df2.iterrows():
                    did = d["Disb ID"]; dc1, dc2, dc3, dc4 = st.columns([3, 2, 2, 1])
                    dc1.markdown(f"**{d['Description']}**"); dc2.caption(d["Type"]); dc3.markdown(f"${parse_budget(d['Value']):,.2f}" if d["Type"] == "Fixed ($)" else f"{d['Value']}%")
                    if dc4.button("🗑", key=f"del_disb_{did}"):
                        st.session_state.estimate_disb = st.session_state.estimate_disb[st.session_state.estimate_disb["Disb ID"] != did]; save_estimate_disb(st.session_state.estimate_disb); st.rerun()
            with st.form("add_disb_form"):
                dc1, dc2, dc3 = st.columns([3, 2, 2])
                disb_desc = dc1.text_input("Description"); disb_type = dc2.selectbox("Type", ["Fixed ($)", "% of fee"]); disb_val = dc3.number_input("Value", min_value=0.0, step=10.0)
                if st.form_submit_button("Add disbursement", use_container_width=True):
                    if disb_desc:
                        st.session_state.estimate_disb = pd.concat([st.session_state.estimate_disb, pd.DataFrame([{"Disb ID": create_id(), "Estimate ID": act, "Description": disb_desc, "Type": disb_type, "Value": str(disb_val)}])], ignore_index=True)
                        save_estimate_disb(st.session_state.estimate_disb); st.rerun()
            st.markdown("---")
            if est.get("Project ID"):
                if st.button("📤 Push total fee to linked project", use_container_width=True):
                    pidx2 = st.session_state.projects[st.session_state.projects["Project ID"] == est["Project ID"]].index
                    if not pidx2.empty:
                        st.session_state.projects.at[pidx2[0], "Fee"] = str(totals["total"]); save_projects(st.session_state.projects); st.success(f"Fee of ${totals['total']:,.2f} pushed to '{est['Project name']}'.")
            est_fresh = st.session_state.estimates[st.session_state.estimates["Estimate ID"] == act].iloc[0].to_dict()
            totals_fresh = estimate_totals(act, st.session_state.estimate_lines, st.session_state.estimate_disb, est_fresh.get("Margin %", "0"), role_rates)
            pdf_html = generate_pdf_html(est_fresh, st.session_state.estimate_lines, st.session_state.estimate_disb, totals_fresh, role_rates)
            st.download_button("⬇️ Download estimate as HTML (print to PDF)", data=pdf_html.encode("utf-8"), file_name=f"estimate_{est_fresh['Estimate name'].replace(' ','_')}.html", mime="text/html", use_container_width=True)
    else:
        st.info("Select an estimate from the sidebar or create a new one.")

# ── CLIENTS ───────────────────────────────────────────────────────────────────

elif page == "Clients":
    st.subheader("Client Database")
    if not st.session_state.companies.empty:
        status_counts = st.session_state.companies["Status"].value_counts().reset_index()
        status_counts.columns = ["Status", "Count"]
        pie = alt.Chart(status_counts).mark_arc(innerRadius=50).encode(
            theta=alt.Theta("Count:Q"),
            color=alt.Color("Status:N", scale=alt.Scale(domain=list(CLIENT_STATUS_COLOURS.keys()), range=list(CLIENT_STATUS_COLOURS.values())), legend=alt.Legend(title="Status")),
            tooltip=[alt.Tooltip("Status:N"), alt.Tooltip("Count:Q")],
        ).properties(width=260, height=260, title="Clients by status")
        text = alt.Chart(status_counts).mark_text(radius=130, fontSize=12, fontWeight="bold").encode(
            theta=alt.Theta("Count:Q", stack=True), text=alt.Text("Count:Q"), color=alt.value("#333"), order=alt.Order("Count:Q"))
        chart = alt.layer(pie, text).resolve_scale(color="independent")
        col_chart, col_summary, _ = st.columns([1, 1, 2])
        with col_chart: st.altair_chart(chart, use_container_width=False)
        with col_summary:
            st.markdown("**Summary**")
            for s in CLIENT_STATUSES:
                cnt = int(status_counts[status_counts["Status"] == s]["Count"].sum()) if s in status_counts["Status"].values else 0
                colour = CLIENT_STATUS_COLOURS[s]
                st.markdown(f"<div style='display:flex;align-items:center;gap:8px;margin-bottom:6px'><div style='width:14px;height:14px;border-radius:50%;background:{colour}'></div><span style='font-size:13px'><strong>{s}</strong>: {cnt}</span></div>", unsafe_allow_html=True)
        st.markdown("---")

    tab_companies, tab_contacts = st.tabs(["🏢 Companies", "👤 Contacts"])

    with tab_companies:
        search_co = st.text_input("Search companies", key="search_companies")
        cos = st.session_state.companies.copy()
        if search_co:
            s = search_co.lower()
            cos = cos[cos["Name"].str.lower().str.contains(s, na=False) | cos["Industry"].str.lower().str.contains(s, na=False) | cos["Tags"].str.lower().str.contains(s, na=False)]
        act_co = st.session_state.active_company_id

        if act_co == "new":
            st.markdown("### New company")
            cf_state_key = "new_company_cfs"
            if cf_state_key not in st.session_state: st.session_state[cf_state_key] = []
            nc1, nc2 = st.columns(2)
            with nc1:
                nc_name = st.text_input("Company name", key="nc_name"); nc_status = st.selectbox("Status", CLIENT_STATUSES, key="nc_status")
                nc_industry = st.selectbox("Industry", [""] + INDUSTRIES, key="nc_industry"); nc_phone = st.text_input("Phone", key="nc_phone")
                nc_website = st.text_input("Website", key="nc_website"); nc_referral = st.selectbox("Referral source", [""] + REFERRAL_SOURCES, key="nc_referral")
            with nc2:
                nc_billing = st.text_area("Billing address", height=100, key="nc_billing"); nc_postal = st.text_area("Postal address", height=100, key="nc_postal")
                nc_tags = st.text_input("Tags (comma separated)", key="nc_tags"); nc_notes = st.text_area("Notes", height=80, key="nc_notes")
            st.session_state[cf_state_key] = render_custom_fields_editor(st.session_state[cf_state_key], "new_co")
            s1, s2 = st.columns(2)
            if s1.button("Save company", use_container_width=True, key="save_new_company"):
                if not nc_name: st.warning("Please enter a company name.")
                else:
                    new_co = {"Company ID": create_id(), "Name": nc_name, "Status": nc_status, "Industry": nc_industry, "Website": nc_website, "Phone": nc_phone, "Billing address": nc_billing, "Postal address": nc_postal, "Referral source": nc_referral, "Notes": nc_notes, "Tags": normalize_tags(parse_tags(nc_tags)), "Custom fields": serialize_custom_fields(st.session_state[cf_state_key]), "Created": pd.Timestamp.now().strftime("%Y-%m-%d"), "Last updated": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")}
                    st.session_state.companies = pd.concat([st.session_state.companies, pd.DataFrame([new_co])], ignore_index=True)
                    save_companies(st.session_state.companies); st.session_state.active_company_id = new_co["Company ID"]
                    if cf_state_key in st.session_state: del st.session_state[cf_state_key]
                    st.rerun()
            if s2.button("Cancel", use_container_width=True, key="cancel_new_company"):
                st.session_state.active_company_id = None
                if cf_state_key in st.session_state: del st.session_state[cf_state_key]
                st.rerun()

        elif act_co is not None:
            co_row = st.session_state.companies[st.session_state.companies["Company ID"] == act_co]
            if co_row.empty: st.warning("Company not found.")
            else:
                co = co_row.iloc[0].to_dict(); sc = CLIENT_STATUS_COLOURS.get(co["Status"], "#aaaaaa")
                hc1, hc2, hc3 = st.columns([3, 1, 1])
                hc1.markdown(f"## {co['Name']}")
                hc1.markdown(f"<span style='background:{sc};color:white;padding:3px 10px;border-radius:12px;font-size:12px'>{co['Status']}</span> &nbsp; <span style='color:#888;font-size:13px'>{co['Industry']}</span>", unsafe_allow_html=True)
                edit_mode = st.session_state.get(f"edit_co_{act_co}", False)
                if hc2.button("✏️ Edit" if not edit_mode else "▲ Close edit", use_container_width=True): st.session_state[f"edit_co_{act_co}"] = not edit_mode; st.rerun()
                if hc3.button("✕ Close", use_container_width=True): st.session_state.active_company_id = None; st.rerun()
                if edit_mode:
                    cf_edit_key = f"edit_co_cfs_{act_co}"
                    if cf_edit_key not in st.session_state: st.session_state[cf_edit_key] = parse_custom_fields(co.get("Custom fields", ""))
                    with st.form("edit_company_form"):
                        ec1, ec2 = st.columns(2)
                        with ec1:
                            e_name = st.text_input("Company name", value=co["Name"]); e_status = st.selectbox("Status", CLIENT_STATUSES, index=CLIENT_STATUSES.index(co["Status"]) if co["Status"] in CLIENT_STATUSES else 0)
                            e_industry = st.selectbox("Industry", [""] + INDUSTRIES, index=([""] + INDUSTRIES).index(co["Industry"]) if co["Industry"] in INDUSTRIES else 0)
                            e_phone = st.text_input("Phone", value=co["Phone"]); e_website = st.text_input("Website", value=co["Website"])
                            e_referral = st.selectbox("Referral source", [""] + REFERRAL_SOURCES, index=([""] + REFERRAL_SOURCES).index(co["Referral source"]) if co["Referral source"] in REFERRAL_SOURCES else 0)
                        with ec2:
                            e_billing = st.text_area("Billing address", value=co["Billing address"], height=100); e_postal = st.text_area("Postal address", value=co["Postal address"], height=100)
                            e_tags = st.text_input("Tags", value=co["Tags"]); e_notes = st.text_area("Notes", value=co["Notes"], height=80)
                        updated_cfs2 = render_custom_fields_editor(st.session_state[cf_edit_key], f"edit_co_{act_co}")
                        s1, s2 = st.columns(2)
                        if s1.form_submit_button("Save", use_container_width=True):
                            cidx = st.session_state.companies[st.session_state.companies["Company ID"] == act_co].index[0]
                            for k, v in [("Name", e_name), ("Status", e_status), ("Industry", e_industry), ("Phone", e_phone), ("Website", e_website), ("Referral source", e_referral), ("Billing address", e_billing), ("Postal address", e_postal), ("Tags", normalize_tags(parse_tags(e_tags))), ("Notes", e_notes), ("Custom fields", serialize_custom_fields(updated_cfs2)), ("Last updated", pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"))]:
                                st.session_state.companies.at[cidx, k] = v
                            save_companies(st.session_state.companies); st.session_state[f"edit_co_{act_co}"] = False
                            if cf_edit_key in st.session_state: del st.session_state[cf_edit_key]
                            st.rerun()
                        if s2.form_submit_button("Delete company", use_container_width=True):
                            st.session_state.companies = st.session_state.companies[st.session_state.companies["Company ID"] != act_co]
                            save_companies(st.session_state.companies); st.session_state.active_company_id = None; st.rerun()
                else:
                    d1, d2, d3 = st.columns(3)
                    d1.markdown(f"📞 {co['Phone'] or '—'}"); d2.markdown(f"🌐 {co['Website'] or '—'}"); d3.markdown(f"🔗 {co['Referral source'] or '—'}")
                    st.markdown(f"**Billing:** {co['Billing address'] or '—'}  &nbsp;|&nbsp;  **Postal:** {co['Postal address'] or '—'}")
                    if co["Tags"]: st.markdown(" ".join(f"`{t}`" for t in parse_tags(co["Tags"])))
                    if co["Notes"]: st.info(co["Notes"])
                    cfs = parse_custom_fields(co.get("Custom fields", ""))
                    if cfs:
                        st.markdown("**Custom fields**")
                        for cf in cfs:
                            if cf.get("label"): st.markdown(f"- **{cf['label']}:** {cf.get('value','')}")

                st.markdown("---")
                lt1, lt2, lt3 = st.tabs(["📁 Projects", "📋 Estimates", "👤 Contacts"])
                with lt1:
                    linked_proj = st.session_state.projects[st.session_state.projects["Company ID"] == act_co]
                    if linked_proj.empty: st.caption("No linked projects.")
                    else:
                        for _, p in linked_proj.iterrows(): st.markdown(f"**{p['Project name']}** — {p['Stage']} — {p['Status']}")
                with lt2:
                    linked_est = st.session_state.estimates[st.session_state.estimates["Company ID"] == act_co]
                    if linked_est.empty: st.caption("No linked estimates.")
                    else:
                        for _, e in linked_est.iterrows():
                            t2 = estimate_totals(e["Estimate ID"], st.session_state.estimate_lines, st.session_state.estimate_disb, e.get("Margin %", "0"), role_rates)
                            st.markdown(f"**{e['Estimate name']}** — Total: ${t2['total']:,.2f}")
                with lt3:
                    linked_contacts = st.session_state.contacts[st.session_state.contacts["Company ID"] == act_co].copy()
                    if linked_contacts.empty: st.caption("No linked contacts.")
                    else:
                        for _, ct in linked_contacts.iterrows():
                            ctid = ct["Contact ID"]; is_primary = ct.get("Is primary", "False") == "True"
                            exp_key = f"co_ct_exp_{ctid}"; is_exp = st.session_state.get(exp_key, False)
                            r1, r2, r3, r4 = st.columns([3, 2, 2, 1])
                            r1.markdown(f"**{ct['First name']} {ct['Last name']}**" + (" ⭐" if is_primary else ""))
                            r2.caption(ct["Title"] or "No title"); r3.caption(ct["Email"] or "No email")
                            if r4.button("✏️" if not is_exp else "▲", key=f"co_ct_toggle_{ctid}"):
                                st.session_state[exp_key] = not is_exp; st.rerun()
                            if is_exp:
                                with st.form(key=f"co_ct_edit_{ctid}"):
                                    ef1, ef2 = st.columns(2)
                                    with ef1:
                                        e_first = st.text_input("First name", value=ct["First name"]); e_last = st.text_input("Last name", value=ct["Last name"])
                                        e_title = st.text_input("Title / Role", value=ct["Title"]); e_email = st.text_input("Email", value=ct["Email"])
                                    with ef2:
                                        e_phone = st.text_input("Phone", value=ct["Phone"]); e_mobile = st.text_input("Mobile", value=ct["Mobile"])
                                        e_primary = st.checkbox("Primary contact", value=is_primary)
                                        comp_opts_ct = ["(none)"] + company_names; curr_co = ct.get("Company name", "")
                                        e_company = st.selectbox("Company", comp_opts_ct, index=comp_opts_ct.index(curr_co) if curr_co in comp_opts_ct else 0)
                                    e_address = st.text_area("Address", value=ct["Address"], height=60); e_notes = st.text_area("Notes", value=ct["Notes"], height=60)
                                    e_tags = st.text_input("Tags", value=ct["Tags"])
                                    sb1, sb2, sb3 = st.columns(3)
                                    save_ct = sb1.form_submit_button("Save", use_container_width=True)
                                    remove_ct = sb2.form_submit_button("Remove from company", use_container_width=True)
                                    delete_ct = sb3.form_submit_button("Delete contact", use_container_width=True)
                                    if save_ct:
                                        new_co_row = st.session_state.companies[st.session_state.companies["Name"] == e_company]
                                        ctidx = st.session_state.contacts[st.session_state.contacts["Contact ID"] == ctid].index[0]
                                        for k, v in [("First name", e_first), ("Last name", e_last), ("Title", e_title), ("Email", e_email), ("Phone", e_phone), ("Mobile", e_mobile), ("Is primary", str(e_primary)), ("Company name", e_company if e_company != "(none)" else ""), ("Company ID", new_co_row.iloc[0]["Company ID"] if not new_co_row.empty else ""), ("Address", e_address), ("Notes", e_notes), ("Tags", normalize_tags(parse_tags(e_tags))), ("Last updated", pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"))]:
                                            st.session_state.contacts.at[ctidx, k] = v
                                        save_contacts(st.session_state.contacts); st.session_state[exp_key] = False; st.rerun()
                                    if remove_ct:
                                        ctidx = st.session_state.contacts[st.session_state.contacts["Contact ID"] == ctid].index[0]
                                        st.session_state.contacts.at[ctidx, "Company ID"] = ""; st.session_state.contacts.at[ctidx, "Company name"] = ""; st.session_state.contacts.at[ctidx, "Last updated"] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
                                        save_contacts(st.session_state.contacts); st.session_state[exp_key] = False; st.rerun()
                                    if delete_ct:
                                        st.session_state.contacts = st.session_state.contacts[st.session_state.contacts["Contact ID"] != ctid]
                                        save_contacts(st.session_state.contacts); st.rerun()
                            st.divider()
                    st.markdown("**＋ Add contact to this company**")
                    with st.form(key=f"add_ct_to_co_{act_co}"):
                        an1, an2 = st.columns(2)
                        with an1:
                            a_first = st.text_input("First name"); a_last = st.text_input("Last name")
                            a_title = st.text_input("Title / Role"); a_email = st.text_input("Email")
                        with an2:
                            a_phone = st.text_input("Phone"); a_mobile = st.text_input("Mobile")
                            a_primary = st.checkbox("Primary contact"); a_notes = st.text_area("Notes", height=60)
                        if st.form_submit_button("Add contact", use_container_width=True):
                            if not a_first or not a_last: st.warning("Please enter first and last name.")
                            else:
                                co_name = st.session_state.companies[st.session_state.companies["Company ID"] == act_co].iloc[0]["Name"]
                                new_ct2 = {"Contact ID": create_id(), "Company ID": act_co, "Company name": co_name, "First name": a_first, "Last name": a_last, "Title": a_title, "Email": a_email, "Phone": a_phone, "Mobile": a_mobile, "Address": "", "Notes": a_notes, "Tags": "", "Custom fields": "[]", "Is primary": str(a_primary), "Created": pd.Timestamp.now().strftime("%Y-%m-%d"), "Last updated": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")}
                                st.session_state.contacts = pd.concat([st.session_state.contacts, pd.DataFrame([new_ct2])], ignore_index=True)
                                save_contacts(st.session_state.contacts); st.rerun()
        else:
            if cos.empty: st.info("No companies yet. Use '＋ New company' in the sidebar.")
            else:
                cols = st.columns(3)
                for i, (_, co) in enumerate(cos.iterrows()):
                    cid = co["Company ID"]; sc = CLIENT_STATUS_COLOURS.get(co["Status"], "#aaaaaa")
                    linked_proj_count = len(st.session_state.projects[st.session_state.projects["Company ID"] == cid])
                    linked_contact_count = len(st.session_state.contacts[st.session_state.contacts["Company ID"] == cid])
                    billing = client_billing_summary(cid, st.session_state.invoices, st.session_state.invoice_lines)
                    with cols[i % 3]:
                        st.markdown(
                            f"<div style='border:1px solid #e3e1dd;border-radius:6px;padding:14px 16px;margin-bottom:6px;background:#ffffff;border-left:4px solid {sc};box-shadow:0 1px 3px rgba(0,0,0,0.04)'>"
                            f"<div style='font-weight:700;font-size:15px;margin-bottom:4px;color:#1a1a1a'>{co['Name']}</div>"
                            f"<div style='display:inline-block;padding:2px 10px;border-radius:12px;background:{sc};color:white;font-size:11px;font-weight:600;margin-bottom:6px'>{co['Status']}</div>"
                            f"<div style='font-size:11px;color:#6b6b6b'>{co['Industry'] or ''}</div>"
                            f"<div style='font-size:11px;color:#6b6b6b'>📞 {co['Phone'] or '—'} &nbsp;·&nbsp; 🌐 {co['Website'] or '—'}</div>"
                            f"<div style='font-size:11px;color:#888;margin-top:4px'>📁 {linked_proj_count} projects &nbsp;·&nbsp; 👤 {linked_contact_count} contacts</div>"
                            f"<div style='font-size:11px;color:#888'>💰 ${billing['total_invoiced']:,.0f} invoiced &nbsp;·&nbsp; ${billing['outstanding']:,.0f} outstanding</div>"
                            + (f"<div style='margin-top:6px'>{' '.join(f'<span style=background:#f0eee9;padding:2px 6px;border-radius:8px;font-size:10px>{t}</span>' for t in parse_tags(co['Tags']))}</div>" if co["Tags"] else "")
                            + "</div>", unsafe_allow_html=True)
                        if st.button("Open", key=f"open_co_{cid}", use_container_width=True):
                            st.session_state.active_company_id = cid; st.rerun()

    with tab_contacts:
        search_ct = st.text_input("Search contacts", key="search_contacts")
        cts = st.session_state.contacts.copy()
        if search_ct:
            s = search_ct.lower()
            cts = cts[cts["First name"].str.lower().str.contains(s, na=False) | cts["Last name"].str.lower().str.contains(s, na=False) | cts["Email"].str.lower().str.contains(s, na=False) | cts["Company name"].str.lower().str.contains(s, na=False)]
        act_ct = st.session_state.active_contact_id
        if act_ct == "new":
            st.markdown("### New contact")
            cf_ct_key = "new_contact_cfs"
            if cf_ct_key not in st.session_state: st.session_state[cf_ct_key] = []
            cc1, cc2 = st.columns(2)
            with cc1:
                nc_first = st.text_input("First name", key="nc_first"); nc_last = st.text_input("Last name", key="nc_last")
                nc_title = st.text_input("Title / Role", key="nc_title"); nc_email = st.text_input("Email", key="nc_email")
                nc_phone = st.text_input("Phone", key="nc_ct_phone"); nc_mobile = st.text_input("Mobile", key="nc_mobile")
            with cc2:
                comp_opts4 = ["(none)"] + company_names; nc_company = st.selectbox("Company", comp_opts4, key="nc_company")
                nc_address = st.text_area("Address", height=80, key="nc_address"); nc_tags = st.text_input("Tags (comma separated)", key="nc_ct_tags")
                nc_notes = st.text_area("Notes", height=80, key="nc_ct_notes"); nc_primary = st.checkbox("Primary contact", key="nc_primary")
            st.session_state[cf_ct_key] = render_custom_fields_editor(st.session_state[cf_ct_key], "new_ct")
            s1, s2 = st.columns(2)
            if s1.button("Save contact", use_container_width=True, key="save_new_contact"):
                if not nc_first or not nc_last: st.warning("Please enter first and last name.")
                else:
                    comp_row4 = st.session_state.companies[st.session_state.companies["Name"] == nc_company]
                    new_ct = {"Contact ID": create_id(), "Company ID": comp_row4.iloc[0]["Company ID"] if not comp_row4.empty else "", "Company name": nc_company if nc_company != "(none)" else "", "First name": nc_first, "Last name": nc_last, "Title": nc_title, "Email": nc_email, "Phone": nc_phone, "Mobile": nc_mobile, "Address": nc_address, "Notes": nc_notes, "Tags": normalize_tags(parse_tags(nc_tags)), "Custom fields": serialize_custom_fields(st.session_state[cf_ct_key]), "Is primary": str(nc_primary), "Created": pd.Timestamp.now().strftime("%Y-%m-%d"), "Last updated": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")}
                    st.session_state.contacts = pd.concat([st.session_state.contacts, pd.DataFrame([new_ct])], ignore_index=True)
                    save_contacts(st.session_state.contacts); st.session_state.active_contact_id = new_ct["Contact ID"]
                    if cf_ct_key in st.session_state: del st.session_state[cf_ct_key]
                    st.rerun()
            if s2.button("Cancel", use_container_width=True, key="cancel_new_contact"):
                st.session_state.active_contact_id = None
                if cf_ct_key in st.session_state: del st.session_state[cf_ct_key]
                st.rerun()
        elif act_ct is not None:
            ct_row = st.session_state.contacts[st.session_state.contacts["Contact ID"] == act_ct]
            if ct_row.empty: st.warning("Contact not found.")
            else:
                ct = ct_row.iloc[0].to_dict()
                hc1, hc2, hc3 = st.columns([3, 1, 1])
                hc1.markdown(f"## {ct['First name']} {ct['Last name']}"); hc1.caption(f"{ct['Title'] or ''} · {ct['Company name'] or 'No company'}")
                edit_ct = st.session_state.get(f"edit_ct_{act_ct}", False)
                if hc2.button("✏️ Edit" if not edit_ct else "▲ Close edit", key=f"edit_ct_btn_{act_ct}", use_container_width=True): st.session_state[f"edit_ct_{act_ct}"] = not edit_ct; st.rerun()
                if hc3.button("✕ Close", key=f"close_ct_btn_{act_ct}", use_container_width=True): st.session_state.active_contact_id = None; st.rerun()
                hc4, _ = st.columns([1, 3])
                if hc4.button("🗑 Delete contact", key=f"del_ct_btn_{act_ct}", use_container_width=True):
                    st.session_state.contacts = st.session_state.contacts[st.session_state.contacts["Contact ID"] != act_ct]
                    save_contacts(st.session_state.contacts); st.session_state.active_contact_id = None; st.session_state.message = "Contact deleted."; st.rerun()
                if edit_ct:
                    cf_ct_edit_key = f"edit_ct_cfs_{act_ct}"
                    if cf_ct_edit_key not in st.session_state: st.session_state[cf_ct_edit_key] = parse_custom_fields(ct.get("Custom fields", ""))
                    with st.form("edit_contact_form"):
                        ec1, ec2 = st.columns(2)
                        with ec1:
                            e_first = st.text_input("First name", value=ct["First name"]); e_last = st.text_input("Last name", value=ct["Last name"])
                            e_title = st.text_input("Title / Role", value=ct["Title"]); e_email = st.text_input("Email", value=ct["Email"])
                            e_phone = st.text_input("Phone", value=ct["Phone"]); e_mobile = st.text_input("Mobile", value=ct["Mobile"])
                        with ec2:
                            comp_opts5 = ["(none)"] + company_names; curr_co_name = ct.get("Company name", "")
                            e_company = st.selectbox("Company", comp_opts5, index=comp_opts5.index(curr_co_name) if curr_co_name in comp_opts5 else 0)
                            e_address = st.text_area("Address", value=ct["Address"], height=80); e_tags = st.text_input("Tags", value=ct["Tags"])
                            e_notes = st.text_area("Notes", value=ct["Notes"], height=80); e_primary = st.checkbox("Primary contact", value=ct.get("Is primary", "False") == "True")
                        updated_ct_cfs2 = render_custom_fields_editor(st.session_state[cf_ct_edit_key], f"edit_ct_{act_ct}")
                        s1, s2 = st.columns(2)
                        if s1.form_submit_button("Save", use_container_width=True):
                            ctidx = st.session_state.contacts[st.session_state.contacts["Contact ID"] == act_ct].index[0]
                            comp_row5 = st.session_state.companies[st.session_state.companies["Name"] == e_company]
                            for k, v in [("First name", e_first), ("Last name", e_last), ("Title", e_title), ("Email", e_email), ("Phone", e_phone), ("Mobile", e_mobile), ("Company name", e_company if e_company != "(none)" else ""), ("Company ID", comp_row5.iloc[0]["Company ID"] if not comp_row5.empty else ""), ("Address", e_address), ("Tags", normalize_tags(parse_tags(e_tags))), ("Notes", e_notes), ("Is primary", str(e_primary)), ("Custom fields", serialize_custom_fields(updated_ct_cfs2)), ("Last updated", pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"))]:
                                st.session_state.contacts.at[ctidx, k] = v
                            save_contacts(st.session_state.contacts); st.session_state[f"edit_ct_{act_ct}"] = False
                            if cf_ct_edit_key in st.session_state: del st.session_state[cf_ct_edit_key]
                            st.rerun()
                        if s2.form_submit_button("Delete contact", use_container_width=True):
                            st.session_state.contacts = st.session_state.contacts[st.session_state.contacts["Contact ID"] != act_ct]
                            save_contacts(st.session_state.contacts); st.session_state.active_contact_id = None; st.rerun()
                else:
                    d1, d2, d3 = st.columns(3)
                    d1.markdown(f"📧 {ct['Email'] or '—'}"); d2.markdown(f"📞 {ct['Phone'] or '—'}"); d3.markdown(f"📱 {ct['Mobile'] or '—'}")
                    st.markdown(f"**Company:** {ct['Company name'] or '—'}  &nbsp;|&nbsp;  **Address:** {ct['Address'] or '—'}")
                    if ct.get("Is primary") == "True": st.success("⭐ Primary contact")
                    if ct["Tags"]: st.markdown(" ".join(f"`{t}`" for t in parse_tags(ct["Tags"])))
                    if ct["Notes"]: st.info(ct["Notes"])
                    if ct.get("Email"):
                        st.markdown(f"<a href='mailto:{ct['Email']}' target='_blank'><button style='background:#3498db;color:white;border:none;padding:8px 16px;border-radius:6px;cursor:pointer;font-size:13px;margin-top:8px'>✉️ Open email draft</button></a>", unsafe_allow_html=True)
                    cfs2 = parse_custom_fields(ct.get("Custom fields", ""))
                    if cfs2:
                        st.markdown("**Custom fields**")
                        for cf2 in cfs2:
                            if cf2.get("label"): st.markdown(f"- **{cf2['label']}:** {cf2.get('value','')}")
        else:
            if cts.empty: st.info("No contacts yet. Use '＋ New contact' in the sidebar.")
            else:
                cols = st.columns(3)
                for i, (_, ct) in enumerate(cts.iterrows()):
                    ctid = ct["Contact ID"]
                    with cols[i % 3]:
                        st.markdown("<div style='border:1px solid #e3e1dd;border-radius:6px;padding:14px 16px;margin-bottom:6px;background:#ffffff;border-left:4px solid #1a1a1a;box-shadow:0 1px 3px rgba(0,0,0,0.04)'>"
                                    f"<div style='font-weight:700;font-size:15px;margin-bottom:2px;color:#1a1a1a'>{ct['First name']} {ct['Last name']}</div>"
                                    f"<div style='font-size:12px;color:#6b6b6b;margin-bottom:4px'>{ct['Title'] or ''} &nbsp;·&nbsp; {ct['Company name'] or 'No company'}</div>"
                                    f"<div style='font-size:11px;color:#6b6b6b'>📧 {ct['Email'] or '—'}</div>"
                                    f"<div style='font-size:11px;color:#6b6b6b'>📞 {ct['Phone'] or '—'}</div>"
                                    + ("⭐ Primary" if ct.get("Is primary") == "True" else "") + "</div>", unsafe_allow_html=True)
                        if st.button("Open", key=f"open_ct_{ctid}", use_container_width=True):
                            st.session_state.active_contact_id = ctid; st.rerun()

# ── RESOURCING ────────────────────────────────────────────────────────────────

elif page == "Resourcing":
    capacity = float(st.session_state.res_capacity)
    hol_set = holiday_dates_set(st.session_state.holidays)
    tab_chart, tab_plan, tab_compare, tab_team, tab_leave, tab_holidays = st.tabs(
        ["📊 Availability Chart", "✏️ Plan Hours", "📈 Projected vs Actual", "👥 Team", "🌴 Leave", "🗓 Holidays"]
    )

    # ── TAB 1: AVAILABILITY CHART ─────────────────────────────────────────────
    with tab_chart:
        nav = st.columns([0.6, 1.2, 0.6, 1.4, 0.6, 1.6, 0.6, 3])
        if nav[0].button("←", key="res_wk_prev"): st.session_state.res_week_offset -= 1; st.rerun()
        if nav[1].button("Today", key="res_today", use_container_width=True): st.session_state.res_week_offset = 0; st.rerun()
        if nav[2].button("→", key="res_wk_next"): st.session_state.res_week_offset += 1; st.rerun()

        weeks = get_week_starts(st.session_state.res_week_offset, 17, hol_set)
        first_month = weeks[0]["month"]

        if nav[4].button("←", key="res_mo_prev"): st.session_state.res_week_offset -= 4; st.rerun()
        nav[5].markdown(f"<div style='text-align:center;padding-top:6px;font-weight:600'>{first_month}</div>", unsafe_allow_html=True)
        if nav[6].button("→", key="res_mo_next"): st.session_state.res_week_offset += 4; st.rerun()

        st.markdown("")
        html = build_availability_table_html(member_names, weeks, st.session_state.resource_allocs, st.session_state.leave, hol_set, capacity)
        st.markdown(html, unsafe_allow_html=True)
        st.caption("Each cell shows **remaining available hours** (that week's capacity − projected hours). Public holidays shrink the whole week; a 🌴 marks a week where that person has personal leave, which lowers only their capacity.")

    # ── TAB 2: PLAN HOURS ─────────────────────────────────────────────────────
    with tab_plan:
        if not member_names:
            st.warning("No team members set up yet. Add team members in the Project Tracker page first.")
        else:
            pc = st.columns([2, 0.6, 2.4, 0.6, 2])
            plan_member = pc[0].selectbox("Team member", member_names, key="res_plan_member")
            if pc[1].button("◀", key="res_plan_prev"): st.session_state.res_plan_offset -= 1; st.rerun()
            if pc[3].button("▶", key="res_plan_next"): st.session_state.res_plan_offset += 1; st.rerun()
            if pc[4].button("Today", key="res_plan_today", use_container_width=True): st.session_state.res_plan_offset = 0; st.rerun()

            plan_weeks = get_week_starts(st.session_state.res_plan_offset, 8, hol_set)
            week_strs = [w["start_str"] for w in plan_weeks]
            pc[2].markdown(f"<div style='text-align:center;font-weight:600;padding-top:6px'>{plan_weeks[0]['date_label']} → {plan_weeks[-1]['date_label']}</div>", unsafe_allow_html=True)

            # Projects this member is allocated to: in the project's team, the PM, or already has hours booked
            assigned = set()
            for _, r in st.session_state.projects.iterrows():
                pmembers = parse_team_members(r.get("Team members", ""))
                if plan_member in pmembers or plan_member == (r.get("Project manager", "") or ""):
                    assigned.add(r["Project name"])
            if not st.session_state.resource_allocs.empty:
                ma = st.session_state.resource_allocs[st.session_state.resource_allocs["Team member"] == plan_member]
                assigned.update(ma["Project name"].dropna().tolist())

            all_project_names = st.session_state.projects["Project name"].dropna().unique().tolist()
            default_show = [p for p in all_project_names if p in assigned]
            proj_filter = st.multiselect(
                f"Projects for {plan_member} — defaults to their allocations; add more if needed",
                all_project_names,
                default=default_show,
                key=f"res_proj_filter_{plan_member}"
            )

            FIXED_RES_ROWS = [("", "Admin"), ("", "WIP"), ("", "Design Team Meeting"), ("", "Red Dot Projects")]
            proj_rows = [(r["Project ID"], r["Project name"]) for _, r in st.session_state.projects.iterrows() if r["Project name"] in proj_filter]
            all_rows = FIXED_RES_ROWS + proj_rows

            allocs = st.session_state.resource_allocs

            def get_planned(pname, ws):
                if allocs.empty: return 0.0
                m = allocs[(allocs["Team member"] == plan_member) & (allocs["Project name"] == pname) & (allocs["Week start"] == ws)]
                return parse_budget(m.iloc[0]["Projected hours"]) if not m.empty else 0.0

            st.markdown("---")
            hdr = st.columns([3] + [1] * 8)
            hdr[0].markdown("**Project / Task**")
            _plan_leave = leave_dates_for_member(plan_member, st.session_state.leave)
            for j, w in enumerate(plan_weeks):
                star = " 🔸" if w["is_current"] else ""
                _ld = member_week_leave_days(None, w["start"], _plan_leave, hol_set)
                marks = ""
                if w["workdays"] < 5: marks += f" 🗓{w['workdays']}d"
                if _ld > 0: marks += " 🌴"
                hdr[j + 1].markdown(f"<div style='font-size:10px;font-weight:600;text-align:center'>{w['label']}{star}<br>{w['date_label'][:5]}{marks}</div>", unsafe_allow_html=True)

            new_grid = {}
            for ri, (pid, pname) in enumerate(all_rows):
                rc = st.columns([3] + [1] * 8)
                disp = pname if len(pname) <= 28 else pname[:26] + "…"
                rc[0].markdown(f"<div style='font-size:13px;font-weight:500;padding-top:6px'>{disp}</div>", unsafe_allow_html=True)
                new_grid[ri] = {}
                for j, w in enumerate(plan_weeks):
                    ws = w["start_str"]
                    new_grid[ri][ws] = rc[j + 1].number_input(
                        "h", min_value=0.0, max_value=80.0, step=0.5, value=get_planned(pname, ws),
                        key=f"res_cell_{ri}_{ws}_{plan_member}", label_visibility="collapsed", format="%.1f"
                    )

            st.markdown("---")
            tot = st.columns([3] + [1] * 8)
            tot[0].markdown("**Total projected / Available**")
            plan_member_leave = leave_dates_for_member(plan_member, st.session_state.leave)
            for j, w in enumerate(plan_weeks):
                ws = w["start_str"]
                planned = sum(new_grid[ri][ws] for ri in new_grid)
                wcap, _, _ = member_week_capacity(w, capacity, plan_member_leave, hol_set)
                available = wcap - planned
                bg, fg = avail_color(available, wcap if wcap > 0 else capacity)
                tot[j + 1].markdown(
                    f"<div style='text-align:center;font-weight:700;padding:4px 2px'>{planned:.1f}</div>"
                    f"<div style='text-align:center;font-weight:700;background:{bg};color:{fg};border-radius:4px;padding:3px 2px;font-size:12px'>{fmt_hours(available)} free</div>",
                    unsafe_allow_html=True)

            st.markdown("")
            save_col, _ = st.columns([2, 4])
            if save_col.button("💾 Save Plan", use_container_width=True, key="res_save_plan"):
                df = st.session_state.resource_allocs.copy()
                df = df[~((df["Team member"] == plan_member) & (df["Week start"].isin(week_strs)))]
                new_entries = []
                for ri, (pid, pname) in enumerate(all_rows):
                    for ws in week_strs:
                        hrs = new_grid[ri][ws]
                        if hrs > 0:
                            new_entries.append({
                                "Alloc ID": create_id(), "Team member": plan_member,
                                "Project ID": pid, "Project name": pname, "Week start": ws,
                                "Projected hours": str(hrs), "Last updated": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
                            })
                if new_entries:
                    df = pd.concat([df, pd.DataFrame(new_entries)], ignore_index=True)
                st.session_state.resource_allocs = df
                save_resource_allocs(df)
                st.success(f"Projected hours saved for {plan_member}."); st.rerun()

    # ── TAB 3: PROJECTED VS ACTUAL ────────────────────────────────────────────
    with tab_compare:
        st.markdown("Compare **projected** hours (from planning) against **actual** hours logged in timesheets.")
        cc = st.columns([2, 0.5, 2.5, 0.5])
        cmp_member = cc[0].selectbox("Team member", ["All members"] + member_names, key="res_cmp_member")
        if cc[1].button("◀", key="res_cmp_prev"): st.session_state.res_week_offset -= 1; st.rerun()
        if cc[3].button("▶", key="res_cmp_next"): st.session_state.res_week_offset += 1; st.rerun()

        cmp_weeks = get_week_starts(st.session_state.res_week_offset, 12, hol_set)
        cc[2].markdown(f"<div style='text-align:center;font-weight:600;padding-top:6px'>{cmp_weeks[0]['date_label']} → {cmp_weeks[-1]['date_label']}</div>", unsafe_allow_html=True)

        ts = st.session_state.timesheets
        allocs = st.session_state.resource_allocs

        if cmp_member == "All members":
            rows = []
            for w in cmp_weeks:
                proj = sum(member_week_planned(m, w["start_str"], allocs) for m in member_names)
                act = sum(member_week_actual(m, w["start_str"], ts) for m in member_names)
                rows.append({"Week": w["label"], "Projected": round(proj, 1), "Actual": round(act, 1), "Variance": round(act - proj, 1)})
            cmp_df = pd.DataFrame(rows)
        else:
            rows = []
            for w in cmp_weeks:
                proj = member_week_planned(cmp_member, w["start_str"], allocs)
                act = member_week_actual(cmp_member, w["start_str"], ts)
                rows.append({"Week": w["label"], "Projected": round(proj, 1), "Actual": round(act, 1), "Variance": round(act - proj, 1)})
            cmp_df = pd.DataFrame(rows)

        if cmp_df[["Projected", "Actual"]].to_numpy().sum() == 0:
            st.info("No projected or actual hours in this window yet.")
        else:
            long_df = cmp_df.melt(id_vars="Week", value_vars=["Projected", "Actual"], var_name="Type", value_name="Hours")
            week_order = cmp_df["Week"].tolist()
            bar = alt.Chart(long_df).mark_bar().encode(
                x=alt.X("Week:N", sort=week_order, title="", axis=alt.Axis(labelAngle=0, labelFontSize=11)),
                xOffset=alt.XOffset("Type:N"),
                y=alt.Y("Hours:Q", title="Hours"),
                color=alt.Color("Type:N", scale=alt.Scale(domain=["Projected", "Actual"], range=["#3498db", "#2ecc71"]),
                                legend=alt.Legend(title="", orient="top")),
                tooltip=[alt.Tooltip("Week:N"), alt.Tooltip("Type:N"), alt.Tooltip("Hours:Q")],
            ).properties(width="container", height=320, background="transparent").configure_view(strokeWidth=0).configure_axis(labelColor="#2c2c2c", titleColor="#2c2c2c", gridColor="#e3e1dd")
            st.altair_chart(bar, use_container_width=True)

            def style_variance(val):
                try: v = float(val)
                except: return ""
                if v > 0: return "background-color:#fdecea;color:#c0392b"   # over plan
                if v < 0: return "background-color:#eafaf1;color:#1e8449"   # under plan
                return ""
            st.markdown("**Detail**")
            st.dataframe(cmp_df.style.map(style_variance, subset=["Variance"]), use_container_width=True, hide_index=True)
            st.caption("Variance = Actual − Projected. Positive (red) means more hours logged than planned; negative (green) means under plan.")

    # ── TAB 4: TEAM ───────────────────────────────────────────────────────────
    with tab_team:
        st.markdown("Manage team members and roles. A member's role sets their default hourly rate used in timesheets and fee estimates.")
        tc1, tc2 = st.columns([1, 1])
        with tc1:
            st.markdown("**Add a team member**")
            with st.form("team_member_form"):
                nm = st.text_input("Name"); nr = st.selectbox("Role", list(DEFAULT_ROLES.keys()))
                if st.form_submit_button("Add team member", use_container_width=True):
                    name = nm.strip()
                    if not name: st.warning("Please enter a name.")
                    elif name in st.session_state.members_df["Team member"].tolist(): st.warning("Already exists.")
                    else:
                        st.session_state.members_df = pd.concat([st.session_state.members_df, pd.DataFrame([{"Team member": name, "Role": nr}])], ignore_index=True)
                        save_team_members_df(st.session_state.members_df); st.rerun()
        with tc2:
            st.markdown("**Team members**")
            if st.session_state.members_df.empty:
                st.caption("No team members yet.")
            else:
                for _, mem in st.session_state.members_df.iterrows():
                    mname, mrole = mem["Team member"], mem["Role"]; is_exp = st.session_state.expanded_member == mname
                    mc1, mc2, mc3 = st.columns([3, 2, 1]); mc1.markdown(f"**{mname}**"); mc2.caption(mrole or "—")
                    if mc3.button("✏️" if not is_exp else "▲", key=f"edit_mem_{mname}"): st.session_state.expanded_member = None if is_exp else mname; st.rerun()
                    if is_exp:
                        with st.form(key=f"edit_member_form_{mname}"):
                            new_name = st.text_input("Name", value=mname)
                            new_role = st.selectbox("Role", list(DEFAULT_ROLES.keys()), index=list(DEFAULT_ROLES.keys()).index(mrole) if mrole in DEFAULT_ROLES else 0)
                            s1, s2 = st.columns(2)
                            if s1.form_submit_button("Save", use_container_width=True):
                                midx = st.session_state.members_df[st.session_state.members_df["Team member"] == mname].index[0]
                                st.session_state.members_df.at[midx, "Team member"] = new_name.strip(); st.session_state.members_df.at[midx, "Role"] = new_role
                                save_team_members_df(st.session_state.members_df); st.session_state.expanded_member = None; st.rerun()
                            if s2.form_submit_button("Delete", use_container_width=True):
                                st.session_state.members_df = st.session_state.members_df[st.session_state.members_df["Team member"] != mname]
                                save_team_members_df(st.session_state.members_df); st.session_state.expanded_member = None; st.rerun()

        st.markdown("---")
        st.markdown("**Role rates** — default hourly rate per role")
        with st.form("role_rates_form"):
            rr = list(DEFAULT_ROLES.keys())
            current_rates = get_role_rates(st.session_state.roles_df)
            rate_inputs = {}
            for chunk_start in range(0, len(rr), 4):
                chunk = rr[chunk_start:chunk_start + 4]
                rcols = st.columns(4)
                for j, role in enumerate(chunk):
                    rate_inputs[role] = rcols[j].number_input(
                        role, min_value=0.0, step=5.0,
                        value=float(current_rates.get(role, DEFAULT_ROLES.get(role, 0.0))),
                        key=f"role_rate_{role}")
            if st.form_submit_button("Save rates", use_container_width=True):
                st.session_state.roles_df = pd.DataFrame([{"Role": r, "Hourly rate": str(v)} for r, v in rate_inputs.items()])
                save_roles(st.session_state.roles_df); st.success("Role rates updated."); st.rerun()

    # ── TAB 5: LEAVE (per-person) ─────────────────────────────────────────────
    with tab_leave:
        if not member_names:
            st.warning("No team members set up yet.")
        else:
            st.markdown("Record individual leave. Leave only reduces **that person's** capacity for the affected weeks — the rest of the team is unaffected.")
            lc1, lc2 = st.columns([1, 1])
            with lc1:
                st.markdown("**Book leave**")
                with st.form("add_leave_form"):
                    lv_member = st.selectbox("Team member", member_names, key="lv_member")
                    lv_from = st.date_input("From", value=pd.Timestamp.now().date(), key="lv_from")
                    lv_to = st.date_input("To", value=pd.Timestamp.now().date(), key="lv_to")
                    lv_type = st.selectbox("Type", LEAVE_TYPES, key="lv_type")
                    lv_notes = st.text_input("Notes (optional)", key="lv_notes")
                    if st.form_submit_button("Book leave", use_container_width=True):
                        if lv_to < lv_from:
                            st.warning("'To' date is before 'From' date.")
                        else:
                            existing = leave_dates_for_member(lv_member, st.session_state.leave)
                            new_rows = []
                            d = pd.Timestamp(lv_from)
                            end = pd.Timestamp(lv_to)
                            while d <= end:
                                if d.weekday() < 5 and d.date() not in existing:   # weekdays only, no dupes
                                    new_rows.append({"Leave ID": create_id(), "Team member": lv_member,
                                                     "Date": d.strftime("%Y-%m-%d"), "Type": lv_type, "Notes": lv_notes})
                                d += pd.Timedelta(days=1)
                            if new_rows:
                                st.session_state.leave = pd.concat([st.session_state.leave, pd.DataFrame(new_rows)], ignore_index=True)
                                save_leave(st.session_state.leave)
                                st.success(f"Booked {len(new_rows)} day(s) of leave for {lv_member}."); st.rerun()
                            else:
                                st.info("No new weekdays to add (weekends skipped / already booked).")
            with lc2:
                st.markdown("**Upcoming leave**")
                view_member = st.selectbox("Show", ["All members"] + member_names, key="lv_view_member")
                lv_df = st.session_state.leave.copy()
                if view_member != "All members":
                    lv_df = lv_df[lv_df["Team member"] == view_member]
                if lv_df.empty:
                    st.caption("No leave booked.")
                else:
                    lv_df["_dt"] = pd.to_datetime(lv_df["Date"], errors="coerce")
                    today = pd.Timestamp.now().normalize()
                    lv_df = lv_df[lv_df["_dt"] >= today - pd.Timedelta(days=7)].sort_values("_dt")
                    # Group consecutive days per member+type into ranges for a tidy display
                    shown = 0
                    for (mem, typ), grp in lv_df.groupby(["Team member", "Type"]):
                        dates = sorted(grp["_dt"].dropna().tolist())
                        # collapse into contiguous runs
                        runs = []
                        run = [dates[0]] if dates else []
                        for prev, cur_d in zip(dates, dates[1:]):
                            if (cur_d - prev).days <= 3:   # within a few days (skip weekends)
                                run.append(cur_d)
                            else:
                                runs.append(run); run = [cur_d]
                        if run: runs.append(run)
                        for r in runs:
                            shown += 1
                            label = r[0].strftime("%d %b") if len(r) == 1 else f"{r[0].strftime('%d %b')} – {r[-1].strftime('%d %b %Y')}"
                            rc = st.columns([3, 2, 1])
                            rc[0].markdown(f"**{mem}**")
                            rc[1].caption(f"{label} · {typ} ({len(r)}d)")
                            if rc[2].button("🗑", key=f"del_leave_{mem}_{typ}_{r[0].strftime('%Y%m%d')}"):
                                drop_strs = [d.strftime("%Y-%m-%d") for d in r]
                                st.session_state.leave = st.session_state.leave[
                                    ~((st.session_state.leave["Team member"] == mem) &
                                      (st.session_state.leave["Type"] == typ) &
                                      (st.session_state.leave["Date"].isin(drop_strs)))]
                                save_leave(st.session_state.leave); st.rerun()
                    if shown == 0:
                        st.caption("No upcoming leave.")

    # ── TAB 5: HOLIDAYS ───────────────────────────────────────────────────────
    with tab_holidays:
        st.markdown("Public holidays reduce that week's workdays for **everyone**, scaling the whole team's capacity down for the affected week.")

        st.markdown("**Load a full year of NZ public holidays**")
        yc1, yc2, _ = st.columns([1, 1, 3])
        year_choice = yc1.number_input("Year", min_value=2022, max_value=2035, value=pd.Timestamp.now().year, step=1, key="hol_year")
        if yc2.button("＋ Add year", use_container_width=True, key="add_year_hols"):
            existing_dates = set(st.session_state.holidays["Date"].tolist())
            new_rows = [{"Date": d, "Name": n} for d, n in nz_public_holidays(int(year_choice)) if d not in existing_dates]
            if new_rows:
                st.session_state.holidays = pd.concat([st.session_state.holidays, pd.DataFrame(new_rows)], ignore_index=True)
                save_holidays(st.session_state.holidays)
                st.success(f"Added {len(new_rows)} public holiday(s) for {int(year_choice)}."); st.rerun()
            else:
                st.info(f"All {int(year_choice)} public holidays are already in the list.")
        st.caption("Generates the standard NZ public holidays (incl. computed Easter, King's Birthday, Labour Day and official Matariki dates). Edit or delete any below — e.g. add regional anniversary days.")
        st.markdown("---")

        hc1, hc2 = st.columns([1, 1])
        with hc1:
            st.markdown("**Add a single holiday**")
            with st.form("add_holiday_form"):
                h_date = st.date_input("Date", value=pd.Timestamp.now().date())
                h_name = st.text_input("Name", placeholder="e.g. Wellington Anniversary")
                if st.form_submit_button("Add holiday", use_container_width=True):
                    ds = h_date.strftime("%Y-%m-%d")
                    if not st.session_state.holidays[st.session_state.holidays["Date"] == ds].empty:
                        st.warning("A holiday already exists on that date.")
                    else:
                        st.session_state.holidays = pd.concat(
                            [st.session_state.holidays, pd.DataFrame([{"Date": ds, "Name": h_name or "Holiday"}])],
                            ignore_index=True)
                        save_holidays(st.session_state.holidays); st.rerun()
        with hc2:
            st.markdown("**Scheduled holidays**")
            hol_df = st.session_state.holidays.copy()
            if hol_df.empty:
                st.caption("No holidays added yet.")
            else:
                hol_df["_dt"] = pd.to_datetime(hol_df["Date"], errors="coerce")
                hol_df = hol_df.sort_values("_dt")
                today = pd.Timestamp.now().normalize()
                hol_df = hol_df[hol_df["_dt"] >= today - pd.Timedelta(days=30)]
                if hol_df.empty:
                    st.caption("No upcoming holidays. Older holidays are hidden.")
                for _, h in hol_df.iterrows():
                    dt = h["_dt"]
                    rcols = st.columns([2, 3, 1])
                    rcols[0].markdown(f"**{dt.strftime('%d %b %Y') if not pd.isna(dt) else h['Date']}**")
                    rcols[1].caption(h["Name"])
                    if rcols[2].button("🗑", key=f"del_hol_{h['Date']}_{h['Name'][:6]}"):
                        st.session_state.holidays = st.session_state.holidays[
                            ~((st.session_state.holidays["Date"] == h["Date"]) & (st.session_state.holidays["Name"] == h["Name"]))]
                        save_holidays(st.session_state.holidays); st.rerun()

# ── footer ────────────────────────────────────────────────────────────────────

if st.session_state.message:
    st.success(st.session_state.message); st.session_state.message = ""

st.markdown("---")
st.download_button("⬇️ Download project tracker CSV", data=st.session_state.projects.to_csv(index=False).encode("utf-8"), file_name="fitout_projects.csv", mime="text/csv")