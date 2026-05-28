from pathlib import Path
import re
import uuid
import json

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
COMPLIANCE_TASKS = [
    "Fire safety sign-off", "Electrical certificate", "Plumbing certificate",
    "OHS inspection", "Code compliance certificate",
]
COLUMNS = [
    "Project ID", "Project name", "Client", "Company ID", "Location", "Project manager",
    "Start date", "Target completion", "Stage", "Status", "Budget", "Fee",
    "Phase fees", "Weekly hours allocated", "Member hours allocation",
    "Phase schedule", "Milestones", "Team members", "Compliance checklist",
    "Notes", "Last updated",
]
TASK_COLUMNS = ["Task ID", "Project ID", "Project name", "Task name", "Team", "Assigned to", "Status", "Notes", "Last updated"]
TIMESHEET_COLUMNS = ["Entry ID", "Project ID", "Project name", "Phase", "Team member", "Role", "Date", "Hours", "Rate", "Notes"]
ESTIMATE_COLUMNS = ["Estimate ID", "Estimate name", "Client", "Company ID", "Project ID", "Project name", "Margin %", "Notes", "Created", "Last updated"]
ESTIMATE_LINE_COLUMNS = ["Line ID", "Estimate ID", "Phase", "Role", "Hours", "Rate"]
ESTIMATE_DISB_COLUMNS = ["Disb ID", "Estimate ID", "Description", "Type", "Value"]
COMPANY_COLUMNS = [
    "Company ID", "Name", "Status", "Industry", "Website", "Phone",
    "Billing address", "Postal address", "Referral source",
    "Notes", "Tags", "Custom fields", "Created", "Last updated",
]
CONTACT_COLUMNS = [
    "Contact ID", "Company ID", "Company name", "First name", "Last name",
    "Title", "Email", "Phone", "Mobile", "Address",
    "Notes", "Tags", "Custom fields", "Is primary", "Created", "Last updated",
]

TASK_TEAMS = ["Design", "Project Management"]
TASK_STATUSES = ["Not started", "Ongoing", "Completed"]
TASK_STATUS_COLOURS = {"Not started": "#aaaaaa", "Ongoing": "#f39c12", "Completed": "#2ecc71"}
CLIENT_STATUSES = ["Active", "Prospect", "Lead", "Inactive"]
CLIENT_STATUS_COLOURS = {"Active": "#2ecc71", "Prospect": "#3498db", "Lead": "#f39c12", "Inactive": "#aaaaaa"}
INDUSTRIES = ["Architecture", "Interior Design", "Construction", "Engineering", "Property Development",
              "Retail", "Hospitality", "Education", "Healthcare", "Government", "Other"]
REFERRAL_SOURCES = ["Word of mouth", "Website", "Social media", "Returning client", "Referral", "Directory", "Other"]

DEFAULT_ROLES = {
    "Technician": 85.0, "Graduate": 95.0, "Intermediate Designer": 120.0,
    "Senior Designer": 150.0, "Director": 200.0,
}

# ── helpers ───────────────────────────────────────────────────────────────────

def parse_budget(value):
    if pd.isna(value) or value == "": return 0.0
    try: return float(str(value).replace(",", "").replace("$", "").strip())
    except ValueError: return 0.0

def format_budget(value): return f"${parse_budget(value):,.2f}"

def parse_weekly_hours(value):
    if pd.isna(value) or value == "": return 0.0
    try: return float(str(value).replace(",", "").strip())
    except ValueError: return 0.0

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

def stage_progress(stage):
    return int(((STAGES.index(stage) + 1) / len(STAGES)) * 100) if stage in STAGES else 0

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

def normalize_phase_schedule(value):
    return "\n".join(l.strip() for l in str(value).splitlines() if l.strip())

def parse_date(value, fallback=None):
    p = pd.to_datetime(value, errors="coerce")
    return fallback if pd.isna(p) else p.date()

def create_id(): return uuid.uuid4().hex[:8]

def parse_custom_fields(value):
    if not value or pd.isna(value) or value == "": return []
    try: return json.loads(value)
    except Exception: return []

def serialize_custom_fields(fields): return json.dumps(fields)

def parse_tags(value):
    if not value or pd.isna(value): return []
    return [t.strip() for t in str(value).split(",") if t.strip()]

def normalize_tags(tags): return ", ".join(sorted(set(tags)))

# ── data loaders ──────────────────────────────────────────────────────────────

def ensure_file(path, columns):
    if not path.exists():
        pd.DataFrame(columns=columns).to_csv(path, index=False)

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
def load_timesheets(): return load_df(TIMESHEETS_FILE, TIMESHEET_COLUMNS)
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
    return pd.concat([df, pd.DataFrame([data])], ignore_index=True)

# ── fee helpers ───────────────────────────────────────────────────────────────

def estimate_totals(est_id, lines_df, disb_df, margin_pct, role_rates):
    lines = lines_df[lines_df["Estimate ID"] == est_id]
    hours_cost = sum(parse_budget(r["Hours"]) * (parse_budget(r["Rate"]) if r["Rate"] else role_rates.get(r["Role"], 0.0))
                     for _, r in lines.iterrows())
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
    return round(sum(parse_budget(e["Hours"]) * (parse_budget(e["Rate"]) if e["Rate"] else role_rates.get(e["Role"], 0.0))
                     for _, e in entries.iterrows()), 2)

def project_hours_logged(project_id, timesheets_df):
    entries = timesheets_df[timesheets_df["Project ID"] == project_id]
    return round(sum(parse_budget(e["Hours"]) for _, e in entries.iterrows()), 1)

def generate_pdf_html(est_row, lines_df, disb_df, totals, role_rates):
    est_id = est_row["Estimate ID"]
    roles = list(DEFAULT_ROLES.keys())
    phase_rows = ""
    for phase in STAGES:
        phase_lines = lines_df[(lines_df["Estimate ID"] == est_id) & (lines_df["Phase"] == phase)]
        if phase_lines.empty: continue
        phase_total = 0.0
        role_cells = ""
        for role in roles:
            rl = phase_lines[phase_lines["Role"] == role]
            hrs = rl["Hours"].apply(parse_budget).sum()
            cost = hrs * role_rates.get(role, 0.0)
            phase_total += cost
            role_cells += f"<td style='text-align:center;padding:4px 8px'>{hrs if hrs>0 else ''}</td><td style='text-align:right;padding:4px 8px'>{'${:,.0f}'.format(cost) if cost>0 else ''}</td>"
        phase_rows += f"<tr><td style='padding:4px 8px;font-weight:600'>{phase}</td>{role_cells}<td style='text-align:right;padding:4px 8px;font-weight:700'>${phase_total:,.2f}</td></tr>"
    role_headers = "".join(f"<th colspan='2' style='padding:6px 8px;background:#2c3e50;color:white'>{r}</th>" for r in roles)
    disbs = disb_df[disb_df["Estimate ID"] == est_id]
    disb_rows = "".join(
        f"<tr><td style='padding:4px 8px'>{d['Description']}</td><td style='padding:4px 8px'>{d['Type']}</td>"
        f"<td style='text-align:right;padding:4px 8px'>{'${:,.2f}'.format(parse_budget(d['Value'])) if d['Type']=='Fixed ($)' else d['Value']+'%'}</td></tr>"
        for _, d in disbs.iterrows()
    )
    margin_pct = parse_budget(est_row.get("Margin %", "0"))
    return f"""<html><head><style>body{{font-family:Arial,sans-serif;font-size:12px;color:#222;margin:40px}}
    h1,h2{{color:#2c3e50}}h2{{border-bottom:1px solid #ccc;padding-bottom:4px}}
    table{{border-collapse:collapse;width:100%;margin-bottom:20px}}td,th{{border:1px solid #ddd}}
    .summary td{{padding:6px 12px}}.total{{font-size:16px;font-weight:700;color:#2c3e50}}</style></head><body>
    <h1>Fee Estimate — {est_row['Estimate name']}</h1>
    <p><strong>Client:</strong> {est_row['Client']} &nbsp;|&nbsp; <strong>Project:</strong> {est_row.get('Project name','—')} &nbsp;|&nbsp; <strong>Date:</strong> {est_row.get('Created','')}</p>
    <h2>Phase & Role Breakdown</h2><table><thead><tr><th style='padding:6px 8px;background:#2c3e50;color:white'>Phase</th>
    {role_headers}<th style='padding:6px 8px;background:#2c3e50;color:white'>Phase Total</th></tr>
    <tr style='background:#ecf0f1'><td></td>{"".join(f"<td style='text-align:center;font-size:10px;padding:4px'>Hrs</td><td style='text-align:center;font-size:10px;padding:4px'>Cost</td>" for _ in roles)}<td></td></tr>
    </thead><tbody>{phase_rows}</tbody></table>
    <h2>Disbursements</h2><table><thead><tr><th style='padding:6px 8px;background:#2c3e50;color:white'>Description</th>
    <th style='padding:6px 8px;background:#2c3e50;color:white'>Type</th><th style='padding:6px 8px;background:#2c3e50;color:white'>Value</th></tr></thead>
    <tbody>{disb_rows or "<tr><td colspan='3' style='padding:6px 8px;color:#888'>No disbursements</td></tr>"}</tbody></table>
    <h2>Summary</h2><table class='summary' style='width:350px'>
    <tr><td>Hours subtotal</td><td style='text-align:right'>${totals['hours_cost']:,.2f}</td></tr>
    <tr><td>Fixed disbursements</td><td style='text-align:right'>${totals['fixed_disb']:,.2f}</td></tr>
    <tr><td>% disbursements</td><td style='text-align:right'>${totals['pct_disb_amt']:,.2f}</td></tr>
    <tr><td>Subtotal</td><td style='text-align:right'>${totals['subtotal']:,.2f}</td></tr>
    <tr><td>Margin ({margin_pct:.1f}%)</td><td style='text-align:right'>${totals['margin_amt']:,.2f}</td></tr>
    <tr class='total'><td>TOTAL FEE</td><td style='text-align:right'>${totals['total']:,.2f}</td></tr>
    </table></body></html>"""

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
        assigned = round(data["Assigned hours"], 1)
        available = round(max(0.0, weekly_capacity - assigned), 1)
        records.append({"Team member": m, "Projects assigned": data["Projects assigned"],
                        "Assigned hours": assigned, "Available hours": available,
                        "Status": "Swamped" if available < 10 else ("Getting full" if available < 20 else "OK")})
    return pd.DataFrame(records).sort_values(["Assigned hours", "Team member"], ascending=[False, True])

