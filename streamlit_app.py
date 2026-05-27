from pathlib import Path
import re
import uuid

import altair as alt
import pandas as pd
import streamlit as st

PAGE_TITLE = "Office Fitout Project Tracker"
DATA_FILE = Path(__file__).parent / "projects.csv"
TEAM_MEMBERS_FILE = Path(__file__).parent / "team_members.csv"

STAGES = [
    "Concept",
    "Design Development",
    "Tender",
    "Construction",
    "Handover",
    "Code of Compliance",
]
STATUSES = ["On track", "At risk", "Delayed", "Complete"]
COMPLIANCE_TASKS = [
    "Fire safety sign-off",
    "Electrical certificate",
    "Plumbing certificate",
    "OHS inspection",
    "Code compliance certificate",
]
COLUMNS = [
    "Project ID",
    "Project name",
    "Client",
    "Location",
    "Project manager",
    "Start date",
    "Target completion",
    "Stage",
    "Status",
    "Budget",
    "Weekly hours allocated",
    "Member hours allocation",
    "Phase schedule",
    "Milestones",
    "Team members",
    "Compliance checklist",
    "Notes",
    "Last updated",
]

TASKS_FILE = Path(__file__).parent / "tasks.csv"
TASK_COLUMNS = [
    "Task ID",
    "Project ID",
    "Project name",
    "Task name",
    "Team",
    "Assigned to",
    "Status",
    "Notes",
    "Last updated",
]
TASK_TEAMS = ["Design", "Project Management"]
TASK_STATUSES = ["Not started", "Ongoing", "Completed"]


def ensure_data_file():
    if not DATA_FILE.exists():
        pd.DataFrame(columns=COLUMNS).to_csv(DATA_FILE, index=False)


def ensure_team_members_file():
    if not TEAM_MEMBERS_FILE.exists():
        pd.DataFrame({"Team member": []}).to_csv(TEAM_MEMBERS_FILE, index=False)


def parse_budget(value):
    if pd.isna(value) or value == "":
        return 0.0
    try:
        return float(str(value).replace(",", "").replace("$", "").strip())
    except ValueError:
        return 0.0


def format_budget(value):
    amount = parse_budget(value)
    return f"${amount:,.2f}"


def parse_weekly_hours(value):
    if pd.isna(value) or value == "":
        return 0.0
    try:
        return float(str(value).replace(",", "").strip())
    except ValueError:
        return 0.0


def compute_team_member_hours(df: pd.DataFrame, team_members: list[str], weekly_capacity: float = 40.0) -> pd.DataFrame:
    workload = {member: {"Assigned hours": 0.0, "Projects assigned": 0} for member in team_members}
    for _, row in df.iterrows():
        members = parse_team_members(row.get("Team members", ""))
        member_hours = parse_member_hours(row.get("Member hours allocation", ""))
        if member_hours:
            for member, hours in member_hours.items():
                if member not in workload:
                    workload[member] = {"Assigned hours": 0.0, "Projects assigned": 0}
                workload[member]["Assigned hours"] += hours
                workload[member]["Projects assigned"] += 1
            continue

        weekly_hours = parse_weekly_hours(row.get("Weekly hours allocated", ""))
        if weekly_hours <= 0 or not members:
            continue
        share = weekly_hours / len(members)
        for member in members:
            if member not in workload:
                workload[member] = {"Assigned hours": 0.0, "Projects assigned": 0}
            workload[member]["Assigned hours"] += share
            workload[member]["Projects assigned"] += 1

    records = []
    for member, data in workload.items():
        assigned = round(data["Assigned hours"], 1)
        available = round(max(0.0, weekly_capacity - assigned), 1)
        if available < 10:
            status = "Swamped"
        elif available < 20:
            status = "Getting full"
        else:
            status = "OK"
        records.append(
            {
                "Team member": member,
                "Projects assigned": data["Projects assigned"],
                "Assigned hours": assigned,
                "Available hours": available,
                "Status": status,
            }
        )

    return pd.DataFrame(records).sort_values(["Assigned hours", "Team member"], ascending=[False, True])


def style_workload_table(row):
    available = row["Available hours"]
    if available < 10:
        return ["background-color: #ff9999"] * len(row)
    if available < 20:
        return ["background-color: #ffcc99"] * len(row)
    return ["background-color: #d4f4d4"] * len(row)


def style_task_table(row):
    status = row["Status"]
    if status == "Completed":
        return ["background-color: #d4f4d4"] * len(row)
    if status == "Ongoing":
        return ["background-color: #fff2cc"] * len(row)
    if status == "Not started":
        return ["background-color: #e6e6e6"] * len(row)
    return [""] * len(row)


