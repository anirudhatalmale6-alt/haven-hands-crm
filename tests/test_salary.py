"""
Checks against Haven Hands' own paperwork.

The golden case is the agency's SALARY PAYMENT SCHEDULE for case 39
(printed 10-09-2026), transcribed by hand from the
PDF below. It is an independent oracle: the figures were produced by Haven
Hands, not by this code, so it can genuinely fail.

Several tests deliberately break one rule at a time and assert the golden
case then STOPS matching - without those, a passing golden test would not
tell us which rules are actually load-bearing.
"""

import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from havenhands.salary import (  # noqa: E402
    SalaryTerms, build_schedule, schedule_totals, add_months, count_weekday,
    truncate_money, money,
)

# (month, payment date, basic, off day comp, placement fee, amount received)
GOLDEN_ROWS = [
    (1,  date(2026, 10, 11), "696.43", "80.34", "696.43",  "80.34"),
    (2,  date(2026, 11, 11), "696.43", "53.56", "696.43",  "53.56"),
    (3,  date(2026, 12, 11), "696.43", "53.56", "696.43",  "53.56"),
    (4,  date(2027,  1, 11), "696.43", "80.34", "696.43",  "80.34"),
    (5,  date(2027,  2, 11), "696.43", "53.56",  "14.28", "735.71"),
    (6,  date(2027,  3, 11), "696.43", "53.56",   "0.00", "749.99"),
    (7,  date(2027,  4, 11), "696.43", "80.34",   "0.00", "776.77"),
    (8,  date(2027,  5, 11), "696.43", "53.56",   "0.00", "749.99"),
    (9,  date(2027,  6, 11), "696.43", "53.56",   "0.00", "749.99"),
    (10, date(2027,  7, 11), "696.43", "80.34",   "0.00", "776.77"),
    (11, date(2027,  8, 11), "696.43", "53.56",   "0.00", "749.99"),
    (12, date(2027,  9, 11), "696.43", "53.56",   "0.00", "749.99"),
    (13, date(2027, 10, 11), "696.43", "80.34",   "0.00", "776.77"),
    (14, date(2027, 11, 11), "696.43", "53.56",   "0.00", "749.99"),
    (15, date(2027, 12, 11), "696.43", "53.56",   "0.00", "749.99"),
    (16, date(2028,  1, 11), "696.43", "80.34",   "0.00", "776.77"),
    (17, date(2028,  2, 11), "696.43", "53.56",   "0.00", "749.99"),
    (18, date(2028,  3, 11), "696.43", "53.56",   "0.00", "749.99"),
    (19, date(2028,  4, 11), "696.43", "80.34",   "0.00", "776.77"),
    (20, date(2028,  5, 11), "696.43", "53.56",   "0.00", "749.99"),
    (21, date(2028,  6, 11), "696.43", "80.34",   "0.00", "776.77"),
    (22, date(2028,  7, 11), "696.43", "53.56",   "0.00", "749.99"),
    (23, date(2028,  8, 11), "696.43", "53.56",   "0.00", "749.99"),
    (24, date(2028,  9, 11), "696.43", "80.34",   "0.00", "776.77"),
]

GOLDEN_TOTALS = {
    "basic": "16714.32",
    "off_day_comp": "1526.46",
    "placement_fee": "2800.00",
    "received": "15440.78",
}


def golden_terms(**kw) -> SalaryTerms:
    base = dict(
        basic_salary=Decimal("696.43"),
        commencement_date=date(2026, 9, 11),
        days_off_per_month=2,
        total_placement_fee=Decimal("2800.00"),
        loan_months=4,
        contract_months=24,
    )
    base.update(kw)
    return SalaryTerms(**base)


def actual_rows(terms: SalaryTerms):
    return [
        (r.number, r.payment_date, f"{r.basic_salary:.2f}", f"{r.off_day_comp:.2f}",
         f"{r.placement_fee_deduction:.2f}", f"{r.amount_received:.2f}")
        for r in build_schedule(terms)
    ]


