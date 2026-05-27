from pathlib import Path
import re
import uuid

import altair as alt
import pandas as pd
import streamlit as st

PAGE_TITLE = "Office Fitout Project Tracker"
DATA_FILE = Path(__file__).parent / "projects.csv"

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
    "Phase schedule",
    "Milestones",
    "Compliance checklist",
    "Notes",
    "Last updated",
]


def ensure_data_file():
    if not DATA_FILE.exists():
        pd.DataFrame(columns=COLUMNS).to_csv(DATA_FILE, index=False)


def parse_budget(value):
    if pd.isna(value) or value == "":
        return 0.0
    try:
        return float(str(value).replace(",", "").replace("$", "").strip())
    except ValueError:
        return 0.0


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


def format_budget(value):
    budget = parse_budget(value)
    return f"${budget:,.2f}" if budget else ""


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


def ensure_required_columns(df: pd.DataFrame):
    for column in COLUMNS:
        if column not in df.columns:
            df[column] = ""
    return df[COLUMNS]


def ensure_date_columns(df: pd.DataFrame):
    for date_col in ["Start date", "Target completion"]:
        if date_col in df.columns:
            df[date_col] = df[date_col].fillna("")
    return df


def load_projects():
    ensure_data_file()
    df = pd.read_csv(DATA_FILE, dtype=str)
    df = ensure_required_columns(df)
    df = ensure_date_columns(df)
    return df


def save_projects(df: pd.DataFrame):
    df.to_csv(DATA_FILE, index=False)


def create_project_id() -> str:
    return uuid.uuid4().hex[:8]


def add_or_update_project(data: dict, df: pd.DataFrame) -> pd.DataFrame:
    existing = df[df["Project name"] == data["Project name"]]
    data["Last updated"] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")

    if not existing.empty:
        index = existing.index[0]
        for key, value in data.items():
            df.at[index, key] = value
    else:
        data["Project ID"] = create_project_id()
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


def build_gantt_chart(df: pd.DataFrame):
    phase_rows = []
    for _, row in df.iterrows():
        phases = parse_phase_schedule(row.get("Phase schedule", ""))
        if phases:
            for phase in phases:
                phase_rows.append(
                    {
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

    # compute midpoint for text labels
    gantt["Start date"] = pd.to_datetime(gantt["Start date"])
    gantt["Target completion"] = pd.to_datetime(gantt["Target completion"])
    gantt["mid"] = gantt["Start date"] + (gantt["Target completion"] - gantt["Start date"]) / 2

    base = (
        alt.Chart(gantt)
        .mark_bar(size=18)
        .encode(
            x=alt.X("Start date:T", title="Start"),
            x2=alt.X2("Target completion:T", title="Finish"),
            y=alt.Y(
                "Project name:N",
                sort=alt.SortField("Start date", order="descending"),
                title="Project",
            ),
            color=alt.Color("Stage:N", legend=alt.Legend(title="Phase")),
            tooltip=[
                alt.Tooltip("Project name:N"),
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
            y=alt.Y("Project name:N", sort=alt.SortField("Start date", order="descending")),
            text=alt.Text("Stage:N"),
        )
    )

    chart = alt.layer(base, text).properties(height=400)
    return chart


st.set_page_config(page_title=PAGE_TITLE, layout="wide")
st.title("🏢 Commercial Fitout Project Tracker")
st.markdown(
    "Use this workspace tracker to add new fitout projects, update stages, monitor risk status, and track progress from concept through to code compliance."
)

if "projects" not in st.session_state:
    st.session_state.projects = load_projects()

if "message" not in st.session_state:
    st.session_state.message = ""

with st.sidebar:
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

        # Milestone manager
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
    gantt_chart = build_gantt_chart(filtered_projects)
    if gantt_chart is not None:
        st.altair_chart(gantt_chart, use_container_width=True)
    else:
        st.info("Add project start and target completion dates to see the Gantt chart.")

    st.markdown("---")
    st.subheader("Add a new project")
    with st.form("new_project_form"):
        new_name = st.text_input("Project name", max_chars=100)
        new_client = st.text_input("Client")
        new_location = st.text_input("Location")
        new_manager = st.text_input("Project manager")
        col1, col2 = st.columns(2)
        with col1:
            new_start = st.date_input("Start date")
        with col2:
            new_target = st.date_input("Target completion")
        new_stage = st.selectbox("Stage", STAGES, index=0)
        new_status = st.selectbox("Status", STATUSES, index=0)
        new_budget = st.number_input("Budget", min_value=0.0, step=100.0, format="%f")
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
        new_compliance = st.multiselect("Compliance checklist", COMPLIANCE_TASKS)
        new_notes = st.text_area("Notes", height=120)
        submit_new = st.form_submit_button("Save project")

        if submit_new:
            if not new_name:
                st.warning("Please enter a project name before saving.")
            else:
                project_data = {
                    "Project name": new_name,
                    "Client": new_client,
                    "Location": new_location,
                    "Project manager": new_manager,
                    "Start date": new_start.strftime("%Y-%m-%d"),
                    "Target completion": new_target.strftime("%Y-%m-%d"),
                    "Stage": new_stage,
                    "Status": new_status,
                    "Budget": str(new_budget),
                    "Phase schedule": normalize_phase_schedule(new_phase_schedule),
                    "Milestones": normalize_milestones(new_milestones),
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
        # If sidebar requested to show notes for this project, display them
        if st.session_state.get("show_notes_for") == selected:
            st.subheader("Project notes")
            st.info(current.get("Notes", "(no notes)"))
            if st.button("Close notes", key=f"close_notes_{selected}"):
                st.session_state.show_notes_for = None
                st.experimental_rerun()
        current_compliance = compliance_to_list(current.get("Compliance checklist", ""))
        with st.form("edit_project_form"):
            edit_client = st.text_input("Client", value=current.get("Client", ""))
            edit_location = st.text_input("Location", value=current.get("Location", ""))
            edit_manager = st.text_input("Project manager", value=current.get("Project manager", ""))
            col1, col2 = st.columns(2)
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
            st.progress(stage_progress(current.get("Stage")))
            st.write(f"Compliance progress: {compliance_progress(current.get('Compliance checklist', ''))}%")
            st.write(f"Milestone completion: {milestone_progress(current.get('Milestones', ''))}%")
            update_button = st.form_submit_button("Update project")
            if update_button:
                updated_data = {
                    "Project name": selected,
                    "Client": edit_client,
                    "Location": edit_location,
                    "Project manager": edit_manager,
                    "Start date": edit_start.strftime("%Y-%m-%d"),
                    "Target completion": edit_target.strftime("%Y-%m-%d"),
                    "Stage": edit_stage,
                    "Status": edit_status,
                    "Budget": str(edit_budget),
                    "Phase schedule": normalize_phase_schedule(edit_phase_schedule),
                    "Milestones": normalize_milestones(edit_milestones),
                    "Compliance checklist": normalize_checklist(edit_compliance),
                    "Notes": edit_notes,
                }
                st.session_state.projects = add_or_update_project(updated_data, st.session_state.projects)
                save_projects(st.session_state.projects)
                st.session_state.message = f"Updated project '{selected}'."
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