def parse_milestones(value: str) -> list[str]:
    if not value or pd.isna(value):
        return []
    return [line.strip() for line in str(value).splitlines() if line.strip()]


def normalize_milestones(value: str) -> str:
    return "\n".join(parse_milestones(value))


def milestone_progress(value: str) -> int:
    milestones = parse_milestones(value)
    if not milestones:
        return 0
    completed = sum(
        1
        for milestone in milestones
        if milestone.endswith("✓")
        or milestone.startswith("[x]")
        or milestone.startswith("[X]")
        or milestone.lower().endswith("complete")
    )
    return int((completed / len(milestones)) * 100)


def parse_phase_schedule(value: str) -> list[dict]:
    phases = []
    if not value or pd.isna(value):
        return phases
    for line in str(value).splitlines():
        cleaned = line.strip()
        if not cleaned or ":" not in cleaned:
            continue
        stage, rest = [part.strip() for part in cleaned.split(":", 1)]
        match = re.search(r"(\d{4}-\d{2}-\d{2})\s*(?:to|\-|–|—)\s*(\d{4}-\d{2}-\d{2})", rest)
        if not match:
            continue
        start = pd.to_datetime(match.group(1), errors="coerce")
        end = pd.to_datetime(match.group(2), errors="coerce")
        if pd.isna(start) or pd.isna(end):
            continue
        phases.append(
            {
                "Stage": stage,
                "Start date": start,
                "Target completion": end,
                "Duration weeks": round((end - start).days / 7, 1),
            }
        )
    return phases


def normalize_phase_schedule(value: str) -> str:
    return "\n".join(line.strip() for line in str(value).splitlines() if line.strip())


def parse_team_members(value: str) -> list[str]:
    if not value or pd.isna(value):
        return []
    return [item.strip() for item in str(value).split(";") if item.strip()]


def normalize_team_members(values):
    return "; ".join(sorted(values))


def parse_member_hours(value: str) -> dict[str, float]:
    if not value or pd.isna(value):
        return {}

    member_hours = {}
    lines = [part.strip() for part in str(value).splitlines() if part.strip()]
    for line in lines:
        if ":" not in line:
            continue
        member, hours = [part.strip() for part in line.split(":", 1)]
        if not member:
            continue
        parsed_hours = parse_weekly_hours(hours)
        if parsed_hours > 0:
            member_hours[member] = parsed_hours
    return member_hours


def normalize_member_hours(member_hours: dict[str, float]) -> str:
    lines = [f"{member}: {hours}" for member, hours in sorted(member_hours.items())]
    return "\n".join(lines)


def compliance_to_list(value: str):
    if not value or pd.isna(value):
        return []
    return [item.strip() for item in str(value).split(";") if item.strip()]


def normalize_checklist(values):
    return "; ".join(sorted(values))


def compliance_progress(value: str) -> int:
    completed = len([task for task in compliance_to_list(value) if task in COMPLIANCE_TASKS])
    return int((completed / len(COMPLIANCE_TASKS)) * 100) if COMPLIANCE_TASKS else 0


def stage_progress(stage: str) -> int:
    if stage in STAGES:
        return int(((STAGES.index(stage) + 1) / len(STAGES)) * 100)
    return 0


def parse_date(value: str, fallback=None):
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return fallback
    return parsed.date()


def load_projects():
    ensure_data_file()
    df = pd.read_csv(DATA_FILE, dtype=str)
    for column in COLUMNS:
        if column not in df.columns:
            df[column] = ""
    df = df[COLUMNS]
    df = df.fillna("")
    return df


def save_projects(df: pd.DataFrame):
    df.to_csv(DATA_FILE, index=False)


def load_team_members() -> list[str]:
    ensure_team_members_file()
    df = pd.read_csv(TEAM_MEMBERS_FILE, dtype=str)
    if "Team member" not in df.columns:
        df["Team member"] = ""
    members = [str(name).strip() for name in df["Team member"].dropna().unique()]
    return [member for member in sorted(members) if member]


def save_team_members(members: list[str]):
    members = sorted({str(member).strip() for member in members if str(member).strip()})
    pd.DataFrame({"Team member": members}).to_csv(TEAM_MEMBERS_FILE, index=False)


def ensure_tasks_file():
    if not TASKS_FILE.exists():
        pd.DataFrame(columns=TASK_COLUMNS).to_csv(TASKS_FILE, index=False)


