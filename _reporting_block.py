
# --- REPORTING ---------------------------------------------------------------
elif page == "Reporting":
    import calendar as _cal
    from io import BytesIO as _BytesIO
    st.header("Reporting")
    _ts = st.session_state.timesheets.copy()
    _members = st.session_state.members_df["Team member"].dropna().tolist() if "members_df" in st.session_state else []
    if _ts.empty or not _members:
        st.info("No timesheet data or team members available to report on yet.")
    else:
        _ts["_date"] = pd.to_datetime(_ts["Date"], errors="coerce")
        _ts = _ts.dropna(subset=["_date"])
        _ts["_month"] = _ts["_date"].dt.to_period("M")
        _periods = sorted(_ts["_month"].dropna().unique(), reverse=True)
        _period_labels = {p.strftime("%B %Y"): p for p in _periods}
        rc1, rc2 = st.columns(2)
        with rc1:
            sel_member = st.selectbox("Team member", _members, key="rep_member")
        with rc2:
            sel_month_label = st.selectbox("Month", list(_period_labels.keys()) or ["(no data)"], key="rep_month")
        sel_period = _period_labels.get(sel_month_label)
        rep = _ts[(_ts["Team member"] == sel_member) & (_ts["_month"] == sel_period)].copy()
        rep["_hours"] = rep["Hours"].apply(parse_budget)
        rep["_billable"] = ~rep["Project name"].isin(FIXED_TASK_NAMES)
        _proj = st.session_state.projects[["Project ID", "Client"]].drop_duplicates("Project ID") if "projects" in st.session_state else pd.DataFrame(columns=["Project ID", "Client"])
        _client_map = dict(zip(_proj["Project ID"].astype(str), _proj["Client"]))
        rows = []
        grp = rep.groupby(["Project ID", "Project name"], dropna=False)
        for (pid, pname), g in grp:
            bill = round(g.loc[g["_billable"], "_hours"].sum(), 2)
            nonbill = round(g.loc[~g["_billable"], "_hours"].sum(), 2)
            rows.append({"Job Code": str(pid), "Client": _client_map.get(str(pid), ""), "Job Name": pname, "Billable Hrs": bill, "Non-Bill Hrs": nonbill, "Total Hours": round(bill + nonbill, 2)})
        rep_df = pd.DataFrame(rows, columns=["Job Code", "Client", "Job Name", "Billable Hrs", "Non-Bill Hrs", "Total Hours"]).sort_values("Job Code").reset_index(drop=True)
        tot_bill = round(rep_df["Billable Hrs"].sum(), 2) if not rep_df.empty else 0.0
        tot_nonbill = round(rep_df["Non-Bill Hrs"].sum(), 2) if not rep_df.empty else 0.0
        tot_all = round(tot_bill + tot_nonbill, 2)
        _title = f"{sel_member.upper()} \u2014 TIME REPORT {sel_month_label.upper()}"
        st.markdown(f"<div style='background:#1f4e79;color:#fff;padding:14px;border-radius:6px 6px 0 0;text-align:center;font-family:Inter,sans-serif'><div style='font-size:20px;font-weight:700'>{_title}</div><div style='font-size:13px;opacity:.85;margin-top:4px'>Hours by Job</div></div>", unsafe_allow_html=True)
        if rep_df.empty:
            st.info("No hours logged for this person in the selected month.")
        else:
            disp = rep_df.copy()
            for c in ["Billable Hrs", "Non-Bill Hrs", "Total Hours"]:
                disp[c] = disp[c].map(lambda v: f"{v:.2f}")
            total_row = pd.DataFrame([{"Job Code": "TOTAL", "Client": "", "Job Name": "", "Billable Hrs": f"{tot_bill:.2f}", "Non-Bill Hrs": f"{tot_nonbill:.2f}", "Total Hours": f"{tot_all:.2f}"}])
            disp = pd.concat([disp, total_row], ignore_index=True)
            st.dataframe(disp, use_container_width=True, hide_index=True)
        def _build_excel():
            buf = _BytesIO()
            out = rep_df.copy()
            out.loc[len(out)] = ["TOTAL", "", "", tot_bill, tot_nonbill, tot_all]
            with pd.ExcelWriter(buf, engine="openpyxl") as xl:
                out.to_excel(xl, index=False, sheet_name="Hours by Job", startrow=2)
                ws = xl.sheets["Hours by Job"]
                ws.cell(row=1, column=1, value=_title)
            buf.seek(0)
            return buf.getvalue()
        def _build_pdf():
            from fpdf import FPDF
            pdf = FPDF(orientation="L", unit="mm", format="A4")
            pdf.add_page()
            pdf.set_fill_color(31, 78, 121); pdf.set_text_color(255, 255, 255)
            pdf.set_font("Helvetica", "B", 14)
            pdf.cell(0, 10, _title, ln=1, align="C", fill=True)
            pdf.set_font("Helvetica", "", 10)
            pdf.cell(0, 7, "Hours by Job", ln=1, align="C", fill=True)
            pdf.ln(3)
            headers = ["Job Code", "Client", "Job Name", "Billable Hrs", "Non-Bill Hrs", "Total Hours"]
            widths = [25, 60, 80, 35, 35, 35]
            pdf.set_text_color(0, 0, 0); pdf.set_font("Helvetica", "B", 9)
            pdf.set_fill_color(46, 117, 182); pdf.set_text_color(255, 255, 255)
            for h, w in zip(headers, widths):
                pdf.cell(w, 8, h, border=1, align="C", fill=True)
            pdf.ln()
            pdf.set_text_color(0, 0, 0); pdf.set_font("Helvetica", "", 9)
            for _, r in rep_df.iterrows():
                cells = [str(r["Job Code"]), str(r["Client"])[:32], str(r["Job Name"])[:44], f"{r['Billable Hrs']:.2f}", f"{r['Non-Bill Hrs']:.2f}", f"{r['Total Hours']:.2f}"]
                aligns = ["L", "L", "L", "R", "R", "R"]
                for c, w, a in zip(cells, widths, aligns):
                    pdf.cell(w, 7, c, border=1, align=a)
                pdf.ln()
            pdf.set_font("Helvetica", "B", 9); pdf.set_fill_color(31, 78, 121); pdf.set_text_color(255, 255, 255)
            tot_cells = ["TOTAL", "", "", f"{tot_bill:.2f}", f"{tot_nonbill:.2f}", f"{tot_all:.2f}"]
            for c, w, a in zip(tot_cells, widths, ["L", "L", "L", "R", "R", "R"]):
                pdf.cell(w, 8, c, border=1, align=a, fill=True)
            pdf.ln()
            return bytes(pdf.output())
        _fname = f"{sel_member.replace(' ', '_')}_TimeReport_{sel_month_label.replace(' ', '_')}"
        dc1, dc2 = st.columns(2)
        with dc1:
            st.download_button("\U0001F4C4 Download PDF", data=_build_pdf(), file_name=f"{_fname}.pdf", mime="application/pdf", use_container_width=True, disabled=rep_df.empty)
        with dc2:
            st.download_button("\U0001F4CA Download Excel", data=_build_excel(), file_name=f"{_fname}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True, disabled=rep_df.empty)

