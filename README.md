# Haven Hands CRM — salary payment schedule

The salary and placement-loan calculation module for Haven Hands Pte. Ltd.
(EA Licence 25C3257), with PDF / Excel / CSV output.

It reproduces the agency's existing SALARY PAYMENT SCHEDULE exactly. The
test suite is checked against a real schedule (case 39), row for
row and cent for cent.

## Running it on a Mac

You need Python 3.10 or newer. macOS ships with Python 3, so this is usually
just copy-and-paste into Terminal:

```sh
cd ~/Downloads/haven-hands-crm       # wherever you put this folder
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 -m playwright install chromium   # one-off, for PDF printing
python3 app.py
```

Then open <http://127.0.0.1:8201> in Safari or Chrome.

To stop it, press `Ctrl-C` in the Terminal window. To start it again later,
`cd` back into the folder and run:

```sh
source .venv/bin/activate
python3 app.py
```

## Checking the figures are right

```sh
python3 -m pytest tests/ -v
```

42 tests. They include a row-for-row reproduction of the agency's own
schedule, plus tests that deliberately break one rule at a time and assert
the schedule then stops matching — so a green run means the rules are
actually being exercised, not just that nothing crashed.

To compare a generated PDF against an original one:

```sh
python3 verify_against_original.py original.pdf generated.pdf
```

## The calculation rules

Taken from the agency's own schedules, not from assumption:

| Rule | Behaviour |
|---|---|
| Salary per day | basic ÷ 26, **truncated** to cents (696.43 ÷ 26 → 26.78, not 26.79) |
| Salary month | **ends on the payment date**, starts the day after the previous one — commencement 11-09-2026 makes month 1 run 12 Sep – 11 Oct |
| Off day compensation | (rest days falling in the period − rest days taken) × salary per day, never below zero |
| Placement loan | fee ÷ agreed months, but a single deduction never exceeds the basic salary, so off-day compensation always reaches the helper |
| Amount received | basic salary + off day compensation − placement fee deduction |

The salary-month boundary matters more than it looks: the obvious
alternative reading (11 Sep – 10 Oct) agrees with the agency's schedule in
16 of 24 months and is still wrong. It changes whether a month contains four
or five Sundays, and so whether two or three off days are compensated.

## Layout

```
havenhands/salary.py      the engine — the only place money is decided
havenhands/documents.py   Jinja → HTML → PDF via headless Chromium
havenhands/exports.py     Excel and CSV
app.py                    web interface
templates/                screen and print templates
tests/test_salary.py      checks against the agency's real schedule
```

## Still to build

Case and contract records, document generation from the 21 branded
templates, checklists, staff logins, search, export and backups.