def load_tasks() -> pd.DataFrame:
    ensure_tasks_file()
    df = pd.read_csv(TASKS_FILE, dtype=str)
    for column in TASK_COLUMNS:
        if column not in df.columns:
            df[column] = ""
    df = df[TASK_COLUMNS].fillna("")
    return df


def save_tasks(df: pd.DataFrame):
    df.to_csv(TASKS_FILE, index=False)


def create_task_id() -> str:
    return uuid.uuid4().hex[:8]


def add_or_update_project(data: dict, df: pd.DataFrame) -> pd.DataFrame:
    existing = df[df["Project name"] == data["Project name"]]
    data["Last updated"] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")

    if not existing.empty:
        index = existing.index[0]
        for key, value in data.items():
            df.at[index, key] = value
    else:
        data["Project ID"] = data.get("Project ID") or create_project_id()
        df = pd.concat([df, pd.DataFrame([data])], ignore_index=True)
    return df


def filter_projects(df: pd.DataFrame, stage_filter, status_filter, search_text: str) -> pd.DataFrame:
    filtered = df.copy()
    if stage_filter:
        filtered = filtered[filtered["Stage"].isin(stage_filter)]
    if status_filter:
        filtered = filtered[filtered["Status"].isin(status_filter)]
    if search_text:
        search_lower = search_text.lower()
        filtered = filtered[
            filtered["Project name"].str.lower().str.contains(search_lower, na=False)
            | filtered["Client"].str.lower().str.contains(search_lower, na=False)
            | filtered["Location"].str.lower().str.contains(search_lower, na=False)
        ]
    return filtered


def build_gantt_chart(df: pd.DataFrame, outlines: bool = True):
    phase_rows = []
    for _, row in df.iterrows():
        phases = parse_phase_schedule(row.get("Phase schedule", ""))
        if phases:
            for phase in phases:
                phase_rows.append(
                    {
                        "Project phase": f"{row['Project name']} — {phase['Stage']}",
                        "Project name": row["Project name"],
                        "Client": row["Client"],
                        "Location": row["Location"],
                        "Stage": phase["Stage"],
                        "Status": row["Status"],
                        "Start date": phase["Start date"],
                        "Target completion": phase["Target completion"],
                        "Budget": parse_budget(row["Budget"]),
                        "Compliance progress": compliance_progress(row.get("Compliance checklist", "")),
                        "Milestone progress": milestone_progress(row.get("Milestones", "")),
                        "Duration weeks": phase["Duration weeks"],
                    }
                )
        else:
            start = pd.to_datetime(row["Start date"], errors="coerce")
            end = pd.to_datetime(row["Target completion"], errors="coerce")
            if pd.isna(start) or pd.isna(end):
                continue
            phase_rows.append(
                {
                    "Project phase": f"{row['Project name']} — {row['Stage']}",
                    "Project name": row["Project name"],
                    "Client": row["Client"],
                    "Location": row["Location"],
                    "Stage": row["Stage"],
                    "Status": row["Status"],
                    "Start date": start,
                    "Target completion": end,
                    "Budget": parse_budget(row["Budget"]),
                    "Compliance progress": compliance_progress(row.get("Compliance checklist", "")),
                    "Milestone progress": milestone_progress(row.get("Milestones", "")),
                    "Duration weeks": round((end - start).days / 7, 1),
                }
            )

    gantt = pd.DataFrame(phase_rows)
    if gantt.empty:
        return None

    gantt["Start date"] = pd.to_datetime(gantt["Start date"])
    gantt["Target completion"] = pd.to_datetime(gantt["Target completion"])
    gantt["mid"] = gantt["Start date"] + (gantt["Target completion"] - gantt["Start date"]) / 2

    unique_rows = gantt["Project phase"].nunique()
    per_row = 24
    height = max(180, min(1200, per_row * unique_rows))

    opacity = 0.75 if outlines else 1.0
    stroke = "black" if outlines else None
    stroke_width = 0.4 if outlines else 0.0

    base = (
        alt.Chart(gantt)
        .mark_bar(size=max(4, int(per_row * 0.8)), opacity=opacity, stroke=stroke, strokeWidth=stroke_width)
        .encode(
            x=alt.X("Start date:T", title="Start"),
            x2=alt.X2("Target completion:T", title="Finish"),
            y=alt.Y(
                "Project phase:N",
                sort=alt.SortField("Start date", order="descending"),
                title="Project / phase",
            ),
            color=alt.Color("Stage:N", legend=alt.Legend(title="Phase")),
            tooltip=[
                alt.Tooltip("Project name:N"),
                alt.Tooltip("Project phase:N"),
                alt.Tooltip("Client:N"),
                alt.Tooltip("Location:N"),
                alt.Tooltip("Stage:N"),
                alt.Tooltip("Status:N"),
                alt.Tooltip("Budget:Q", format="$,.2f"),
                alt.Tooltip("Compliance progress:Q", format=".0f"),
                alt.Tooltip("Milestone progress:Q", format=".0f"),
                alt.Tooltip("Duration weeks:Q", format=".1f"),
            ],
        )
    )

    text = (
        alt.Chart(gantt)
        .mark_text(fontSize=11, color="white", baseline="middle")
        .encode(
            x=alt.X("mid:T"),
            y=alt.Y("Project phase:N", sort=alt.SortField("Start date", order="descending")),
            text=alt.Text("Stage:N"),
        )
    )

    today_line = alt.Chart(pd.DataFrame({"today": [pd.Timestamp.now().normalize()]})).mark_rule(color="red", strokeDash=[4, 4], size=2).encode(
        x=alt.X("today:T")
    )

    return alt.layer(base, text, today_line).properties(height=height)