def style_workload_table(row):
    a = row["Available hours"]
    c = "#ff9999" if a < 10 else ("#ffcc99" if a < 20 else "#d4f4d4")
    return [f"background-color: {c}"] * len(row)

# ── custom field UI ───────────────────────────────────────────────────────────

def render_custom_fields_editor(existing_fields, key_prefix):
    """Render editable custom fields. Returns updated list."""
    st.markdown("**Custom fields**")
    updated = []
    for i, cf in enumerate(existing_fields):
        c1, c2, c3, c4 = st.columns([2, 2, 3, 1])
        label = c1.text_input("Label", value=cf.get("label", ""), key=f"{key_prefix}_cf_label_{i}", label_visibility="collapsed", placeholder="Label")
        ftype = c2.selectbox("Type", ["Text", "Dropdown"], index=0 if cf.get("type", "Text") == "Text" else 1,
                             key=f"{key_prefix}_cf_type_{i}", label_visibility="collapsed")
        if ftype == "Text":
            val = c3.text_input("Value", value=cf.get("value", ""), key=f"{key_prefix}_cf_val_{i}", label_visibility="collapsed", placeholder="Value")
            opts = cf.get("options", [])
        else:
            opts_str = c3.text_input("Options (comma separated)", value=", ".join(cf.get("options", [])),
                                     key=f"{key_prefix}_cf_opts_{i}", label_visibility="collapsed", placeholder="Option 1, Option 2")
            opts = [o.strip() for o in opts_str.split(",") if o.strip()]
            val = cf.get("value", opts[0] if opts else "")
        remove = c4.checkbox("✕", key=f"{key_prefix}_cf_remove_{i}")
        if not remove:
            updated.append({"label": label, "type": ftype, "value": val, "options": opts})
    if st.button("＋ Add custom field", key=f"{key_prefix}_add_cf"):
        updated.append({"label": "", "type": "Text", "value": "", "options": []})
        st.rerun()
    return updated

# ── dialogs ───────────────────────────────────────────────────────────────────

