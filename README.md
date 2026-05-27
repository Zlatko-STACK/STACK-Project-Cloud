# Office Fitout Project Tracker

A Streamlit app for tracking your commercial interior office fitout projects from concept through to code of compliance.

## What it does

- Add new fitout projects with client, location, manager, dates, stage, status, budget, milestones, compliance checklist, and notes
- Update existing projects and move them through stages like Concept, Design Development, Tender, Construction, Handover, and Code of Compliance
- Track milestone completion progress for each project
- Define and plot detailed phase schedules for each project using date ranges
- Filter by stage and status, search by project/client/location
- Download the project tracker as a CSV file
- Persist project information locally in `projects.csv`
- View the project timeline in a Gantt-style chart
- Track budgets and compliance checklist progress

## Run locally

1. Install requirements

   ```bash
   pip install -r requirements.txt
   ```

2. Start the app

   ```bash
   streamlit run streamlit_app.py
   ```

## Notes

- Project data is saved to `projects.csv` in the repository root.
- The app supports basic project management and can be extended with timelines, budgets, or dependencies.

