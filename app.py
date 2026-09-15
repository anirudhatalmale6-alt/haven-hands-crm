"""
Haven Hands CRM - salary payment schedule.

The calculation module, wrapped in a page so it can be driven with real case
figures. Rules are taken from Haven Hands' own salary payment schedules; see
havenhands/salary.py and tests/test_salary.py.
"""

from __future__ import annotations

import os
import tempfile
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from flask import Flask, Response, render_template, request

from havenhands.salary import (
    SalaryTerms, build_schedule, schedule_totals, planned_instalment,
    WEEKDAY_NAMES,
)
from havenhands.exports import schedule_to_xlsx, schedule_to_csv
from havenhands.documents import salary_schedule_pdf

app = Flask(__name__)

DEFAULTS = {
    "employer_name": "Employer Name",
    "fdw_name": "Helper Name",
    "basic_salary": "696.43",
    "commencement_date": "2026-09-11",
    "days_off_per_month": "2",
    "rest_day_weekday": "6",
    "total_placement_fee": "2800.00",
    "loan_months": "4",
    "contract_months": "24",
    "daily_rate_rounding": "truncate",
}


def _dec(raw, fallback="0") -> Decimal:
    try:
        return Decimal(str(raw).strip() or fallback)
    except (InvalidOperation, ValueError):
        return Decimal(fallback)


def _int(raw, fallback=0) -> int:
    try:
        return int(Decimal(str(raw).strip() or fallback))
    except (InvalidOperation, ValueError):
        return fallback


def _form() -> dict:
    data = dict(DEFAULTS)
    if request.method == "POST":
        for key in DEFAULTS:
            if key in request.form:
                data[key] = request.form[key]
    return data


def _terms(data: dict) -> SalaryTerms:
    try:
        start = datetime.strptime(data["commencement_date"], "%Y-%m-%d").date()
    except ValueError:
        start = date.today()
    return SalaryTerms(
        basic_salary=_dec(data["basic_salary"]),
        commencement_date=start,
        days_off_per_month=_int(data["days_off_per_month"], 2),
        rest_day_weekday=_int(data["rest_day_weekday"], 6) % 7,
        total_placement_fee=_dec(data["total_placement_fee"]),
        loan_months=_int(data["loan_months"], 0),
        contract_months=max(1, min(60, _int(data["contract_months"], 24))),
        daily_rate_rounding=data["daily_rate_rounding"],
    )


@app.route("/", methods=["GET", "POST"])
def index():
    data = _form()
    terms = _terms(data)
    rows = build_schedule(terms)
    return render_template(
        "schedule.html", data=data, terms=terms, rows=rows,
        totals=schedule_totals(rows), instalment=planned_instalment(terms),
        weekday_names=WEEKDAY_NAMES)


@app.route("/schedule.pdf", methods=["POST"])
def export_pdf():
    data = _form()
    terms = _terms(data)
    fd, path = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)
    salary_schedule_pdf(terms, data["employer_name"], data["fdw_name"], path)
    with open(path, "rb") as fh:
        payload = fh.read()
    os.unlink(path)
    name = f"salary-schedule-{data['fdw_name'].replace(' ', '-')}.pdf"
    return Response(payload, mimetype="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


@app.route("/export.xlsx", methods=["POST"])
def export_xlsx():
    data = _form()
    terms = _terms(data)
    rows = build_schedule(terms)
    fd, path = tempfile.mkstemp(suffix=".xlsx")
    os.close(fd)
    schedule_to_xlsx(rows, terms, data["employer_name"], data["fdw_name"], path)
    with open(path, "rb") as fh:
        payload = fh.read()
    os.unlink(path)
    name = f"salary-schedule-{data['fdw_name'].replace(' ', '-')}.xlsx"
    return Response(
        payload,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{name}"'})


@app.route("/export.csv", methods=["POST"])
def export_csv():
    data = _form()
    rows = build_schedule(_terms(data))
    name = f"salary-schedule-{data['fdw_name'].replace(' ', '-')}.csv"
    return Response(schedule_to_csv(rows), mimetype="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8201"))
    app.run(host="0.0.0.0", port=port, debug=False)