@st.dialog("Project Tasks", width="large")
def show_task_popup(proj_name):
    st.subheader(proj_name)
    proj_tasks = st.session_state.tasks[st.session_state.tasks["Project name"] == proj_name].copy()
    for status in TASK_STATUSES:
        status_tasks = proj_tasks[proj_tasks["Status"] == status]
        colour = TASK_STATUS_COLOURS[status]
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
                new_assigned = st.multiselect("Assignee", st.session_state.members_df["Team member"].tolist(),
                    default=assigned, key=f"popup_assign_{tid}", label_visibility="collapsed")
            with c3:
                new_status = st.selectbox("Status", TASK_STATUSES,
                    index=TASK_STATUSES.index(task["Status"]) if task["Status"] in TASK_STATUSES else 0,
                    key=f"popup_status_{tid}", label_visibility="collapsed")
            if new_assigned != assigned or new_status != task["Status"]:
                idx = st.session_state.tasks[st.session_state.tasks["Task ID"] == tid].index[0]
                st.session_state.tasks.at[idx, "Assigned to"] = "; ".join(new_assigned)
                st.session_state.tasks.at[idx, "Status"] = new_status
                st.session_state.tasks.at[idx, "Last updated"] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
                save_tasks(st.session_state.tasks)
            st.divider()
    st.markdown("### ＋ Add a task")
    with st.form(key=f"popup_new_task_{proj_name}"):
        nt_name = st.text_input("Task name")
        nt_team = st.selectbox("Team", TASK_TEAMS)
        nt_assigned = st.multiselect("Assigned to", st.session_state.members_df["Team member"].tolist())
        nt_status = st.selectbox("Status", TASK_STATUSES)
        nt_notes = st.text_area("Notes", height=80)
        if st.form_submit_button("Create task", use_container_width=True):
            if not nt_name: st.warning("Please enter a task name.")
            else:
                proj_row = st.session_state.projects[st.session_state.projects["Project name"] == proj_name]
                pid = proj_row.iloc[0]["Project ID"] if not proj_row.empty else ""
                st.session_state.tasks = add_or_update_task({
                    "Task ID": "", "Project ID": pid, "Project name": proj_name,
                    "Task name": nt_name, "Team": nt_team,
                    "Assigned to": "; ".join(nt_assigned), "Status": nt_status, "Notes": nt_notes,
                }, st.session_state.tasks)
                save_tasks(st.session_state.tasks)
                st.rerun()


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
            lh_role = st.selectbox("Role", list(DEFAULT_ROLES.keys()),
                index=list(DEFAULT_ROLES.keys()).index(member_role) if member_role in DEFAULT_ROLES else 0)
            lh_rate = st.number_input("Hourly rate ($)", min_value=0.0, value=role_rates.get(lh_role, 0.0), step=5.0)
            lh_hours = st.number_input("Hours", min_value=0.0, step=0.5, value=0.0)
        lh_notes = st.text_area("Notes", height=80)
        if st.form_submit_button("Save entry", use_container_width=True):
            if not lh_member or lh_hours <= 0: st.warning("Please select a team member and enter hours.")
            else:
                st.session_state.timesheets = add_timesheet_entry({
                    "Project ID": proj_id, "Project name": proj_name, "Phase": lh_phase,
                    "Team member": lh_member, "Role": lh_role, "Date": str(lh_date),
                    "Hours": str(lh_hours), "Rate": str(lh_rate), "Notes": lh_notes,
                }, st.session_state.timesheets)
                save_timesheets(st.session_state.timesheets)
                st.success("Hours logged!")
                st.rerun()
    proj_entries = st.session_state.timesheets[st.session_state.timesheets["Project ID"] == proj_id].copy()
    if not proj_entries.empty:
        st.markdown("---")
        proj_entries["Cost"] = proj_entries.apply(lambda r: round(parse_budget(r["Hours"]) * parse_budget(r["Rate"]), 2), axis=1)
        st.markdown(f"**Total: {proj_entries['Hours'].apply(parse_budget).sum():.1f} hrs &nbsp;|&nbsp; ${proj_entries['Cost'].sum():,.2f}**")
        if "expanded_ts_entry" not in st.session_state: st.session_state.expanded_ts_entry = None
        for _, e in proj_entries.sort_values("Date", ascending=False).iterrows():
            eid = e["Entry ID"]
            is_exp = st.session_state.expanded_ts_entry == eid
            c1, c2, c3, c4, c5 = st.columns([2, 1, 1, 1, 1])
            c1.markdown(f"**{e['Team member']}** — {e['Phase'] or 'No phase'}"); c1.caption(e["Notes"] or "")
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
                        for k, v in [("Team member", e_member), ("Phase", e_phase), ("Role", e_role),
                                     ("Date", str(e_date)), ("Hours", str(e_hours)), ("Rate", str(e_rate)), ("Notes", e_notes)]:
                            st.session_state.timesheets.at[idx, k] = v
                        save_timesheets(st.session_state.timesheets)
                        st.session_state.expanded_ts_entry = None; st.rerun()
            st.divider()

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
        cards.append({"Project name": row["Project name"], "Project ID": proj_id,
                      "Client": row["Client"], "Stage": row["Stage"], "Status": row["Status"],
                      "phase_info": phase_info, "min_upcoming": min_upcoming if min_upcoming is not None else 9999,
                      "fee": fee, "consumed": consumed, "hours": hours, "pct": pct})
    cards.sort(key=lambda c: c["min_upcoming"])
    if not cards: st.info("No projects to display."); return

    cols = st.columns(3)
    for i, card in enumerate(cards):
        proj, proj_id = card["Project name"], card["Project ID"]
        sc = STATUS_COLOURS.get(card["Status"], "#cccccc")
        pct = card["pct"]
        fc = "#2ecc71" if pct < 75 else ("#f39c12" if pct <= 90 else "#e74c3c")
        dots = "".join(
            "<div style='display:flex;flex-direction:column;align-items:center;gap:2px;min-width:60px'>"
            f"<div style='width:18px;height:18px;border-radius:50%;background:{phase_colour(p['days'])};border:{'2px solid #333' if p['stage']==card['Stage'] else '2px solid transparent'}'></div>"
            f"<span style='font-size:9px;color:#555;text-align:center'>{p['stage'][:6]}</span>"
            f"<span style='font-size:9px;color:#333;font-weight:500'>{days_label(p['days'])}</span></div>"
            for p in card["phase_info"]
        )
        fee_bar = (
            f"<div style='margin-top:10px'><div style='font-size:11px;color:#555;margin-bottom:3px'>Fee: ${card['consumed']:,.0f} of ${card['fee']:,.0f} used ({pct}%) &nbsp;·&nbsp; {card['hours']} hrs logged</div>"
            f"<div style='background:#e0e0e0;border-radius:6px;height:8px;overflow:hidden'><div style='width:{min(pct,100)}%;height:100%;background:{fc};border-radius:6px'></div></div></div>"
        ) if card["fee"] > 0 else ""
        html = (f"<div style='border:1px solid #ddd;border-radius:10px;padding:14px 16px;margin-bottom:6px;background:#fafafa;border-left:5px solid {sc}'>"
                f"<div style='font-weight:700;font-size:15px;margin-bottom:2px'>{proj}</div>"
                f"<div style='font-size:12px;color:#666;margin-bottom:8px'>{card['Client']} &nbsp;&middot;&nbsp;<span style='color:{sc};font-weight:600'>{card['Status']}</span></div>"
                f"<div style='font-size:11px;color:#888;margin-bottom:10px'>Current stage: <strong>{card['Stage']}</strong></div>"
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
                        st.session_state.projects.at[pidx, "Stage"] = ns
                        st.session_state.projects.at[pidx, "Status"] = nst
                        st.session_state.projects.at[pidx, "Last updated"] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
                        save_projects(st.session_state.projects)
                        st.session_state.expanded_card = None; st.session_state.message = f"Updated stage for '{proj}'."; st.rerun()

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
st.title("🏢 STACK Project Cloud")
st.markdown("Track fitout projects from concept through to code compliance.")

for key, loader in [("projects", load_projects), ("members_df", load_team_members),
                    ("roles_df", load_roles), ("tasks", load_tasks), ("timesheets", load_timesheets),
                    ("estimates", load_estimates), ("estimate_lines", load_estimate_lines),
                    ("estimate_disb", load_estimate_disb), ("companies", load_companies),
                    ("contacts", load_contacts)]:
    if key not in st.session_state: st.session_state[key] = loader()

for key, default in [("message", ""), ("expanded_card", None), ("show_add_project", False),
                     ("show_team_management", False), ("selected_project", ""), ("selectbox_key", 0),
                     ("expanded_task", None), ("expanded_ts_entry", None), ("expanded_member", None),
                     ("active_estimate_id", None), ("active_company_id", None), ("active_contact_id", None),
                     ("client_tab", "Companies")]:
    if key not in st.session_state: st.session_state[key] = default

member_names = st.session_state.members_df["Team member"].tolist()
role_rates = get_role_rates(st.session_state.roles_df)
company_names = st.session_state.companies["Name"].dropna().tolist()

# ── sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    page = st.selectbox("Page", ["Project Tracker", "Task Tracker", "Timesheets", "Fee Estimator", "Clients"])
    if page == "Project Tracker":
        st.header("Filters")
        selected_stages = [s for s in st.multiselect("Stage", ["All"] + STAGES, default=["All"]) if s != "All"]
        selected_status = [s for s in st.multiselect("Status", ["All"] + STATUSES, default=["All"]) if s != "All"]
        search_query = st.text_input("Search")
        st.markdown("---"); st.write("**Insights**")
        n = len(st.session_state.projects)
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
        st.header("Timesheet filters")
        ts_proj = st.selectbox("Project", ["All projects"] + st.session_state.projects["Project name"].dropna().unique().tolist(), key="ts_proj_filter")
        ts_member = st.selectbox("Team member", ["All members"] + member_names, key="ts_member_filter")
        st.markdown("---")
        total_h = st.session_state.timesheets["Hours"].apply(parse_budget).sum()
        total_c = sum(parse_budget(r["Hours"]) * (parse_budget(r["Rate"]) if r["Rate"] else role_rates.get(r["Role"], 0)) for _, r in st.session_state.timesheets.iterrows())
        st.metric("Total hours", f"{total_h:.1f}"); st.metric("Total cost", f"${total_c:,.2f}")
    elif page == "Fee Estimator":
        st.header("Estimates")
        if not st.session_state.estimates.empty:
            for _, e in st.session_state.estimates.iterrows():
                t = estimate_totals(e["Estimate ID"], st.session_state.estimate_lines, st.session_state.estimate_disb, e.get("Margin %", "0"), role_rates)
                if st.button(f"{e['Estimate name']}\n${t['total']:,.0f}", key=f"sidebar_est_{e['Estimate ID']}", use_container_width=True):
                    st.session_state.active_estimate_id = e["Estimate ID"]; st.rerun()
        if st.button("＋ New estimate", use_container_width=True):
            st.session_state.active_estimate_id = "new"; st.rerun()
    elif page == "Clients":
        st.header("Clients")
        st.metric("Companies", len(st.session_state.companies))
        st.metric("Contacts", len(st.session_state.contacts))
        st.markdown("---")
        for s in CLIENT_STATUSES:
            cnt = st.session_state.companies["Status"].value_counts().to_dict().get(s, 0)
            st.write(f"- {s}: {cnt}")
        st.markdown("---")
        if st.button("＋ New company", use_container_width=True):
            st.session_state.active_company_id = "new"; st.session_state.client_tab = "Companies"; st.rerun()
        if st.button("＋ New contact", use_container_width=True):
            st.session_state.active_contact_id = "new"; st.session_state.client_tab = "Contacts"; st.rerun()

# ── PROJECT TRACKER ───────────────────────────────────────────────────────────

if page == "Project Tracker":
    filtered = filter_projects(st.session_state.projects, selected_stages, selected_status, search_query)
    display = filtered.copy()
    display["Compliance %"] = display["Compliance checklist"].apply(compliance_progress)
    display["Milestone %"] = display["Milestones"].apply(milestone_progress)
    display["Budget"] = display["Budget"].apply(format_budget)
    left, right = st.columns([2, 1])
    with left:
        st.subheader("Active projects")
        if display.empty: st.info("No projects match the filters.")
        else: st.dataframe(display[COLUMNS + ["Compliance %", "Milestone %"]].fillna(""), use_container_width=True)
    with right:
        st.subheader("Update an existing project")
        proj_options = [""] + st.session_state.projects["Project name"].dropna().unique().tolist()
        try: di = proj_options.index(st.session_state.selected_project)
        except ValueError: di = 0
        selected = st.selectbox("Select a project", proj_options, index=di, key=f"project_edit_select_{st.session_state.selectbox_key}")
        if selected != st.session_state.selected_project:
            st.session_state.selected_project = selected; st.rerun()
        if st.session_state.selected_project:
            selected = st.session_state.selected_project
            if st.button("✕ Cancel", key="cancel_edit"):
                st.session_state.selected_project = ""; st.session_state.selectbox_key += 1; st.rerun()
            pidx = st.session_state.projects[st.session_state.projects["Project name"] == selected].index[0]
            cur = st.session_state.projects.loc[pidx].to_dict()
            with st.form("edit_project_form"):
                st.text_input("Project ID", value=cur.get("Project ID", ""), disabled=True)
                # Company picker
                comp_opts = ["(none)"] + company_names
                cur_comp = cur.get("Client", "")
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
                    st.session_state.projects = add_or_update_project({
                        "Project ID": cur.get("Project ID", ""), "Project name": selected,
                        "Client": e_company if e_company != "(none)" else "", "Company ID": comp_id,
                        "Location": e_location, "Project manager": e_manager,
                        "Start date": e_start.strftime("%Y-%m-%d"), "Target completion": e_target.strftime("%Y-%m-%d"),
                        "Stage": e_stage, "Status": e_status, "Budget": str(e_budget), "Fee": str(e_fee),
                        "Phase fees": e_phase_fees, "Weekly hours allocated": str(e_weekly_hours),
                        "Member hours allocation": normalize_member_hours(parse_member_hours(e_member_hours)),
                        "Phase schedule": normalize_phase_schedule(e_phase_schedule),
                        "Milestones": normalize_milestones(e_milestones),
                        "Team members": normalize_team_members(e_members),
                        "Compliance checklist": normalize_checklist(e_compliance), "Notes": e_notes,
                    }, st.session_state.projects)
                    save_projects(st.session_state.projects)
                    st.session_state.message = f"Updated '{selected}'."; st.session_state.selected_project = ""; st.session_state.selectbox_key += 1; st.rerun()
                if dlt:
                    st.session_state.projects = st.session_state.projects[st.session_state.projects["Project name"] != selected]
                    save_projects(st.session_state.projects)
                    st.session_state.message = f"Deleted '{selected}'."; st.session_state.selected_project = ""; st.session_state.selectbox_key += 1; st.rerun()

    st.markdown("---")
    st.subheader("Project Stages")
    st.caption("🔴 < 14 days  |  🟡 14–30 days  |  🟢 30+ days  |  ⚫ Not scheduled / passed")
    build_traffic_light_cards(filtered)

    st.markdown("---")
    col_add, col_team = st.columns(2)
    with col_add:
        if st.button("▲ Close" if st.session_state.show_add_project else "＋ Add a new project", key="toggle_add_project", use_container_width=True):
            st.session_state.show_add_project = not st.session_state.show_add_project; st.rerun()
        if st.session_state.show_add_project:
            with st.form("new_project_form"):
                n_id = st.text_input("Project ID (leave blank to auto-generate)")
                n_name = st.text_input("Project name")
                comp_opts2 = ["(none)"] + company_names
                n_company = st.selectbox("Client (company)", comp_opts2)
                n_location = st.text_input("Location"); n_manager = st.text_input("Project manager")
                c1, c2 = st.columns(2)
                with c1: n_start = st.date_input("Start date")
                with c2: n_target = st.date_input("Target completion")
                n_stage = st.selectbox("Stage", STAGES); n_status = st.selectbox("Status", STATUSES)
                n_budget = st.number_input("Budget", min_value=0.0, step=100.0, format="%f")
                n_fee = st.number_input("Total fee ($)", min_value=0.0, step=100.0, format="%f")
                n_phase_fees = st.text_area("Phase fees", height=80)
                n_weekly_hours = st.number_input("Weekly hours allocated", min_value=0.0, step=1.0)
                n_member_hours = st.text_area("Member hours allocation", height=80)
                n_phase_schedule = st.text_area("Phase schedule", height=80)
                n_milestones = st.text_area("Milestones", height=80)
                n_members = st.multiselect("Team members", member_names)
                n_compliance = st.multiselect("Compliance checklist", COMPLIANCE_TASKS)
                n_notes = st.text_area("Notes", height=80)
                if st.form_submit_button("Save project", use_container_width=True):
                    if not n_name: st.warning("Please enter a project name.")
                    else:
                        comp_row2 = st.session_state.companies[st.session_state.companies["Name"] == n_company]
                        comp_id2 = comp_row2.iloc[0]["Company ID"] if not comp_row2.empty else ""
                        st.session_state.projects = add_or_update_project({
                            "Project ID": n_id, "Project name": n_name,
                            "Client": n_company if n_company != "(none)" else "", "Company ID": comp_id2,
                            "Location": n_location, "Project manager": n_manager,
                            "Start date": n_start.strftime("%Y-%m-%d"), "Target completion": n_target.strftime("%Y-%m-%d"),
                            "Stage": n_stage, "Status": n_status, "Budget": str(n_budget), "Fee": str(n_fee),
                            "Phase fees": n_phase_fees, "Weekly hours allocated": str(n_weekly_hours),
                            "Member hours allocation": normalize_member_hours(parse_member_hours(n_member_hours)),
                            "Phase schedule": normalize_phase_schedule(n_phase_schedule),
                            "Milestones": normalize_milestones(n_milestones),
                            "Team members": normalize_team_members(n_members),
                            "Compliance checklist": normalize_checklist(n_compliance), "Notes": n_notes,
                        }, st.session_state.projects)
                        save_projects(st.session_state.projects)
                        st.session_state.message = f"Saved '{n_name}'."; st.session_state.show_add_project = False; st.rerun()

    with col_team:
        if st.button("▲ Close" if st.session_state.show_team_management else "👥 Team member management", key="toggle_team_management", use_container_width=True):
            st.session_state.show_team_management = not st.session_state.show_team_management; st.rerun()
        if st.session_state.show_team_management:
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
            if not st.session_state.members_df.empty:
                st.markdown("**Team members**")
                for _, mem in st.session_state.members_df.iterrows():
                    mname, mrole = mem["Team member"], mem["Role"]
                    is_exp = st.session_state.expanded_member == mname
                    mc1, mc2, mc3 = st.columns([3, 2, 1])
                    mc1.markdown(f"**{mname}**"); mc2.caption(mrole)
                    if mc3.button("✏️" if not is_exp else "▲", key=f"edit_mem_{mname}"):
                        st.session_state.expanded_member = None if is_exp else mname; st.rerun()
                    if is_exp:
                        with st.form(key=f"edit_member_form_{mname}"):
                            new_name = st.text_input("Name", value=mname)
                            new_role = st.selectbox("Role", list(DEFAULT_ROLES.keys()), index=list(DEFAULT_ROLES.keys()).index(mrole) if mrole in DEFAULT_ROLES else 0)
                            s1, s2 = st.columns(2)
                            if s1.form_submit_button("Save", use_container_width=True):
                                midx = st.session_state.members_df[st.session_state.members_df["Team member"] == mname].index[0]
                                st.session_state.members_df.at[midx, "Team member"] = new_name.strip()
                                st.session_state.members_df.at[midx, "Role"] = new_role
                                save_team_members_df(st.session_state.members_df); st.session_state.expanded_member = None; st.rerun()
                            if s2.form_submit_button("Delete", use_container_width=True):
                                st.session_state.members_df = st.session_state.members_df[st.session_state.members_df["Team member"] != mname]
                                save_team_members_df(st.session_state.members_df); st.session_state.expanded_member = None; st.rerun()
            weekly_capacity = st.number_input("Weekly capacity (hrs)", min_value=1.0, value=40.0, step=1.0)
            workload_df = compute_team_member_hours(st.session_state.projects, st.session_state.members_df, weekly_capacity)
            if not workload_df.empty:
                st.dataframe(workload_df.style.apply(style_workload_table, axis=1), use_container_width=True)
                overloaded = workload_df[workload_df["Available hours"] < 10]
                if not overloaded.empty: st.warning("Swamped: " + ", ".join(overloaded["Team member"].tolist()))

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
                st.markdown(f"<div style='border:1px solid #ddd;border-radius:10px;padding:14px 16px;margin-bottom:6px;background:#fafafa;border-left:5px solid {colour}'>"
                            f"<div style='font-weight:700;font-size:14px;margin-bottom:4px'>{task['Task name']}</div>"
                            f"<div style='font-size:11px;color:#666;margin-bottom:4px'>📁 {task['Project name']}</div>"
                            f"<div style='font-size:11px;color:#666;margin-bottom:4px'>👤 {task['Assigned to'] or 'Unassigned'}</div>"
                            f"<div style='display:inline-block;padding:2px 10px;border-radius:12px;background:{colour};color:white;font-size:11px;font-weight:600'>{task['Status']}</div>"
                            + (f"<div style='font-size:11px;color:#888;margin-top:8px'>{task['Notes']}</div>" if task["Notes"] else "") + "</div>", unsafe_allow_html=True)
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
    ts_df = st.session_state.timesheets.copy()
    if st.session_state.get("ts_proj_filter", "All projects") != "All projects": ts_df = ts_df[ts_df["Project name"] == st.session_state["ts_proj_filter"]]
    if st.session_state.get("ts_member_filter", "All members") != "All members": ts_df = ts_df[ts_df["Team member"] == st.session_state["ts_member_filter"]]
    if ts_df.empty: st.info("No timesheet entries yet. Use the ⏱ Hours button on a project card to log hours.")
    else:
        ts_df["Cost"] = ts_df.apply(lambda r: round(parse_budget(r["Hours"]) * (parse_budget(r["Rate"]) if r["Rate"] else role_rates.get(r["Role"], 0)), 2), axis=1)
        m1, m2, m3 = st.columns(3)
        m1.metric("Total hours", f"{ts_df['Hours'].apply(parse_budget).sum():.1f}")
        m2.metric("Total cost", f"${ts_df['Cost'].sum():,.2f}"); m3.metric("Entries", len(ts_df))
        st.markdown("---"); cols = st.columns(3)
        for i, (_, e) in enumerate(ts_df.sort_values("Date", ascending=False).iterrows()):
            eid = e["Entry ID"]
            with cols[i % 3]:
                st.markdown(f"<div style='border:1px solid #ddd;border-radius:10px;padding:14px 16px;margin-bottom:6px;background:#fafafa;border-left:5px solid #3498db'>"
                            f"<div style='font-weight:700;font-size:14px'>{e['Team member']}</div>"
                            f"<div style='font-size:11px;color:#666'>📁 {e['Project name']} — {e['Phase'] or 'No phase'}</div>"
                            f"<div style='font-size:11px;color:#666'>🗓 {e['Date']} &nbsp;·&nbsp; {e['Role']}</div>"
                            f"<div style='font-size:13px;font-weight:600;margin-top:6px'>{e['Hours']} hrs @ ${e['Rate']}/hr = <span style='color:#2ecc71'>${e['Cost']:,.2f}</span></div>"
                            + (f"<div style='font-size:11px;color:#888;margin-top:4px'>{e['Notes']}</div>" if e["Notes"] else "") + "</div>", unsafe_allow_html=True)
                if st.button("🗑 Delete", key=f"del_ts_page_{eid}", use_container_width=True):
                    st.session_state.timesheets = st.session_state.timesheets[st.session_state.timesheets["Entry ID"] != eid]
                    save_timesheets(st.session_state.timesheets); st.rerun()
    st.markdown("---"); st.subheader("Fee summary by project")
    if not st.session_state.projects.empty:
        rows = []
        for _, row in st.session_state.projects.iterrows():
            pid = row["Project ID"]; fee = parse_budget(row.get("Fee", row.get("Budget", "0")))
            consumed = project_fee_consumed(pid, st.session_state.timesheets, role_rates)
            hours = project_hours_logged(pid, st.session_state.timesheets)
            pct = round((consumed / fee) * 100, 1) if fee > 0 else 0
            rows.append({"Project": row["Project name"], "Client": row["Client"], "Total fee": f"${fee:,.2f}", "Hours logged": hours, "Fee consumed": f"${consumed:,.2f}", "% used": f"{pct}%"})
        st.dataframe(pd.DataFrame(rows), use_container_width=True)

# ── FEE ESTIMATOR ─────────────────────────────────────────────────────────────

elif page == "Fee Estimator":
    st.subheader("Fee Estimator")
    act = st.session_state.active_estimate_id
    if act == "new":
        st.markdown("### New estimate")
        with st.form("new_estimate_form"):
            ne_name = st.text_input("Estimate name"); ne_client = st.text_input("Client")
            comp_opts3 = ["(none)"] + company_names
            ne_comp = st.selectbox("Link to company", comp_opts3)
            proj_opts = ["(none)"] + st.session_state.projects["Project name"].dropna().unique().tolist()
            ne_proj = st.selectbox("Link to project (optional)", proj_opts)
            ne_margin = st.number_input("Margin %", min_value=0.0, max_value=100.0, step=0.5, value=15.0)
            ne_notes = st.text_area("Notes", height=80)
            if st.form_submit_button("Create estimate", use_container_width=True):
                if not ne_name: st.warning("Please enter an estimate name.")
                else:
                    proj_row = st.session_state.projects[st.session_state.projects["Project name"] == ne_proj]
                    comp_row3 = st.session_state.companies[st.session_state.companies["Name"] == ne_comp]
                    new_est = {"Estimate ID": create_id(), "Estimate name": ne_name,
                               "Client": ne_comp if ne_comp != "(none)" else ne_client,
                               "Company ID": comp_row3.iloc[0]["Company ID"] if not comp_row3.empty else "",
                               "Project ID": proj_row.iloc[0]["Project ID"] if not proj_row.empty else "",
                               "Project name": ne_proj if ne_proj != "(none)" else "",
                               "Margin %": str(ne_margin), "Notes": ne_notes,
                               "Created": pd.Timestamp.now().strftime("%Y-%m-%d"),
                               "Last updated": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")}
                    st.session_state.estimates = pd.concat([st.session_state.estimates, pd.DataFrame([new_est])], ignore_index=True)
                    save_estimates(st.session_state.estimates)
                    st.session_state.active_estimate_id = new_est["Estimate ID"]; st.rerun()
        if st.button("✕ Cancel", key="cancel_new_est"): st.session_state.active_estimate_id = None; st.rerun()
    elif act is not None:
        est_row = st.session_state.estimates[st.session_state.estimates["Estimate ID"] == act]
        if est_row.empty: st.warning("Estimate not found.")
        else:
            est = est_row.iloc[0].to_dict()
            totals = estimate_totals(act, st.session_state.estimate_lines, st.session_state.estimate_disb, est.get("Margin %", "0"), role_rates)
            hc1, hc2, hc3 = st.columns([3, 1, 1])
            hc1.markdown(f"## {est['Estimate name']}"); hc1.caption(f"{est['Client']} · {est.get('Project name','No project')} · Created {est.get('Created','')}")
            if hc2.button("✏️ Edit details", use_container_width=True):
                st.session_state[f"edit_est_{act}"] = not st.session_state.get(f"edit_est_{act}", False); st.rerun()
            if hc3.button("✕ Close", use_container_width=True): st.session_state.active_estimate_id = None; st.rerun()
            if st.session_state.get(f"edit_est_{act}", False):
                with st.form("edit_est_details"):
                    ee_name = st.text_input("Estimate name", value=est["Estimate name"])
                    ee_client = st.text_input("Client", value=est["Client"])
                    ee_margin = st.number_input("Margin %", min_value=0.0, max_value=100.0, step=0.5, value=parse_budget(est.get("Margin %", "15")))
                    ee_notes = st.text_area("Notes", value=est.get("Notes", ""), height=80)
                    proj_opts2 = ["(none)"] + st.session_state.projects["Project name"].dropna().unique().tolist()
                    curr_proj = est.get("Project name", "")
                    ee_proj = st.selectbox("Linked project", proj_opts2, index=proj_opts2.index(curr_proj) if curr_proj in proj_opts2 else 0)
                    s1, s2 = st.columns(2)
                    if s1.form_submit_button("Save", use_container_width=True):
                        eidx = st.session_state.estimates[st.session_state.estimates["Estimate ID"] == act].index[0]
                        proj_row2 = st.session_state.projects[st.session_state.projects["Project name"] == ee_proj]
                        for k, v in [("Estimate name", ee_name), ("Client", ee_client), ("Margin %", str(ee_margin)),
                                     ("Notes", ee_notes), ("Project name", ee_proj if ee_proj != "(none)" else ""),
                                     ("Project ID", proj_row2.iloc[0]["Project ID"] if not proj_row2.empty else ""),
                                     ("Last updated", pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"))]:
                            st.session_state.estimates.at[eidx, k] = v
                        save_estimates(st.session_state.estimates); st.session_state[f"edit_est_{act}"] = False; st.rerun()
                    if s2.form_submit_button("Delete estimate", use_container_width=True):
                        for df_key, save_fn in [("estimates", save_estimates), ("estimate_lines", save_estimate_lines), ("estimate_disb", save_estimate_disb)]:
                            id_col = "Estimate ID"
                            st.session_state[df_key] = st.session_state[df_key][st.session_state[df_key][id_col] != act]
                            save_fn(st.session_state[df_key])
                        st.session_state.active_estimate_id = None; st.rerun()
            st.markdown("---")
            mc1, mc2, mc3, mc4, mc5 = st.columns(5)
            mc1.metric("Hours cost", f"${totals['hours_cost']:,.2f}"); mc2.metric("Disbursements", f"${totals['total_disb']:,.2f}")
            mc3.metric("Subtotal", f"${totals['subtotal']:,.2f}"); mc4.metric(f"Margin ({est.get('Margin %','0')}%)", f"${totals['margin_amt']:,.2f}")
            mc5.metric("TOTAL FEE", f"${totals['total']:,.2f}")
            st.markdown("---"); st.markdown("### Phase & Role Hours")
            for phase in STAGES:
                with st.expander(f"**{phase}**", expanded=True):
                    phase_lines = st.session_state.estimate_lines[(st.session_state.estimate_lines["Estimate ID"] == act) & (st.session_state.estimate_lines["Phase"] == phase)]
                    roles = list(DEFAULT_ROLES.keys())
                    with st.form(key=f"phase_form_{act}_{phase}"):
                        hour_inputs = {}
                        fcols = st.columns(len(roles) + 1); fcols[0].markdown("**Hrs / Cost**")
                        for j, role in enumerate(roles): fcols[j+1].markdown(f"**{role}**")
                        hr_cols = st.columns(len(roles) + 1); hr_cols[0].markdown("Hours")
                        for j, role in enumerate(roles):
                            existing = phase_lines[phase_lines["Role"] == role]
                            curr_hrs = parse_budget(existing.iloc[0]["Hours"]) if not existing.empty else 0.0
                            hour_inputs[role] = hr_cols[j+1].number_input(role, min_value=0.0, step=0.5, value=curr_hrs, key=f"hrs_{act}_{phase}_{role}", label_visibility="collapsed")
                        cost_cols = st.columns(len(roles) + 1); cost_cols[0].markdown("Cost")
                        phase_cost = 0.0
                        for j, role in enumerate(roles):
                            c = hour_inputs[role] * role_rates.get(role, 0); phase_cost += c
                            cost_cols[j+1].markdown(f"${c:,.0f}")
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
                    did = d["Disb ID"]
                    dc1, dc2, dc3, dc4 = st.columns([3, 2, 2, 1])
                    dc1.markdown(f"**{d['Description']}**"); dc2.caption(d["Type"])
                    dc3.markdown(f"${parse_budget(d['Value']):,.2f}" if d["Type"] == "Fixed ($)" else f"{d['Value']}%")
                    if dc4.button("🗑", key=f"del_disb_{did}"):
                        st.session_state.estimate_disb = st.session_state.estimate_disb[st.session_state.estimate_disb["Disb ID"] != did]
                        save_estimate_disb(st.session_state.estimate_disb); st.rerun()
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
                        st.session_state.projects.at[pidx2[0], "Fee"] = str(totals["total"])
                        save_projects(st.session_state.projects); st.success(f"Fee of ${totals['total']:,.2f} pushed to '{est['Project name']}'.")
            est_fresh = st.session_state.estimates[st.session_state.estimates["Estimate ID"] == act].iloc[0].to_dict()
            totals_fresh = estimate_totals(act, st.session_state.estimate_lines, st.session_state.estimate_disb, est_fresh.get("Margin %", "0"), role_rates)
            pdf_html = generate_pdf_html(est_fresh, st.session_state.estimate_lines, st.session_state.estimate_disb, totals_fresh, role_rates)
            st.download_button("⬇️ Download estimate as HTML (print to PDF)", data=pdf_html.encode("utf-8"),
                               file_name=f"estimate_{est_fresh['Estimate name'].replace(' ','_')}.html", mime="text/html", use_container_width=True)
    else:
        st.info("Select an estimate from the sidebar or create a new one.")

# ── CLIENTS ───────────────────────────────────────────────────────────────────

elif page == "Clients":
    st.subheader("Client Database")

    # ── Status pie chart ──
    if not st.session_state.companies.empty:
        status_counts = st.session_state.companies["Status"].value_counts().reset_index()
        status_counts.columns = ["Status", "Count"]
        status_counts["Colour"] = status_counts["Status"].map(CLIENT_STATUS_COLOURS)

        import altair as alt
        pie = alt.Chart(status_counts).mark_arc(innerRadius=50).encode(
            theta=alt.Theta("Count:Q"),
            color=alt.Color("Status:N", scale=alt.Scale(
                domain=list(CLIENT_STATUS_COLOURS.keys()),
                range=list(CLIENT_STATUS_COLOURS.values())
            ), legend=alt.Legend(title="Status")),
            tooltip=[alt.Tooltip("Status:N"), alt.Tooltip("Count:Q")],
        ).properties(width=260, height=260, title="Clients by status")

        text = alt.Chart(status_counts).mark_text(radius=130, fontSize=12, fontWeight="bold").encode(
            theta=alt.Theta("Count:Q", stack=True),
            text=alt.Text("Count:Q"),
            color=alt.value("#333"),
        )

        pc1, pc2, pc3 = st.columns([1, 1, 2])
        with pc1:
            st.altair_chart(pie + text, use_container_width=False)
        with pc2:
            st.markdown("**Summary**")
            for s in CLIENT_STATUSES:
                cnt = status_counts[status_counts["Status"] == s]["Count"].sum() if s in status_counts["Status"].values else 0
                colour = CLIENT_STATUS_COLOURS[s]
                st.markdown(f"<div style='display:flex;align-items:center;gap:8px;margin-bottom:6px'>"
                            f"<div style='width:14px;height:14px;border-radius:50%;background:{colour}'></div>"
                            f"<span style='font-size:13px'><strong>{s}</strong>: {cnt}</span></div>",
                            unsafe_allow_html=True)
        st.markdown("---")
    tab_companies, tab_contacts = st.tabs(["🏢 Companies", "👤 Contacts"])

    # ── COMPANIES ──
    with tab_companies:
        search_co = st.text_input("Search companies", key="search_companies")
        cos = st.session_state.companies.copy()
        if search_co:
            s = search_co.lower()
            cos = cos[cos["Name"].str.lower().str.contains(s, na=False) | cos["Industry"].str.lower().str.contains(s, na=False) | cos["Tags"].str.lower().str.contains(s, na=False)]

        act_co = st.session_state.active_company_id

        # New company form
        if act_co == "new":
            st.markdown("### New company")
            cf_state_key = "new_company_cfs"
            if cf_state_key not in st.session_state:
                st.session_state[cf_state_key] = []

            nc1, nc2 = st.columns(2)
            with nc1:
                nc_name = st.text_input("Company name", key="nc_name")
                nc_status = st.selectbox("Status", CLIENT_STATUSES, key="nc_status")
                nc_industry = st.selectbox("Industry", [""] + INDUSTRIES, key="nc_industry")
                nc_phone = st.text_input("Phone", key="nc_phone")
                nc_website = st.text_input("Website", key="nc_website")
                nc_referral = st.selectbox("Referral source", [""] + REFERRAL_SOURCES, key="nc_referral")
            with nc2:
                nc_billing = st.text_area("Billing address", height=100, key="nc_billing")
                nc_postal = st.text_area("Postal address", height=100, key="nc_postal")
                nc_tags = st.text_input("Tags (comma separated)", key="nc_tags")
                nc_notes = st.text_area("Notes", height=80, key="nc_notes")

            st.session_state[cf_state_key] = render_custom_fields_editor(st.session_state[cf_state_key], "new_co")

            s1, s2 = st.columns(2)
            if s1.button("Save company", use_container_width=True, key="save_new_company"):
                if not nc_name:
                    st.warning("Please enter a company name.")
                else:
                    new_co = {"Company ID": create_id(), "Name": nc_name, "Status": nc_status,
                              "Industry": nc_industry, "Website": nc_website, "Phone": nc_phone,
                              "Billing address": nc_billing, "Postal address": nc_postal,
                              "Referral source": nc_referral, "Notes": nc_notes,
                              "Tags": normalize_tags(parse_tags(nc_tags)),
                              "Custom fields": serialize_custom_fields(st.session_state[cf_state_key]),
                              "Created": pd.Timestamp.now().strftime("%Y-%m-%d"),
                              "Last updated": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")}
                    st.session_state.companies = pd.concat([st.session_state.companies, pd.DataFrame([new_co])], ignore_index=True)
                    save_companies(st.session_state.companies)
                    st.session_state.active_company_id = new_co["Company ID"]
                    if cf_state_key in st.session_state: del st.session_state[cf_state_key]
                    st.rerun()
            if s2.button("Cancel", use_container_width=True, key="cancel_new_company"):
                st.session_state.active_company_id = None
                if cf_state_key in st.session_state: del st.session_state[cf_state_key]
                st.rerun()

        elif act_co is not None:
            co_row = st.session_state.companies[st.session_state.companies["Company ID"] == act_co]
            if co_row.empty:
                st.warning("Company not found.")
            else:
                co = co_row.iloc[0].to_dict()
                sc = CLIENT_STATUS_COLOURS.get(co["Status"], "#aaaaaa")
                # Header
                hc1, hc2, hc3 = st.columns([3, 1, 1])
                hc1.markdown(f"## {co['Name']}")
                hc1.markdown(f"<span style='background:{sc};color:white;padding:3px 10px;border-radius:12px;font-size:12px'>{co['Status']}</span> &nbsp; <span style='color:#888;font-size:13px'>{co['Industry']}</span>", unsafe_allow_html=True)
                edit_mode = st.session_state.get(f"edit_co_{act_co}", False)
                if hc2.button("✏️ Edit" if not edit_mode else "▲ Close edit", use_container_width=True):
                    st.session_state[f"edit_co_{act_co}"] = not edit_mode; st.rerun()
                if hc3.button("✕ Close", use_container_width=True): st.session_state.active_company_id = None; st.rerun()

                if edit_mode:
                    cf_edit_key = f"edit_co_cfs_{act_co}"
                    if cf_edit_key not in st.session_state: st.session_state[cf_edit_key] = parse_custom_fields(co.get("Custom fields", ""))
                    with st.form("edit_company_form"):
                        ec1, ec2 = st.columns(2)
                        with ec1:
                            e_name = st.text_input("Company name", value=co["Name"])
                            e_status = st.selectbox("Status", CLIENT_STATUSES, index=CLIENT_STATUSES.index(co["Status"]) if co["Status"] in CLIENT_STATUSES else 0)
                            e_industry = st.selectbox("Industry", [""] + INDUSTRIES, index=([""] + INDUSTRIES).index(co["Industry"]) if co["Industry"] in INDUSTRIES else 0)
                            e_phone = st.text_input("Phone", value=co["Phone"])
                            e_website = st.text_input("Website", value=co["Website"])
                            e_referral = st.selectbox("Referral source", [""] + REFERRAL_SOURCES, index=([""] + REFERRAL_SOURCES).index(co["Referral source"]) if co["Referral source"] in REFERRAL_SOURCES else 0)
                        with ec2:
                            e_billing = st.text_area("Billing address", value=co["Billing address"], height=100)
                            e_postal = st.text_area("Postal address", value=co["Postal address"], height=100)
                            e_tags = st.text_input("Tags", value=co["Tags"])
                            e_notes = st.text_area("Notes", value=co["Notes"], height=80)
                        updated_cfs2 = render_custom_fields_editor(st.session_state[cf_edit_key], f"edit_co_{act_co}")
                        s1, s2 = st.columns(2)
                        if s1.form_submit_button("Save", use_container_width=True):
                            cidx = st.session_state.companies[st.session_state.companies["Company ID"] == act_co].index[0]
                            for k, v in [("Name", e_name), ("Status", e_status), ("Industry", e_industry),
                                         ("Phone", e_phone), ("Website", e_website), ("Referral source", e_referral),
                                         ("Billing address", e_billing), ("Postal address", e_postal),
                                         ("Tags", normalize_tags(parse_tags(e_tags))), ("Notes", e_notes),
                                         ("Custom fields", serialize_custom_fields(updated_cfs2)),
                                         ("Last updated", pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"))]:
                                st.session_state.companies.at[cidx, k] = v
                            save_companies(st.session_state.companies)
                            st.session_state[f"edit_co_{act_co}"] = False
                            if cf_edit_key in st.session_state: del st.session_state[cf_edit_key]
                            st.rerun()
                        if s2.form_submit_button("Delete company", use_container_width=True):
                            st.session_state.companies = st.session_state.companies[st.session_state.companies["Company ID"] != act_co]
                            save_companies(st.session_state.companies)
                            st.session_state.active_company_id = None; st.rerun()
                else:
                    # View mode
                    d1, d2, d3 = st.columns(3)
                    d1.markdown(f"📞 {co['Phone'] or '—'}")
                    d2.markdown(f"🌐 {co['Website'] or '—'}")
                    d3.markdown(f"🔗 Referral: {co['Referral source'] or '—'}")
                    st.markdown(f"**Billing:** {co['Billing address'] or '—'}  &nbsp;|&nbsp;  **Postal:** {co['Postal address'] or '—'}")
                    if co["Tags"]: st.markdown(" ".join(f"`{t}`" for t in parse_tags(co["Tags"])))
                    if co["Notes"]: st.info(co["Notes"])
                    cfs = parse_custom_fields(co.get("Custom fields", ""))
                    if cfs:
                        st.markdown("**Custom fields**")
                        for cf in cfs:
                            if cf.get("label"): st.markdown(f"- **{cf['label']}:** {cf.get('value','')}")

                # Linked records
                st.markdown("---")
                lt1, lt2, lt3 = st.tabs(["📁 Projects", "📋 Estimates", "👤 Contacts"])
                with lt1:
                    linked_proj = st.session_state.projects[st.session_state.projects["Company ID"] == act_co]
                    if linked_proj.empty: st.caption("No linked projects.")
                    else:
                        for _, p in linked_proj.iterrows():
                            st.markdown(f"**{p['Project name']}** — {p['Stage']} — {p['Status']}")
                with lt2:
                    linked_est = st.session_state.estimates[st.session_state.estimates["Company ID"] == act_co]
                    if linked_est.empty: st.caption("No linked estimates.")
                    else:
                        for _, e in linked_est.iterrows():
                            t2 = estimate_totals(e["Estimate ID"], st.session_state.estimate_lines, st.session_state.estimate_disb, e.get("Margin %", "0"), role_rates)
                            st.markdown(f"**{e['Estimate name']}** — Total: ${t2['total']:,.2f}")
                with lt3:
                    linked_contacts = st.session_state.contacts[st.session_state.contacts["Company ID"] == act_co].copy()
                    if linked_contacts.empty:
                        st.caption("No linked contacts.")
                    else:
                        for _, ct in linked_contacts.iterrows():
                            ctid = ct["Contact ID"]
                            is_primary = ct.get("Is primary", "False") == "True"
                            exp_key = f"co_ct_exp_{ctid}"
                            is_exp = st.session_state.get(exp_key, False)

                            # Contact summary row
                            r1, r2, r3, r4 = st.columns([3, 2, 2, 1])
                            r1.markdown(f"**{ct['First name']} {ct['Last name']}**" + (" ⭐" if is_primary else ""))
                            r2.caption(ct["Title"] or "No title")
                            r3.caption(ct["Email"] or "No email")
                            if r4.button("✏️" if not is_exp else "▲", key=f"co_ct_toggle_{ctid}"):
                                st.session_state[exp_key] = not is_exp
                                st.rerun()

                            if is_exp:
                                with st.form(key=f"co_ct_edit_{ctid}"):
                                    ef1, ef2 = st.columns(2)
                                    with ef1:
                                        e_first = st.text_input("First name", value=ct["First name"])
                                        e_last = st.text_input("Last name", value=ct["Last name"])
                                        e_title = st.text_input("Title / Role", value=ct["Title"])
                                        e_email = st.text_input("Email", value=ct["Email"])
                                    with ef2:
                                        e_phone = st.text_input("Phone", value=ct["Phone"])
                                        e_mobile = st.text_input("Mobile", value=ct["Mobile"])
                                        e_primary = st.checkbox("Primary contact", value=is_primary)
                                        # Company reassignment
                                        comp_opts_ct = ["(none)"] + company_names
                                        curr_co = ct.get("Company name", "")
                                        e_company = st.selectbox("Company", comp_opts_ct,
                                            index=comp_opts_ct.index(curr_co) if curr_co in comp_opts_ct else 0)
                                    e_address = st.text_area("Address", value=ct["Address"], height=60)
                                    e_notes = st.text_area("Notes", value=ct["Notes"], height=60)
                                    e_tags = st.text_input("Tags", value=ct["Tags"])

                                    sb1, sb2, sb3 = st.columns(3)
                                    save_ct = sb1.form_submit_button("Save", use_container_width=True)
                                    remove_ct = sb2.form_submit_button("Remove from company", use_container_width=True)
                                    delete_ct = sb3.form_submit_button("Delete contact", use_container_width=True)

                                    if save_ct:
                                        new_co_row = st.session_state.companies[st.session_state.companies["Name"] == e_company]
                                        new_co_id = new_co_row.iloc[0]["Company ID"] if not new_co_row.empty else ""
                                        ctidx = st.session_state.contacts[st.session_state.contacts["Contact ID"] == ctid].index[0]
                                        for k, v in [
                                            ("First name", e_first), ("Last name", e_last),
                                            ("Title", e_title), ("Email", e_email),
                                            ("Phone", e_phone), ("Mobile", e_mobile),
                                            ("Is primary", str(e_primary)),
                                            ("Company name", e_company if e_company != "(none)" else ""),
                                            ("Company ID", new_co_id),
                                            ("Address", e_address), ("Notes", e_notes),
                                            ("Tags", normalize_tags(parse_tags(e_tags))),
                                            ("Last updated", pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")),
                                        ]:
                                            st.session_state.contacts.at[ctidx, k] = v
                                        save_contacts(st.session_state.contacts)
                                        st.session_state[exp_key] = False
                                        st.rerun()

                                    if remove_ct:
                                        ctidx = st.session_state.contacts[st.session_state.contacts["Contact ID"] == ctid].index[0]
                                        st.session_state.contacts.at[ctidx, "Company ID"] = ""
                                        st.session_state.contacts.at[ctidx, "Company name"] = ""
                                        st.session_state.contacts.at[ctidx, "Last updated"] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
                                        save_contacts(st.session_state.contacts)
                                        st.session_state[exp_key] = False
                                        st.rerun()

                                    if delete_ct:
                                        st.session_state.contacts = st.session_state.contacts[
                                            st.session_state.contacts["Contact ID"] != ctid]
                                        save_contacts(st.session_state.contacts)
                                        st.rerun()

                            st.divider()

                    # Add a new contact directly from company record
                    st.markdown("**＋ Add contact to this company**")
                    with st.form(key=f"add_ct_to_co_{act_co}"):
                        an1, an2 = st.columns(2)
                        with an1:
                            a_first = st.text_input("First name")
                            a_last = st.text_input("Last name")
                            a_title = st.text_input("Title / Role")
                            a_email = st.text_input("Email")
                        with an2:
                            a_phone = st.text_input("Phone")
                            a_mobile = st.text_input("Mobile")
                            a_primary = st.checkbox("Primary contact")
                            a_notes = st.text_area("Notes", height=60)
                        if st.form_submit_button("Add contact", use_container_width=True):
                            if not a_first or not a_last:
                                st.warning("Please enter first and last name.")
                            else:
                                co_name = st.session_state.companies[st.session_state.companies["Company ID"] == act_co].iloc[0]["Name"]
                                new_ct2 = {
                                    "Contact ID": create_id(), "Company ID": act_co,
                                    "Company name": co_name, "First name": a_first, "Last name": a_last,
                                    "Title": a_title, "Email": a_email, "Phone": a_phone,
                                    "Mobile": a_mobile, "Address": "", "Notes": a_notes,
                                    "Tags": "", "Custom fields": "[]", "Is primary": str(a_primary),
                                    "Created": pd.Timestamp.now().strftime("%Y-%m-%d"),
                                    "Last updated": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"),
                                }
                                st.session_state.contacts = pd.concat(
                                    [st.session_state.contacts, pd.DataFrame([new_ct2])], ignore_index=True)
                                save_contacts(st.session_state.contacts)
                                st.rerun()

        else:
            # Company cards
            if cos.empty: st.info("No companies yet. Use '＋ New company' in the sidebar.")
            else:
                cols = st.columns(3)
                for i, (_, co) in enumerate(cos.iterrows()):
                    cid = co["Company ID"]; sc = CLIENT_STATUS_COLOURS.get(co["Status"], "#aaaaaa")
                    linked_proj_count = len(st.session_state.projects[st.session_state.projects["Company ID"] == cid])
                    linked_contact_count = len(st.session_state.contacts[st.session_state.contacts["Company ID"] == cid])
                    with cols[i % 3]:
                        st.markdown(
                            f"<div style='border:1px solid #ddd;border-radius:10px;padding:14px 16px;margin-bottom:6px;background:#fafafa;border-left:5px solid {sc}'>"
                            f"<div style='font-weight:700;font-size:15px;margin-bottom:4px'>{co['Name']}</div>"
                            f"<div style='display:inline-block;padding:2px 10px;border-radius:12px;background:{sc};color:white;font-size:11px;font-weight:600;margin-bottom:6px'>{co['Status']}</div>"
                            f"<div style='font-size:11px;color:#666'>{co['Industry'] or ''}</div>"
                            f"<div style='font-size:11px;color:#666'>📞 {co['Phone'] or '—'} &nbsp;·&nbsp; 🌐 {co['Website'] or '—'}</div>"
                            f"<div style='font-size:11px;color:#888;margin-top:4px'>📁 {linked_proj_count} projects &nbsp;·&nbsp; 👤 {linked_contact_count} contacts</div>"
                            + (f"<div style='margin-top:6px'>{' '.join(f'<span style=background:#eee;padding:2px 6px;border-radius:8px;font-size:10px>{t}</span>' for t in parse_tags(co['Tags']))}</div>" if co["Tags"] else "")
                            + "</div>", unsafe_allow_html=True)
                        if st.button("Open", key=f"open_co_{cid}", use_container_width=True):
                            st.session_state.active_company_id = cid; st.rerun()

    # ── CONTACTS ──
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
            if cf_ct_key not in st.session_state:
                st.session_state[cf_ct_key] = []

            cc1, cc2 = st.columns(2)
            with cc1:
                nc_first = st.text_input("First name", key="nc_first")
                nc_last = st.text_input("Last name", key="nc_last")
                nc_title = st.text_input("Title / Role", key="nc_title")
                nc_email = st.text_input("Email", key="nc_email")
                nc_phone = st.text_input("Phone", key="nc_ct_phone")
                nc_mobile = st.text_input("Mobile", key="nc_mobile")
            with cc2:
                comp_opts4 = ["(none)"] + company_names
                nc_company = st.selectbox("Company", comp_opts4, key="nc_company")
                nc_address = st.text_area("Address", height=80, key="nc_address")
                nc_tags = st.text_input("Tags (comma separated)", key="nc_ct_tags")
                nc_notes = st.text_area("Notes", height=80, key="nc_ct_notes")
                nc_primary = st.checkbox("Primary contact", key="nc_primary")

            st.session_state[cf_ct_key] = render_custom_fields_editor(st.session_state[cf_ct_key], "new_ct")

            s1, s2 = st.columns(2)
            if s1.button("Save contact", use_container_width=True, key="save_new_contact"):
                if not nc_first or not nc_last:
                    st.warning("Please enter first and last name.")
                else:
                    comp_row4 = st.session_state.companies[st.session_state.companies["Name"] == nc_company]
                    new_ct = {"Contact ID": create_id(),
                              "Company ID": comp_row4.iloc[0]["Company ID"] if not comp_row4.empty else "",
                              "Company name": nc_company if nc_company != "(none)" else "",
                              "First name": nc_first, "Last name": nc_last, "Title": nc_title,
                              "Email": nc_email, "Phone": nc_phone, "Mobile": nc_mobile,
                              "Address": nc_address, "Notes": nc_notes,
                              "Tags": normalize_tags(parse_tags(nc_tags)),
                              "Custom fields": serialize_custom_fields(st.session_state[cf_ct_key]),
                              "Is primary": str(nc_primary),
                              "Created": pd.Timestamp.now().strftime("%Y-%m-%d"),
                              "Last updated": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")}
                    st.session_state.contacts = pd.concat([st.session_state.contacts, pd.DataFrame([new_ct])], ignore_index=True)
                    save_contacts(st.session_state.contacts)
                    st.session_state.active_contact_id = new_ct["Contact ID"]
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
                hc1.markdown(f"## {ct['First name']} {ct['Last name']}")
                hc1.caption(f"{ct['Title'] or ''} · {ct['Company name'] or 'No company'}")
                edit_ct = st.session_state.get(f"edit_ct_{act_ct}", False)
                if hc2.button("✏️ Edit" if not edit_ct else "▲ Close edit", key=f"edit_ct_btn_{act_ct}", use_container_width=True):
                    st.session_state[f"edit_ct_{act_ct}"] = not edit_ct; st.rerun()
                if hc3.button("✕ Close", key=f"close_ct_btn_{act_ct}", use_container_width=True): st.session_state.active_contact_id = None; st.rerun()

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
                            comp_opts5 = ["(none)"] + company_names
                            curr_co_name = ct.get("Company name", "")
                            e_company = st.selectbox("Company", comp_opts5, index=comp_opts5.index(curr_co_name) if curr_co_name in comp_opts5 else 0)
                            e_address = st.text_area("Address", value=ct["Address"], height=80)
                            e_tags = st.text_input("Tags", value=ct["Tags"]); e_notes = st.text_area("Notes", value=ct["Notes"], height=80)
                            e_primary = st.checkbox("Primary contact", value=ct.get("Is primary", "False") == "True")
                        updated_ct_cfs2 = render_custom_fields_editor(st.session_state[cf_ct_edit_key], f"edit_ct_{act_ct}")
                        s1, s2 = st.columns(2)
                        if s1.form_submit_button("Save", use_container_width=True):
                            ctidx = st.session_state.contacts[st.session_state.contacts["Contact ID"] == act_ct].index[0]
                            comp_row5 = st.session_state.companies[st.session_state.companies["Name"] == e_company]
                            for k, v in [("First name", e_first), ("Last name", e_last), ("Title", e_title),
                                         ("Email", e_email), ("Phone", e_phone), ("Mobile", e_mobile),
                                         ("Company name", e_company if e_company != "(none)" else ""),
                                         ("Company ID", comp_row5.iloc[0]["Company ID"] if not comp_row5.empty else ""),
                                         ("Address", e_address), ("Tags", normalize_tags(parse_tags(e_tags))),
                                         ("Notes", e_notes), ("Is primary", str(e_primary)),
                                         ("Custom fields", serialize_custom_fields(updated_ct_cfs2)),
                                         ("Last updated", pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"))]:
                                st.session_state.contacts.at[ctidx, k] = v
                            save_contacts(st.session_state.contacts)
                            st.session_state[f"edit_ct_{act_ct}"] = False
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
                        st.markdown(
                            "<div style='border:1px solid #ddd;border-radius:10px;padding:14px 16px;margin-bottom:6px;background:#fafafa;border-left:5px solid #3498db'>"
                            f"<div style='font-weight:700;font-size:15px;margin-bottom:2px'>{ct['First name']} {ct['Last name']}</div>"
                            f"<div style='font-size:12px;color:#666;margin-bottom:4px'>{ct['Title'] or ''} &nbsp;·&nbsp; {ct['Company name'] or 'No company'}</div>"
                            f"<div style='font-size:11px;color:#666'>📧 {ct['Email'] or '—'}</div>"
                            f"<div style='font-size:11px;color:#666'>📞 {ct['Phone'] or '—'}</div>"
                            + ("⭐ Primary" if ct.get("Is primary") == "True" else "")
                            + "</div>", unsafe_allow_html=True)
                        if st.button("Open", key=f"open_ct_{ctid}", use_container_width=True):
                            st.session_state.active_contact_id = ctid; st.rerun()

# ── footer ────────────────────────────────────────────────────────────────────

if st.session_state.message:
    st.success(st.session_state.message); st.session_state.message = ""

st.markdown("---")
st.download_button("⬇️ Download project tracker CSV",
                   data=st.session_state.projects.to_csv(index=False).encode("utf-8"),
                   file_name="fitout_projects.csv", mime="text/csv")