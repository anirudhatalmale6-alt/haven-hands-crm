"""
Document generation.

Renders a Haven Hands document from case data and prints it to PDF through
headless Chromium, so what the CRM shows on screen and what comes out of the
printer are produced from the same HTML.
"""

from __future__ import annotations

import pathlib
import tempfile

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .salary import SalaryTerms, build_schedule, schedule_totals

ROOT = pathlib.Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "templates"

AGENCY = {
    "ea_licence": "25C3257",
    "ea_rep_name": "Sarah Magnus",
    "ea_rep_reg_no": "R1549677",
}

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES)),
    autoescape=select_autoescape(["html"]),
)


def render_salary_schedule_html(terms: SalaryTerms, employer_name: str,
                                fdw_name: str, **overrides) -> str:
    rows = build_schedule(terms)
    context = dict(AGENCY)
    context.update(
        terms=terms, rows=rows, totals=schedule_totals(rows),
        employer_name=employer_name, fdw_name=fdw_name,
    )
    context.update(overrides)
    return _env.get_template("salary_schedule_pdf.html").render(**context)


def html_to_pdf(html: str, out_path: str) -> str:
    """Print HTML to PDF with headless Chromium."""
    from playwright.sync_api import sync_playwright

    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False,
                                     encoding="utf-8") as fh:
        fh.write(html)
        src = fh.name

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(f"file://{src}", wait_until="load")
            page.pdf(path=out_path, format="A4", print_background=True,
                     margin={"top": "12mm", "bottom": "12mm",
                             "left": "10mm", "right": "10mm"})
            browser.close()
    finally:
        pathlib.Path(src).unlink(missing_ok=True)
    return out_path


def salary_schedule_pdf(terms: SalaryTerms, employer_name: str,
                        fdw_name: str, out_path: str, **overrides) -> str:
    return html_to_pdf(
        render_salary_schedule_html(terms, employer_name, fdw_name, **overrides),
        out_path)
