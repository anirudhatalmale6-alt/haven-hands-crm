"""
Compare the PDF this system generates against the agency's original PDF.

Parses the numeric rows out of both documents independently and diffs them,
so the check is on the printed artifact, not on the objects in memory.
"""

import re
import subprocess
import sys

ROW = re.compile(
    r"^\s*(\d{1,2})\s+(\d{2}-\d{2}-\d{4})\s+"
    r"([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})")
TOTAL = re.compile(
    r"Total\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})")


def rows_of(path):
    text = subprocess.run(["pdftotext", "-layout", path, "-"],
                          capture_output=True, text=True, check=True).stdout
    rows = {}
    for line in text.splitlines():
        m = ROW.match(line)
        if m:
            rows[int(m.group(1))] = tuple(g.replace(",", "") for g in m.groups()[1:])
    t = TOTAL.search(text)
    totals = tuple(g.replace(",", "") for g in t.groups()) if t else None
    return rows, totals


def main(original, generated):
    o_rows, o_tot = rows_of(original)
    g_rows, g_tot = rows_of(generated)

    print(f"original  : {original}  ({len(o_rows)} rows)")
    print(f"generated : {generated}  ({len(g_rows)} rows)\n")

    if not o_rows:
        print("FAIL: could not parse any rows out of the original")
        return 1

    problems = []
    if set(o_rows) != set(g_rows):
        problems.append(f"row numbers differ: only in original "
                        f"{sorted(set(o_rows) - set(g_rows))}, only in generated "
                        f"{sorted(set(g_rows) - set(o_rows))}")

    header = f"{'#':>3}  {'pay date':<12} {'basic':>10} {'off day':>9} {'fee':>10} {'received':>10}"
    print(header)
    print("-" * len(header))
    for n in sorted(set(o_rows) & set(g_rows)):
        same = o_rows[n] == g_rows[n]
        mark = "  ok" if same else "  <-- DIFFERS"
        print(f"{n:>3}  {o_rows[n][0]:<12} {o_rows[n][1]:>10} {o_rows[n][2]:>9} "
              f"{o_rows[n][3]:>10} {o_rows[n][4]:>10}{mark}")
        if not same:
            print(f"     generated: {g_rows[n]}")
            problems.append(f"row {n}: {o_rows[n]} != {g_rows[n]}")

    print()
    print(f"totals original : {o_tot}")
    print(f"totals generated: {g_tot}")
    if o_tot != g_tot:
        problems.append(f"totals differ: {o_tot} != {g_tot}")

    print()
    if problems:
        print(f"MISMATCH - {len(problems)} problem(s):")
        for p in problems:
            print("  -", p)
        return 1
    print(f"EXACT MATCH on all {len(o_rows)} rows and the totals line.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1], sys.argv[2]))