# ------------------------------------------------- the agency's own schedule

def test_reproduces_the_agency_schedule_row_for_row():
    assert actual_rows(golden_terms()) == GOLDEN_ROWS


@pytest.mark.parametrize("row", GOLDEN_ROWS, ids=lambda r: f"month-{r[0]}")
def test_each_golden_row_individually(row):
    # Same assertion split per row, so a failure names the month.
    assert actual_rows(golden_terms())[row[0] - 1] == row


def test_reproduces_the_agency_totals():
    t = schedule_totals(build_schedule(golden_terms()))
    assert f"{t['total_basic']:.2f}" == GOLDEN_TOTALS["basic"]
    assert f"{t['total_off_day_comp']:.2f}" == GOLDEN_TOTALS["off_day_comp"]
    assert f"{t['total_placement_fee']:.2f}" == GOLDEN_TOTALS["placement_fee"]
    assert f"{t['total_received']:.2f}" == GOLDEN_TOTALS["received"]
    assert t["balance_outstanding"] == Decimal("0.00")
    assert t["loan_cleared_in_month"] == 5


def test_the_header_figures_on_the_schedule():
    terms = golden_terms()
    assert terms.daily_rate == Decimal("26.78")     # "Salary Per Day SGD 26.78"
    assert terms.days_off_per_month == 2            # "Day Off Per Month 2"


# --------------------------------------------- which rules are load-bearing

def test_rounding_the_daily_rate_up_would_break_the_schedule():
    # 696.43 / 26 = 26.785769..  Half-up gives 26.79 and every comp figure
    # drifts. The agency's document says 26.78, so truncation is the rule.
    terms = golden_terms(daily_rate_rounding="half_up")
    assert terms.daily_rate == Decimal("26.79")
    assert actual_rows(terms) != GOLDEN_ROWS


def test_the_period_must_end_on_the_payment_date_not_start_on_it():
    # Counting Sundays from the commencement date instead of the day after
    # shifts 8 of the 24 months between 2 and 3 compensated off days.
    from havenhands import salary

    baseline = build_schedule(golden_terms())
    shifted = []
    for n, p_start, pay in salary.salary_periods(golden_terms()):
        # the rejected reading: [commencement anniversary, day before next]
        alt_start = salary.add_months(date(2026, 9, 11), n - 1)
        alt_end = salary.add_months(date(2026, 9, 11), n) - __import__(
            "datetime").timedelta(days=1)
        shifted.append(salary.count_weekday(alt_start, alt_end, salary.SUNDAY))

    ours = [r.rest_days_in_period for r in baseline]
    differences = sum(1 for a, b in zip(ours, shifted) if a != b)
    assert differences == 8, "the two readings must genuinely disagree"
    assert ours[0] == 5 and shifted[0] == 4


def test_the_deduction_cap_is_the_basic_salary_not_the_agreed_instalment():
    # 2800 / 4 = 700.00 agreed, but only 696.43 is ever taken, which is why
    # the loan runs into a fifth month for a 14.28 balance.
    from havenhands.salary import planned_instalment
    assert planned_instalment(golden_terms()) == Decimal("700.00")
    rows = build_schedule(golden_terms())
    assert rows[0].placement_fee_deduction == Decimal("696.43")
    assert rows[4].placement_fee_deduction == Decimal("14.28")
    assert rows[4].is_final_instalment is True


def test_off_day_compensation_always_reaches_the_helper():
    # Even in a month where the whole basic salary goes to the loan.
    rows = build_schedule(golden_terms())
    for r in rows[:4]:
        assert r.amount_received == r.off_day_comp
        assert r.amount_received > 0


# ------------------------------------------------------ the underlying rules

def test_truncate_money_does_not_round_up():
    assert truncate_money(Decimal("26.785769")) == Decimal("26.78")
    assert truncate_money(Decimal("26.789999")) == Decimal("26.78")
    assert money(Decimal("26.785769")) == Decimal("26.79")   # contrast


