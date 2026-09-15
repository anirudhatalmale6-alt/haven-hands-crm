"""
Haven Hands CRM - salary payment schedule engine.

The rules below are taken from Haven Hands' own SALARY PAYMENT SCHEDULE
(case 39, printed 10-09-2026). tests/test_salary.py reproduces
that document row for row, so this module is checked against the agency's
real paperwork rather than against an assumption about how it ought to work.

Rules, as the document actually behaves:

  Salary per day   basic salary / 26, TRUNCATED to cents (696.43/26 =
                   26.7857.. is shown and used as 26.78, not 26.79).

  Salary period    Payment n falls on the monthly anniversary of the
                   commencement date. The period it pays for ENDS on that
                   payment date and STARTS the day after the previous one:
                   commencement 11-09-2026 -> period 1 is 12 Sep .. 11 Oct.
                   This matters: it decides whether a month contains 4 or 5
                   Sundays, and so whether 2 or 3 off days are compensated.

  Off day comp     (rest days falling in the period - rest days actually
                   taken) x salary per day. Never negative.

  Placement loan   The agreed instalment is the fee spread over the agreed
                   number of months, but a single deduction is never more
                   than the basic salary - so the off day compensation
                   always reaches the helper. Whatever is left over runs
                   into an extra month as a smaller final instalment.

  Amount received  basic salary + off day comp - placement fee deduction.

All money is Decimal. Nothing is rounded mid-calculation.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field, asdict
from datetime import date, timedelta
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
from typing import Iterator

TWO_DP = Decimal("0.01")

SUNDAY = 6
WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday",
                 "Friday", "Saturday", "Sunday"]


def money(value) -> Decimal:
    """Round to cents, half-up - how a payslip rounds."""
    return Decimal(str(value)).quantize(TWO_DP, rounding=ROUND_HALF_UP)


def truncate_money(value) -> Decimal:
    """Cut to cents without rounding up. The daily rate is derived this way."""
    return Decimal(str(value)).quantize(TWO_DP, rounding=ROUND_DOWN)


def add_months(d: date, n: int) -> date:
    """Same day-of-month n months on, clamped into a short month.

    31 Jan + 1 month -> 28 Feb (29 Feb in a leap year). A commencement on
    the 29th, 30th or 31st needs this or the schedule throws in February.
    """
    year = d.year + (d.month - 1 + n) // 12
    month = (d.month - 1 + n) % 12 + 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def count_weekday(start: date, end: date, weekday: int) -> int:
    """How many times `weekday` falls in [start, end], both ends inclusive."""
    if end < start:
        return 0
    first = start + timedelta(days=(weekday - start.weekday()) % 7)
    if first > end:
        return 0
    return (end - first).days // 7 + 1


# --------------------------------------------------------------------------
# Inputs
# --------------------------------------------------------------------------

@dataclass
class SalaryTerms:
    """The header block of a Haven Hands salary payment schedule."""

    basic_salary: Decimal
    commencement_date: date

    # "Day Off Per Month" on the schedule: rest days the helper actually
    # takes. Everything above this that falls in the period is compensated.
    days_off_per_month: int = 2

    # The contractual rest day. Sunday on every schedule seen so far, but
    # the Weekly Rest Day Agreement template lets it be any day.
    rest_day_weekday: int = SUNDAY

    total_placement_fee: Decimal = Decimal("0")
    loan_months: int = 0                  # agreed number of instalments

    contract_months: int = 24
    salary_divisor: Decimal = Decimal("26")

    # 'truncate' reproduces Haven Hands' schedules (26.7857 -> 26.78).
    daily_rate_rounding: str = "truncate"

    # A rounding remainder smaller than this is added to the last full
    # instalment instead of becoming a row of its own. 0 = off, which is
    # what Haven Hands' own schedule does (it shows a 14.28 final row).
    final_stub_sweep: Decimal = Decimal("0")

    # Rest days worked beyond the regular pattern, {period_number: days}.
    extra_rest_days_worked: dict[int, int] = field(default_factory=dict)

    @property
    def daily_rate(self) -> Decimal:
        raw = Decimal(str(self.basic_salary)) / Decimal(str(self.salary_divisor))
        if self.daily_rate_rounding == "truncate":
            return truncate_money(raw)
        return money(raw)


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------

@dataclass
class SchedulePeriod:
    number: int
    period_start: date
    period_end: date
    payment_date: date
    rest_days_in_period: int
    rest_days_taken: int
    off_days_compensated: int
    basic_salary: Decimal
    off_day_comp: Decimal
    placement_fee_deduction: Decimal
    amount_received: Decimal
    loan_balance_before: Decimal
    loan_balance_after: Decimal
    is_final_instalment: bool
    remarks: str = ""

    def as_row(self) -> dict:
        row = asdict(self)
        for k, v in row.items():
            if isinstance(v, Decimal):
                row[k] = f"{v:.2f}"
            elif isinstance(v, date):
                row[k] = v.isoformat()
        return row


# --------------------------------------------------------------------------
# Schedule
# --------------------------------------------------------------------------

def salary_periods(terms: SalaryTerms) -> Iterator[tuple[int, date, date]]:
    """Yield (n, period_start, payment_date) for each month of the contract."""
    for n in range(1, terms.contract_months + 1):
        payment_date = add_months(terms.commencement_date, n)
        period_start = add_months(terms.commencement_date, n - 1) + timedelta(days=1)
        yield n, period_start, payment_date


def planned_instalment(terms: SalaryTerms) -> Decimal:
    """The agreed monthly deduction before the basic-salary cap is applied."""
    fee = Decimal(str(terms.total_placement_fee))
    if fee <= 0 or terms.loan_months <= 0:
        return Decimal("0")
    return money(fee / Decimal(terms.loan_months))


def build_schedule(terms: SalaryTerms) -> list[SchedulePeriod]:
    basic = money(terms.basic_salary)
    rate = terms.daily_rate
    instalment = planned_instalment(terms)
    balance = money(terms.total_placement_fee)
    rows: list[SchedulePeriod] = []

    for n, p_start, pay_date in salary_periods(terms):
        rest_days = count_weekday(p_start, pay_date, terms.rest_day_weekday)
        taken = terms.days_off_per_month
        compensated = max(0, rest_days - taken) + terms.extra_rest_days_worked.get(n, 0)
        comp = money(rate * compensated)

        balance_before = balance
        deduction = Decimal("0")
        final = False

        if balance > 0 and instalment > 0:
            # The deduction never touches the off day compensation, so it is
            # capped at the basic salary however large the agreed instalment.
            deduction = min(instalment, basic, balance)
            if Decimal("0") < balance - deduction <= terms.final_stub_sweep:
                deduction = min(balance, basic)
            deduction = money(deduction)
            balance = money(balance - deduction)
            final = balance == 0

        received = money(basic + comp - deduction)

        remarks = []
        if rest_days != 4:
            remarks.append(f"{rest_days} {WEEKDAY_NAMES[terms.rest_day_weekday]}s this period")
        if final and deduction < instalment:
            remarks.append("Final instalment - balance of placement fee")
        elif final:
            remarks.append("Placement fee fully repaid")

        rows.append(SchedulePeriod(
            number=n,
            period_start=p_start,
            period_end=pay_date,
            payment_date=pay_date,
            rest_days_in_period=rest_days,
            rest_days_taken=taken,
            off_days_compensated=compensated,
            basic_salary=basic,
            off_day_comp=comp,
            placement_fee_deduction=deduction,
            amount_received=received,
            loan_balance_before=money(balance_before),
            loan_balance_after=money(balance),
            is_final_instalment=final,
            remarks="; ".join(remarks),
        ))

    return rows


def schedule_totals(rows: list[SchedulePeriod]) -> dict:
    return {
        "months": len(rows),
        "total_basic": money(sum(r.basic_salary for r in rows)),
        "total_off_day_comp": money(sum(r.off_day_comp for r in rows)),
        "total_placement_fee": money(sum(r.placement_fee_deduction for r in rows)),
        "total_received": money(sum(r.amount_received for r in rows)),
        "balance_outstanding": rows[-1].loan_balance_after if rows else money(0),
        "loan_cleared_in_month": next(
            (r.number for r in rows if r.is_final_instalment), None),
    }