st.set_page_config(page_title=PAGE_TITLE, layout="wide")
st.title("🏢 Commercial Fitout Project Tracker")
st.markdown(
    "Use this workspace tracker to add new fitout projects, update stages, monitor risk status, and track progress from concept through to code compliance."
)

if "projects" not in st.session_state:
    st.session_state.projects = load_projects()

if "team_members" not in st.session_state:
    st.session_state.team_members = load_team_members()

if "tasks" not in st.session_state:
    st.session_state.tasks = load_tasks()

if "message" not in st.session_state:
    st.session_state.message = ""

with st.sidebar:
    page = st.selectbox("Page", ["Project Tracker", "Task Tracker"])
    if page == "Project Tracker":
        st.header("Project filters")
        selected_stages = st.multiselect("Stage", STAGES, default=STAGES)
        selected_status = st.multiselect("Status", STATUSES, default=STATUSES)
        search_query = st.text_input("Search by project, client, or location")
        st.markdown("---")
        st.subheader("Quick status view")
        status_quick = st.selectbox("Show projects by status", ["All"] + STATUSES, index=0)
        if status_quick == "All":
            projects_by_status = st.session_state.projects["Project name"].dropna().unique().tolist()
        else:
            projects_by_status = (
                st.session_state.projects[st.session_state.projects["Status"] == status_quick]["Project name"]
                .dropna()
                .unique()
                .tolist()
            )
        selected_quick = st.selectbox("Projects in this status", [""] + projects_by_status, key="sidebar_project_select")
        if selected_quick:
            st.session_state.quick_selected_project = selected_quick
            st.markdown("---")
            st.subheader("Quick actions")
            if st.button("Jump to edit", key=f"jump_{selected_quick}"):
                st.session_state.quick_selected_project = selected_quick
                st.experimental_rerun()
            if st.button("Open notes", key=f"notes_{selected_quick}"):
                st.session_state.show_notes_for = selected_quick
                st.experimental_rerun()

            project_row = st.session_state.projects[st.session_state.projects["Project name"] == selected_quick]
            if not project_row.empty:
                current_milestones = project_row.iloc[0].get("Milestones", "")
            else:
                current_milestones = ""
            milestone_list = parse_milestones(current_milestones)
            if milestone_list:
                st.write("**Manage milestones**")
                milestone_states = []
                for i, m in enumerate(milestone_list):
                    clean = m.replace("✓", "").strip()
                    checked = (
                        m.endswith("✓")
                        or m.startswith("[x]")
                        or m.startswith("[X]")
                        or m.lower().endswith("complete")
                    )
                    cb = st.checkbox(clean, value=checked, key=f"milestone_{selected_quick}_{i}")
                    milestone_states.append((clean, cb))
                if st.button("Save milestones", key=f"save_milestones_{selected_quick}"):
                    new_list = []
                    for text, checked in milestone_states:
                        if checked:
                            new_list.append(text + " ✓")
                        else:
                            new_list.append(text)
                    idx = st.session_state.projects[st.session_state.projects["Project name"] == selected_quick].index[0]
                    st.session_state.projects.at[idx, "Milestones"] = normalize_milestones("\n".join(new_list))
                    save_projects(st.session_state.projects)
                    st.success("Milestones saved")
                    st.experimental_rerun()
        st.markdown("---")
        st.write("**Project insights**")
        total_projects = len(st.session_state.projects)
        total_budget = st.session_state.projects["Budget"].apply(parse_budget).sum()
        average_compliance = (
            st.session_state.projects["Compliance checklist"].apply(compliance_progress).mean()
            if total_projects
            else 0
        )
        average_milestones = (
            st.session_state.projects["Milestones"].apply(milestone_progress).mean()
            if total_projects
            else 0
        )
        st.metric("Total projects", total_projects)
        st.metric("Total budget", format_budget(total_budget))
        st.metric("Average compliance progress", f"{int(average_compliance)}%")
        st.metric("Average milestone completion", f"{int(average_milestones)}%")
        status_counts = st.session_state.projects["Status"].value_counts().to_dict()
        for status in STATUSES:
            st.write(f"- {status}: {status_counts.get(status, 0)}")
    else:
        st.header("Task tracker filters")
        task_project_options = ["All projects"] + st.session_state.projects["Project name"].dropna().unique().tolist()
        selected_task_project = st.selectbox("Project", task_project_options, index=0, key="task_project_select")
        task_team_filter = st.multiselect("Team", TASK_TEAMS, default=TASK_TEAMS, key="task_team_filter")
        task_status_filter = st.multiselect("Status", TASK_STATUSES, default=TASK_STATUSES, key="task_status_filter")
        st.markdown("---")
        st.write("**Task board insights**")
        total_tasks = len(st.session_state.tasks)
        st.metric("Total tasks", total_tasks)
        status_counts = st.session_state.tasks["Status"].value_counts().to_dict()
        for status in TASK_STATUSES:
            st.write(f"- {status}: {status_counts.get(status, 0)}")