def test_count_weekday_inclusive_of_both_ends():
    # 12 Sep 2026 .. 11 Oct 2026 contains Sundays 13, 20, 27 Sep, 4, 11 Oct.
    assert count_weekday(date(2026, 9, 12), date(2026, 10, 11), 6) == 5
    # A period that starts and ends on the same Sunday counts it once.
    assert count_weekday(date(2026, 10, 11), date(2026, 10, 11), 6) == 1
    assert count_weekday(date(2026, 10, 12), date(2026, 10, 11), 6) == 0


def test_add_months_clamps_into_a_short_month():
    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert add_months(date(2028, 1, 31), 1) == date(2028, 2, 29)


def test_a_commencement_on_the_31st_does_not_throw():
    rows = build_schedule(golden_terms(commencement_date=date(2026, 1, 31),
                                       contract_months=14))
    assert rows[0].payment_date == date(2026, 2, 28)
    assert len(rows) == 14


def test_more_rest_days_taken_means_less_compensation():
    four = build_schedule(golden_terms(days_off_per_month=4))
    zero = build_schedule(golden_terms(days_off_per_month=0))
    # With 4 taken, only the 5-Sunday months compensate anything, and just 1 day.
    assert {r.off_days_compensated for r in four} == {0, 1}
    assert {r.off_days_compensated for r in zero} == {4, 5}
    assert sum(r.off_day_comp for r in four) < sum(r.off_day_comp for r in zero)


def test_compensation_is_never_negative():
    rows = build_schedule(golden_terms(days_off_per_month=8))
    assert all(r.off_days_compensated == 0 for r in rows)
    assert all(r.off_day_comp == Decimal("0.00") for r in rows)


def test_a_rest_day_other_than_sunday_is_supported():
    sundays = build_schedule(golden_terms())
    tuesdays = build_schedule(golden_terms(rest_day_weekday=1))
    assert [r.rest_days_in_period for r in sundays] != \
           [r.rest_days_in_period for r in tuesdays]
    assert all(4 <= r.rest_days_in_period <= 5 for r in tuesdays)


def test_no_placement_fee_means_no_deduction():
    rows = build_schedule(golden_terms(total_placement_fee=Decimal("0"),
                                       loan_months=0))
    assert all(r.placement_fee_deduction == Decimal("0.00") for r in rows)
    assert rows[0].amount_received == Decimal("696.43") + rows[0].off_day_comp


def test_a_fee_spread_over_more_months_is_under_the_cap():
    # 2800 over 6 months is 466.67, well under the 696.43 salary cap, so it
    # completes in 6 - the last one a cent light of the rest.
    rows = build_schedule(golden_terms(loan_months=6))
    cuts = [r.placement_fee_deduction for r in rows[:7]]
    assert cuts == [Decimal("466.67")] * 5 + [Decimal("466.65"), Decimal("0.00")]
    assert sum(cuts) == Decimal("2800.00")
    assert rows[5].is_final_instalment is True


def test_every_month_balances_and_nothing_goes_negative():
    rows = build_schedule(golden_terms(loan_months=3))
    for r in rows:
        assert r.amount_received == money(
            r.basic_salary + r.off_day_comp - r.placement_fee_deduction)
        assert r.loan_balance_after == money(
            r.loan_balance_before - r.placement_fee_deduction)
        assert r.amount_received >= 0
        assert r.loan_balance_after >= 0
        assert r.placement_fee_deduction <= r.basic_salary


def test_the_whole_fee_is_collected_and_never_more():
    for fee, months in [("2800", 4), ("2800", 6), ("1000", 3),
                        ("5400", 8), ("3333.33", 7), ("500", 1)]:
        rows = build_schedule(golden_terms(
            total_placement_fee=Decimal(fee), loan_months=months))
        assert schedule_totals(rows)["total_placement_fee"] == Decimal(fee), \
            f"{fee} over {months}"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
