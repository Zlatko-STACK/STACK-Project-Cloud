"""Fee breakdown taxonomy + UI for the STACK Fee Estimator.

Defines the standard scope-of-work task breakdowns for each project phase
(based on the STACK fee breakdown spreadsheet). Each breakdown item can be
toggled on/off and customised (hours/role) per estimate. Selections persist
in estimate_lines via the existing data model:
    ESTIMATE_LINE_COLUMNS = [Line ID, Estimate ID, Phase, Role, Hours, Rate]
with the extra columns Task (breakdown name) and Active (on/off) added
lazily if missing.
"""

import pandas as pd
import streamlit as st

# Phase -> ordered list of standard breakdown tasks (from the spreadsheet).
BREAKDOWN_TASKS = {
    "Project Preliminaries": [
        "Project initiation and commencement",
        "Stakeholder meeting",
        "Review existing building information / aerial details",
        "Brief setup for the project",
        "Conduct site visit / scoping",
        "Initial client briefing meeting",
        "Prepare existing layout plans",
        "Prepare preliminary test fit / sample",
        "Personnel handover to iteration",
        "PM functions - programme and comms",
        "Preliminary cost estimate and markups",
        "Project PCG meetings",
    ],
    "Concept Design": [
        "Functional briefing",
        "Operational briefing",
        "AV briefing",
        "IT briefing",
        "Macro engagement / cultural briefing",
        "Sustainability briefing",
        "Layout refinement - sign off / development following review",
        "Concept design",
        "Renders",
        "Fly through",
        "Presentation",
        "Outline materials for sign off",
        "FF&E selection - product types, materials and finishes",
        "Updated preliminary cost estimate / PM functions from consultants",
        "Project PCG meetings",
    ],
    "Developed & Detailed Design": [
        "Prepare architectural drawings",
        "Run design coordination meetings with consultants",
        "FF&E materials reviews and update / PM jurisdictional procedures",
        "FF&E selection - confirm products and specifications",
        "FF&E selection - obtain sign offs and order confirmations",
        "Project PCG meetings",
    ],
    "Procurement and Council": [
        "Obtain landlord letter of approval / lodge with council for building",
        "Prepare and issue pricing documentation",
        "PM phasing / relocation programming",
        "PM review pricing and reconcile pricing / prepare analysis",
        "PM - liaise with landlord and pre-start",
        "NBS - SSSP",
        "FF&E selection - place FF&E orders / prepare FF&E tracker",
        "Project PCG meetings",
    ],
    "Construction Phase": [
        "Issue construction documents / attend start up meeting / site allowance",
        "PM pre-start and site commencement",
        "Run site construction meetings / administer the contract",
        "FF&E selection - receive FF&E and install",
        "Defecting",
        "Close out",
        "O&M documents",
        "Lodge CCC",
    ],
}


def _ensure_columns(df):
    """Add Task/Active columns to an estimate_lines DataFrame if missing."""
    if "Task" not in df.columns:
        df["Task"] = ""
    if "Active" not in df.columns:
        df["Active"] = True
    return df


def _to_float(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def render_fee_breakdown(act, role_rates, default_roles, save_estimate_lines, create_id):
    """Render the customisable, togglable fee breakdown for one estimate.

    Parameters
    ----------
    act : str               Active Estimate ID.
    role_rates : dict       Role -> hourly rate.
    default_roles : dict     DEFAULT_ROLES (role -> default rate).
    save_estimate_lines : callable  Persists st.session_state.estimate_lines.
    create_id : callable     Returns a new unique id string.
    """
    roles = list(default_roles.keys())
    st.session_state.estimate_lines = _ensure_columns(st.session_state.estimate_lines)
    lines = st.session_state.estimate_lines

    st.markdown("### Fee breakdown")
    st.caption("Toggle each task on/off and customise its role and hours. "
               "Disabled tasks are excluded from the fee total.")

    grand_active = 0.0
    for phase, tasks in BREAKDOWN_TASKS.items():
        phase_lines = lines[(lines["Estimate ID"] == act) & (lines["Phase"] == phase)]
        # Phase subtotal of currently active tasks.
        phase_total = 0.0
        for _, r in phase_lines.iterrows():
            if bool(r.get("Active", True)):
                phase_total += _to_float(r.get("Hours")) * _to_float(r.get("Rate"))
        grand_active += phase_total
        with st.expander(f"**{phase}**  -  ${phase_total:,.0f}", expanded=False):
            with st.form(key=f"breakdown_{act}_{phase}"):
                hc = st.columns([0.6, 4, 2, 1.4, 1.6])
                hc[0].markdown("**On**")
                hc[1].markdown("**Task**")
                hc[2].markdown("**Role**")
                hc[3].markdown("**Hours**")
                hc[4].markdown("**Line $**")
                inputs = {}
                for i, task in enumerate(tasks):
                    existing = phase_lines[phase_lines["Task"] == task]
                    has = not existing.empty
                    cur_active = bool(existing.iloc[0]["Active"]) if has else True
                    cur_role = existing.iloc[0]["Role"] if has and existing.iloc[0]["Role"] in roles else roles[0]
                    cur_hrs = _to_float(existing.iloc[0]["Hours"]) if has else 0.0
                    c = st.columns([0.6, 4, 2, 1.4, 1.6])
                    on = c[0].checkbox("", value=cur_active, key=f"on_{act}_{phase}_{i}", label_visibility="collapsed")
                    c[1].markdown(task)
                    role = c[2].selectbox("", roles, index=roles.index(cur_role),
                                          key=f"role_{act}_{phase}_{i}", label_visibility="collapsed")
                    hrs = c[3].number_input("", min_value=0.0, step=0.5, value=cur_hrs,
                                            key=f"hrs_{act}_{phase}_{i}", label_visibility="collapsed")
                    rate = _to_float(role_rates.get(role, default_roles.get(role, 0.0)))
                    line_val = (hrs * rate) if on else 0.0
                    c[4].markdown(f"${line_val:,.0f}" if on else "_off_")
                    inputs[task] = (on, role, hrs)
                if st.form_submit_button(f"Save {phase}", use_container_width=True):
                    df = st.session_state.estimate_lines
                    keep = ~((df["Estimate ID"] == act) & (df["Phase"] == phase))
                    df = df[keep]
                    new_rows = []
                    for task, (on, role, hrs) in inputs.items():
                        new_rows.append({
                            "Line ID": create_id(), "Estimate ID": act, "Phase": phase,
                            "Task": task, "Role": role, "Hours": hrs,
                            "Rate": _to_float(role_rates.get(role, default_roles.get(role, 0.0))),
                            "Active": bool(on),
                        })
                    st.session_state.estimate_lines = pd.concat(
                        [df, pd.DataFrame(new_rows)], ignore_index=True)
                    save_estimate_lines(st.session_state.estimate_lines)
                    st.rerun()
    st.markdown(f"**Breakdown total (active tasks): ${grand_active:,.0f}**")