if page == "Project Tracker":
    filtered_projects = filter_projects(st.session_state.projects, selected_stages, selected_status, search_query)
    filtered_projects_display = filtered_projects.copy()
    filtered_projects_display["Compliance progress"] = filtered_projects_display["Compliance checklist"].apply(compliance_progress)
    filtered_projects_display["Milestone progress"] = filtered_projects_display["Milestones"].apply(milestone_progress)
    filtered_projects_display["Budget"] = filtered_projects_display["Budget"].apply(format_budget)

    left, right = st.columns([2, 1])

    with left:
        st.subheader("Active projects")
        if filtered_projects_display.empty:
            st.info("No projects match the selected filters yet.")
        else:
            st.dataframe(
                filtered_projects_display[COLUMNS + ["Compliance progress", "Milestone progress"]].fillna(""),
                use_container_width=True,
            )

        st.markdown("---")
        st.subheader("Project Gantt chart")
        outline_toggle = st.checkbox("Outline phase bars", value=True)
        gantt_chart = build_gantt_chart(filtered_projects, outlines=outline_toggle)
        if gantt_chart is not None:
            st.altair_chart(gantt_chart, use_container_width=True)
        else:
            st.info("Add project start and target completion dates to see the Gantt chart.")

        st.markdown("---")
        st.subheader("Add a new project")
        with st.form("new_project_form"):
            new_project_id = st.text_input(
                "Project ID",
                help="Enter a unique project identifier. Leave blank to auto-generate.",
                max_chars=100,
            )
            new_name = st.text_input("Project name", max_chars=100)
            new_client = st.text_input("Client")
            new_location = st.text_input("Location")
            new_manager = st.text_input("Project manager")
            col1, col2 = st.columns([1, 1])
            with col1:
                new_start = st.date_input("Start date")
            with col2:
                new_target = st.date_input("Target completion")
            new_stage = st.selectbox("Stage", STAGES, index=0)
            new_status = st.selectbox("Status", STATUSES, index=0)
            new_budget = st.number_input("Budget", min_value=0.0, step=100.0, format="%f")
            new_weekly_hours = st.number_input(
                "Weekly hours allocated",
                min_value=0.0,
                step=1.0,
                value=0.0,
                help="Enter the total weekly hours allocated to this project.",
            )
            new_member_hours = st.text_area(
                "Member hours allocation",
                help="Enter one member and hours per line, e.g. Alice: 12\nBob: 8. Leave empty to split total weekly hours evenly.",
                height=120,
            )
            new_phase_schedule = st.text_area(
                "Phase schedule",
                help="Enter one phase per line, e.g. Concept: 2026-05-01 to 2026-05-28",
                height=120,
            )
            new_milestones = st.text_area(
                "Milestones",
                help="Enter one milestone per line. Add ✓ or [x] to mark a milestone complete.",
                height=140,
            )
            new_team_members = st.multiselect("Team members", st.session_state.team_members)
            new_compliance = st.multiselect("Compliance checklist", COMPLIANCE_TASKS)
            new_notes = st.text_area("Notes", height=120)
            submit_new = st.form_submit_button("Save project")

            if submit_new:
                if not new_name:
                    st.warning("Please enter a project name before saving.")
                else:
                    project_data = {
                        "Project ID": new_project_id,
                        "Project name": new_name,
                        "Client": new_client,
                        "Location": new_location,
                        "Project manager": new_manager,
                        "Start date": new_start.strftime("%Y-%m-%d"),
                        "Target completion": new_target.strftime("%Y-%m-%d"),
                        "Stage": new_stage,
                        "Status": new_status,
                        "Budget": str(new_budget),
                        "Weekly hours allocated": str(new_weekly_hours),
                        "Member hours allocation": normalize_member_hours(parse_member_hours(new_member_hours)),
                        "Phase schedule": normalize_phase_schedule(new_phase_schedule),
                        "Milestones": normalize_milestones(new_milestones),
                        "Team members": normalize_team_members(new_team_members),
                        "Compliance checklist": normalize_checklist(new_compliance),
                        "Notes": new_notes,
                    }
                    st.session_state.projects = add_or_update_project(project_data, st.session_state.projects)
                    save_projects(st.session_state.projects)
                    st.session_state.message = f"Saved project '{new_name}'."
                    st.experimental_rerun()

    with right:
        st.subheader("Update an existing project")
        project_names = st.session_state.projects["Project name"].dropna().unique().tolist()
        default_selected = st.session_state.get("quick_selected_project", "")
        options = [""] + project_names
        try:
            default_index = options.index(default_selected)
        except ValueError:
            default_index = 0
        selected = st.selectbox("Select a project", options, index=default_index)
        if selected:
            project_index = st.session_state.projects[st.session_state.projects["Project name"] == selected].index[0]
            current = st.session_state.projects.loc[project_index].to_dict()
            if st.session_state.get("show_notes_for") == selected:
                st.subheader("Project notes")
                st.info(current.get("Notes", "(no notes)"))
                if st.button("Close notes", key=f"close_notes_{selected}"):
                    st.session_state.show_notes_for = None
                    st.experimental_rerun()
            current_compliance = compliance_to_list(current.get("Compliance checklist", ""))
            current_team_members = parse_team_members(current.get("Team members", ""))
            current_member_hours = current.get("Member hours allocation", "")
            with st.form("edit_project_form"):
                st.text_input("Project ID", value=current.get("Project ID", ""), disabled=True)
                edit_client = st.text_input("Client", value=current.get("Client", ""))
                edit_location = st.text_input("Location", value=current.get("Location", ""))
                edit_manager = st.text_input("Project manager", value=current.get("Project manager", ""))
                edit_team_members = st.multiselect(
                    "Team members",
                    st.session_state.team_members,
                    default=current_team_members,
                )
                col1, col2 = st.columns([1, 1])
                with col1:
                    edit_start = st.date_input(
                        "Start date",
                        value=parse_date(current.get("Start date"), fallback=pd.Timestamp.now().date()),
                    )
                with col2:
                    edit_target = st.date_input(
                        "Target completion",
                        value=parse_date(current.get("Target completion"), fallback=pd.Timestamp.now().date()),
                    )
                edit_stage = st.selectbox(
                    "Stage",
                    STAGES,
                    index=STAGES.index(current.get("Stage")) if current.get("Stage") in STAGES else 0,
                )
                edit_status = st.selectbox(
                    "Status",
                    STATUSES,
                    index=STATUSES.index(current.get("Status")) if current.get("Status") in STATUSES else 0,
                )
                edit_budget = st.number_input(
                    "Budget",
                    min_value=0.0,
                    step=100.0,
                    value=parse_budget(current.get("Budget", "0")),
                    format="%f",
                )
                edit_weekly_hours = st.number_input(
                    "Weekly hours allocated",
                    min_value=0.0,
                    step=1.0,
                    value=parse_weekly_hours(current.get("Weekly hours allocated", "0")),
                    help="Enter the total weekly hours allocated to this project.",
                )
                edit_member_hours = st.text_area(
                    "Member hours allocation",
                    value=current_member_hours,
                    help="Enter one member and hours per line, e.g. Alice: 12\nBob: 8. Leave empty to split total weekly hours evenly.",
                    height=120,
                )
                edit_phase_schedule = st.text_area(
                    "Phase schedule",
                    value=current.get("Phase schedule", ""),
                    help="Enter one phase per line, e.g. Concept: 2026-05-01 to 2026-05-28",
                    height=120,
                )
                edit_milestones = st.text_area(
                    "Milestones",
                    value=current.get("Milestones", ""),
                    help="Enter one milestone per line. Add ✓ or [x] to mark a milestone complete.",
                    height=140,
                )
                edit_compliance = st.multiselect(
                    "Compliance checklist",
                    COMPLIANCE_TASKS,
                    default=current_compliance,
                )
                edit_notes = st.text_area("Notes", value=current.get("Notes", ""), height=140)
                st.write(f"Stage progress: {stage_progress(current.get('Stage'))}%")
                st.progress(stage_progress(current.get('Stage')))
                st.write(f"Compliance progress: {compliance_progress(current.get('Compliance checklist', ''))}%")
                st.write(f"Milestone completion: {milestone_progress(current.get('Milestones', ''))}%")
                update_button = st.form_submit_button("Update project")
                delete_button = st.form_submit_button("Delete project")
                if update_button:
                    updated_data = {
                        "Project ID": current.get("Project ID", ""),
                        "Project name": selected,
                        "Client": edit_client,
                        "Location": edit_location,
                        "Project manager": edit_manager,
                        "Start date": edit_start.strftime("%Y-%m-%d"),
                        "Target completion": edit_target.strftime("%Y-%m-%d"),
                        "Stage": edit_stage,
                        "Status": edit_status,
                        "Budget": str(edit_budget),
                        "Weekly hours allocated": str(edit_weekly_hours),
                        "Member hours allocation": normalize_member_hours(parse_member_hours(edit_member_hours)),
                        "Phase schedule": normalize_phase_schedule(edit_phase_schedule),
                        "Milestones": normalize_milestones(edit_milestones),
                        "Team members": normalize_team_members(edit_team_members),
                        "Compliance checklist": normalize_checklist(edit_compliance),
                        "Notes": edit_notes,
                    }
                    st.session_state.projects = add_or_update_project(updated_data, st.session_state.projects)
                    save_projects(st.session_state.projects)
                    st.session_state.message = f"Updated project '{selected}'."
                    st.experimental_rerun()
                if delete_button:
                    st.session_state.projects = st.session_state.projects[st.session_state.projects["Project name"] != selected]
                    save_projects(st.session_state.projects)
                    st.session_state.message = f"Deleted project '{selected}'."
                    st.experimental_rerun()

    st.markdown("---")
    st.subheader("Team member management")
    with st.form("team_member_form"):
        new_member = st.text_input("Add team member")
        add_member = st.form_submit_button("Add team member")
        if add_member:
            member_name = new_member.strip()
            if not member_name:
                st.warning("Please enter a team member name.")
            elif member_name in st.session_state.team_members:
                st.warning("This team member already exists.")
            else:
                st.session_state.team_members.append(member_name)
                save_team_members(st.session_state.team_members)
                st.success(f"Added team member '{member_name}'.")
                st.experimental_rerun()

    st.write("**Defined team members**")
    if st.session_state.team_members:
        st.write(", ".join(st.session_state.team_members))
    else:
        st.info("No team members defined yet.")

    weekly_capacity = st.number_input(
        "Weekly capacity per team member",
        min_value=1.0,
        value=40.0,
        step=1.0,
        help="Weekly working hours available for each staff member.",
    )
    workload_df = compute_team_member_hours(st.session_state.projects, st.session_state.team_members, weekly_capacity)
    if not workload_df.empty:
        styled = workload_df.style.apply(style_workload_table, axis=1)
        st.dataframe(styled, use_container_width=True)
        overloaded = workload_df[workload_df["Available hours"] < 10]
        if not overloaded.empty:
            st.warning(
                "Swamped team members: " + ", ".join(overloaded["Team member"].tolist())
            )
    else:
        st.info("No team members or project hours assigned yet.")

