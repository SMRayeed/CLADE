#!/usr/bin/env python3
"""
Cross-tabulate text evidence against model knowledge, one edge at a time.

Every edge in a scored file carries two independent measurements: whether the
source entity's article names the target (the tier), and whether the model
picked the true target out of a field of distractors (mc_correct). Crossing
them splits the graph into four parts, and the fourth is the one that matters:

    in the text, in the model      nothing to fix
    in the text, not in the model  retrieval has something to work with
    not in the text, in the model  learned somewhere we are not looking
    in neither                     no text-based method reaches this edge

    python3 four_boxes.py --scored p1_scored_d2.csv
    python3 four_boxes.py --scored p1_scored_d2.csv --text-cut 3
    python3 four_boxes.py --scored het_scored.csv --csv het_boxes.csv

The split between "in the text" and "not in the text" is an argument, not a
fact, so --text-cut exposes it. The default counts tiers 0-2 as present,
because the accuracy at tier 3 sits beside tier 4 rather than beside tier 0:
an article that names only the parent category behaves, from the model's side,
like an article that says nothing. --text-cut 3 moves tier 3 to the other
side and reports the same tables, which is the robustness check a reader will
ask for.

Standard library only.
"""

import argparse
import csv
import math
import sys
from collections import defaultdict

csv.field_size_limit(min(2**31 - 1, sys.maxsize))

TIER_LABEL = {0: "exact name", 1: "+synonym", 2: "+common name",
              3: "ancestor only", 4: "not named at all"}


def wilson(k, n, z=1.96):
    """Wilson score interval. Degrades sensibly at n = 0 and at k = 0 or n."""
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    center = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (100 * p, 100 * max(0.0, center - half), 100 * min(1.0, center + half))


def read_rows(path):
    with open(path, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        sys.exit(f"{path} has no rows")
    for need in ("tier", "mc_correct"):
        if need not in rows[0]:
            sys.exit(f"{path} has no '{need}' column. Columns present: "
                     + ", ".join(sorted(rows[0])))
    out = []
    for r in rows:
        try:
            r["_tier"] = int(r["tier"])
            r["_hit"] = int(r["mc_correct"])
        except (TypeError, ValueError):
            continue            # a malformed row is dropped, not guessed at
        out.append(r)
    if not out:
        sys.exit(f"{path}: no rows with usable tier and mc_correct")
    return out


def boxes(rows, cut):
    """Counts keyed (text_present, model_correct)."""
    c = defaultdict(int)
    for r in rows:
        c[(r["_tier"] <= cut, bool(r["_hit"]))] += 1
    return c


def print_boxes(title, rows, cut, chance):
    n = len(rows)
    c = boxes(rows, cut)
    tt, tf = c[(True, True)], c[(True, False)]
    ft, ff = c[(False, True)], c[(False, False)]

    print(f"\n{title}   n = {n:,}")
    print("                        model knows      model does not        row")
    print(f"  text names it     {tt:>8,} {100*tt/n:>6.1f}%  "
          f"{tf:>8,} {100*tf/n:>6.1f}%  {100*(tt+tf)/n:>7.1f}%")
    print(f"  text silent       {ft:>8,} {100*ft/n:>6.1f}%  "
          f"{ff:>8,} {100*ff/n:>6.1f}%  {100*(ft+ff)/n:>7.1f}%")
    print(f"  column            {100*(tt+ft)/n:>14.1f}%  "
          f"{100*(tf+ff)/n:>14.1f}%")

    reach = 100 * (tt + tf) / n
    print(f"\n  reachable by text        {reach:5.1f}%   "
          f"(the text states the fact at tier <= {cut})")
    print(f"  retrieval has room to help  {100*tf/n:5.1f}%   "
          f"(stated, and the model misses it)")
    print(f"  out of reach of text        {100*ff/n:5.1f}%   "
          f"(in neither; needs the graph itself)")

    # Accuracy on each side, with intervals, and the gap between them.
    for flag, lab in ((True, "text names it"), (False, "text silent")):
        k = c[(flag, True)]
        m = c[(flag, True)] + c[(flag, False)]
        p, lo, hi = wilson(k, m)
        extra = ""
        if chance is not None and m:
            extra = f"   chance-corrected {p - chance:+6.2f}"
        print(f"  accuracy, {lab:<16} {p:6.2f}% [{lo:5.2f}-{hi:5.2f}]  "
              f"n={m:>6,}{extra}")

    a = wilson(c[(True, True)], c[(True, True)] + c[(True, False)])[0]
    b = wilson(c[(False, True)], c[(False, True)] + c[(False, False)])[0]
    print(f"  difference               {a - b:+6.2f} points")
    return {"n": n, "tt": tt, "tf": tf, "ft": ft, "ff": ff,
            "reach": reach, "acc_text": a, "acc_silent": b}


def print_tiers(rows, chance):
    by = defaultdict(list)
    for r in rows:
        by[r["_tier"]].append(r["_hit"])
    print("\n  accuracy by tier")
    for t in range(5):
        v = by.get(t)
        if not v:
            continue
        p, lo, hi = wilson(sum(v), len(v))
        extra = f"   {p - chance:+6.2f}" if chance is not None else ""
        print(f"    tier {t} {TIER_LABEL[t]:<18} {p:6.2f}% "
              f"[{lo:5.2f}-{hi:5.2f}]  n={len(v):>6,}{extra}")


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scored", required=True,
                    help="output of run_probe_cpu.py (needs tier, mc_correct)")
    ap.add_argument("--text-cut", type=int, default=2,
                    help="highest tier counted as 'the text names it' "
                         "(default 2: exact, synonym, common name)")
    ap.add_argument("--by-relation", action="store_true", default=True)
    ap.add_argument("--no-by-relation", dest="by_relation",
                    action="store_false")
    ap.add_argument("--csv", default="",
                    help="write the per-relation boxes here")
    a = ap.parse_args()

    rows = read_rows(a.scored)

    chance = None
    if rows[0].get("mc_n_choices"):
        try:
            chance = 100.0 / int(rows[0]["mc_n_choices"])
        except (TypeError, ValueError):
            chance = None
    if chance is not None:
        print(f"chance = {chance:.2f}%   text-cut = tier {a.text_cut}")
    else:
        print(f"text-cut = tier {a.text_cut}")

    out = []
    overall = print_boxes("ALL EDGES", rows, a.text_cut, chance)
    print_tiers(rows, chance)
    overall["relation"] = "ALL"
    out.append(overall)

    if a.by_relation and "relation" in rows[0]:
        by = defaultdict(list)
        for r in rows:
            by[r["relation"]].append(r)
        for rel in sorted(by):
            d = print_boxes(rel.upper(), by[rel], a.text_cut, chance)
            print_tiers(by[rel], chance)
            d["relation"] = rel
            out.append(d)

    if a.csv:
        cols = ["relation", "n", "tt", "tf", "ft", "ff", "reach",
                "acc_text", "acc_silent"]
        with open(a.csv, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            for d in out:
                w.writerow({k: d[k] for k in cols})
        print(f"\nwrote {a.csv}")

    print("\nRe-run with --text-cut 3 to move the ancestor tier to the "
          "'text names it' side.")


if __name__ == "__main__":
    main()