else:
    selected_project = st.session_state.get("task_project_select", "All projects")
    selected_teams = st.session_state.get("task_team_filter", TASK_TEAMS)
    selected_statuses = st.session_state.get("task_status_filter", TASK_STATUSES)

    task_query = st.text_input("Search tasks by name, project, or assignee")
    task_df = st.session_state.tasks.copy()
    if selected_project and selected_project != "All projects":
        task_df = task_df[task_df["Project name"] == selected_project]
    if selected_teams:
        task_df = task_df[task_df["Team"].isin(selected_teams)]
    if selected_statuses:
        task_df = task_df[task_df["Status"].isin(selected_statuses)]
    if task_query:
        query = task_query.lower()
        task_df = task_df[
            task_df["Task name"].str.lower().str.contains(query, na=False)
            | task_df["Project name"].str.lower().str.contains(query, na=False)
            | task_df["Assigned to"].str.lower().str.contains(query, na=False)
        ]

    st.subheader("Project task tracker")
    if task_df.empty:
        st.info("No tasks match the selected filters yet.")
    else:
        st.dataframe(task_df[TASK_COLUMNS].fillna(""), use_container_width=True)

    st.markdown("---")
    st.subheader("Update a task")
    task_ids = [""] + task_df["Task ID"].tolist()
    selected_task_id = st.selectbox("Select a task", task_ids)
    if selected_task_id:
        selected_task = task_df[task_df["Task ID"] == selected_task_id].iloc[0]
        with st.form("edit_task_form"):
            st.text_input("Task ID", value=selected_task_id, disabled=True)
            st.text_input("Project", value=selected_task["Project name"], disabled=True)
            edit_task_name = st.text_input("Task name", value=selected_task["Task name"])
            edit_team = st.selectbox(
                "Team",
                TASK_TEAMS,
                index=TASK_TEAMS.index(selected_task["Team"]) if selected_task["Team"] in TASK_TEAMS else 0,
            )
            edit_assigned = st.multiselect(
                "Assigned to",
                st.session_state.team_members,
                default=[member.strip() for member in str(selected_task["Assigned to"]).split(";") if member.strip()],
            )
            edit_status = st.selectbox(
                "Status",
                TASK_STATUSES,
                index=TASK_STATUSES.index(selected_task["Status"]) if selected_task["Status"] in TASK_STATUSES else 0,
            )
            edit_notes = st.text_area("Notes", value=selected_task["Notes"], height=120)
            update_task = st.form_submit_button("Update task")
            delete_task = st.form_submit_button("Delete task")
            if update_task:
                updated_task = {
                    "Task ID": selected_task_id,
                    "Project ID": selected_task["Project ID"],
                    "Project name": selected_task["Project name"],
                    "Task name": edit_task_name,
                    "Team": edit_team,
                    "Assigned to": "; ".join(edit_assigned),
                    "Status": edit_status,
                    "Notes": edit_notes,
                }
                st.session_state.tasks = add_or_update_task(updated_task, st.session_state.tasks)
                save_tasks(st.session_state.tasks)
                st.success(f"Updated task '{edit_task_name}'.")
                st.experimental_rerun()
            if delete_task:
                st.session_state.tasks = st.session_state.tasks[st.session_state.tasks["Task ID"] != selected_task_id]
                save_tasks(st.session_state.tasks)
                st.success(f"Deleted task '{selected_task['Task name']}'.")
                st.experimental_rerun()

    st.markdown("---")
    st.subheader("Add a new task")
    with st.form("new_task_form"):
        task_project = st.selectbox("Project", [""] + st.session_state.projects["Project name"].dropna().unique().tolist())
        task_name = st.text_input("Task name")
        task_team = st.selectbox("Team", TASK_TEAMS)
        task_assigned = st.multiselect("Assigned to", st.session_state.team_members)
        task_status = st.selectbox("Status", TASK_STATUSES, index=0)
        task_notes = st.text_area("Notes", height=120)
        add_task_button = st.form_submit_button("Create task")
        if add_task_button:
            if not task_project or not task_name:
                st.warning("Please select a project and enter a task name.")
            else:
                project_row = st.session_state.projects[st.session_state.projects["Project name"] == task_project]
                project_id = project_row.iloc[0]["Project ID"] if not project_row.empty else ""
                task_data = {
                    "Task ID": "",
                    "Project ID": project_id,
                    "Project name": task_project,
                    "Task name": task_name,
                    "Team": task_team,
                    "Assigned to": "; ".join(task_assigned),
                    "Status": task_status,
                    "Notes": task_notes,
                }
                st.session_state.tasks = add_or_update_task(task_data, st.session_state.tasks)
                save_tasks(st.session_state.tasks)
                st.success(f"Created task '{task_name}'.")
                st.experimental_rerun()

if st.session_state.message:
    st.success(st.session_state.message)

st.markdown("---")
st.download_button(
    label="Download project tracker CSV",
    data=st.session_state.projects.to_csv(index=False).encode("utf-8"),
    file_name="fitout_projects.csv",
    mime="text/csv",
)
