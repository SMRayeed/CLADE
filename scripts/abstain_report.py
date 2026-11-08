#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Robustness checks on the abstention test, from its output CSVs.

The headline from abstain_probe.py is that a page naming only the answer's
family produces far more wrong answers than a page naming nothing. One
difference between the groups could produce that on its own: family-only
questions mostly have all-sibling distractors, while the other groups more
often fall back to random ones. This recomputes every comparison on
questions whose distractors are ALL siblings, so the groups differ only in
what the page says.

It also reports two things the main table does not:
  precision when answering   of the questions it chose to answer, how many
                             were right
  confidence when wrong      how sure the model was of the answers that
                             were wrong; a confident wrong answer is the
                             failure that matters

    python3 abstain_report.py --csv abstain_Qwen2.5-7B-Instruct.csv \\
        --csv abstain_Qwen2.5-0.5B-Instruct.csv

Standard library only.
"""

import argparse
import csv
import math
import os
import statistics
import sys

GROUPS = ["named", "category", "silent"]


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return 100 * p, 100 * max(0.0, c - h), 100 * min(1.0, c + h)


def two_prop(k1, n1, k2, n2):
    if not n1 or not n2:
        return None
    p1, p2 = k1 / n1, k2 / n2
    pp = (k1 + k2) / (n1 + n2)
    se = math.sqrt(pp * (1 - pp) * (1 / n1 + 1 / n2))
    z = (p1 - p2) / se if se > 0 else 0.0
    p = 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))
    return 100 * (p1 - p2), z, p


def table(rows, title):
    print(f"\n  {title}")
    print("    group        n   correct            wrong              declines"
          "        precision  conf. when wrong")
    out = {}
    for g in GROUPS:
        sel = [r for r in rows if r["group"] == g]
        n = len(sel)
        if not n:
            continue
        k = {o: sum(1 for r in sel if r["outcome"] == o)
             for o in ("correct", "wrong", "abstain")}
        cells = []
        for o in ("correct", "wrong", "abstain"):
            p, lo, hi = wilson(k[o], n)
            cells.append(f"{p:5.1f}% [{lo:4.1f}-{hi:4.1f}]")
        ans = k["correct"] + k["wrong"]
        prec = f"{100 * k['correct'] / ans:5.1f}%" if ans else "   - "
        wrong_conf = [float(r["p_pick"]) for r in sel
                      if r["outcome"] == "wrong"]
        conf = (f"{statistics.median(wrong_conf):.2f}"
                if wrong_conf else " - ")
        print(f"    {g:<9} {n:>5}   " + "  ".join(cells) +
              f"   {prec:>8}   {conf:>6}")
        out[g] = (n, k)
    return out


def did(rows, need, seed=0, n_boot=5000):
    """Page effect per question (passage minus closed-book, same question),
    compared between family-only and silent questions. Closed-book shows
    how hard each group is without any page, so this separates what the
    page does from which questions landed in which group."""
    import random
    by = {}
    for r in rows:
        if int(r["n_sibling"]) < need:
            continue
        by.setdefault(r["id"], {})[r["condition"]] = r
    print("\n  WHAT THE PAGE DOES, per question (passage minus closed-book), "
          "all-sibling only")
    print("    outcome    family-only change   silent change   "
          "difference [95% CI]      p")
    for o in ("abstain", "wrong", "correct"):
        d = {"category": [], "silent": []}
        for c in by.values():
            if "passage" in c and "closed" in c:
                g = c["passage"]["group"]
                if g in d:
                    d[g].append((c["passage"]["outcome"] == o) -
                                (c["closed"]["outcome"] == o))
        a, b = d["category"], d["silent"]
        if not a or not b:
            continue
        ma, mb = sum(a) / len(a), sum(b) / len(b)
        va = sum((x - ma) ** 2 for x in a) / max(1, len(a) - 1)
        vb = sum((x - mb) ** 2 for x in b) / max(1, len(b) - 1)
        se = math.sqrt(va / len(a) + vb / len(b))
        z = (ma - mb) / se if se > 0 else 0.0
        p = 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))
        rng = random.Random(seed)
        boots = sorted(
            sum(rng.choice(a) for _ in a) / len(a) -
            sum(rng.choice(b) for _ in b) / len(b)
            for _ in range(n_boot))
        lo, hi = boots[int(0.025 * n_boot)], boots[int(0.975 * n_boot)]
        name = {"abstain": "declines"}.get(o, o)
        print(f"    {name:<9} {100 * ma:+8.1f} pts (n={len(a)})  "
              f"{100 * mb:+8.1f} pts (n={len(b)})  {100 * (ma - mb):+6.1f} "
              f"[{100 * lo:+5.1f}, {100 * hi:+5.1f}]  {p:.3g}")


def item_changes(rows, need):
    """Per question: passage-minus-closed change for each outcome."""
    by = {}
    for r in rows:
        if int(r["n_sibling"]) < need:
            continue
        by.setdefault(r["id"], {})[r["condition"]] = r
    out = {}
    for i, c in by.items():
        if "passage" in c and "closed" in c:
            out[i] = (c["passage"]["group"],
                      {o: (c["passage"]["outcome"] == o) -
                          (c["closed"]["outcome"] == o)
                       for o in ("abstain", "wrong", "correct")})
    return out


def pooled(per_model, seed=0, n_boot=5000):
    """Average each question's page effect over the models, then compare
    family-only with silent questions. The question is the unit, so the
    same question seen by several models is counted once."""
    import random
    # sorted: a set's order changes between runs, and the bootstrap below
    # draws by position
    ids = sorted(set.intersection(*(set(m) for m in per_model)))
    print(f"\n{'=' * 78}\nPOOLED OVER {len(per_model)} MODELS, "
          f"{len(ids):,} questions seen by all, all-sibling only")
    print("    outcome    family-only change   silent change   "
          "difference [95% CI]      p")
    for o in ("abstain", "wrong", "correct"):
        d = {"category": [], "silent": []}
        for i in ids:
            g = per_model[0][i][0]
            if g in d:
                d[g].append(sum(m[i][1][o] for m in per_model) /
                            len(per_model))
        a, b = d["category"], d["silent"]
        if not a or not b:
            continue
        ma, mb = sum(a) / len(a), sum(b) / len(b)
        va = sum((x - ma) ** 2 for x in a) / max(1, len(a) - 1)
        vb = sum((x - mb) ** 2 for x in b) / max(1, len(b) - 1)
        se = math.sqrt(va / len(a) + vb / len(b))
        z = (ma - mb) / se if se > 0 else 0.0
        p = 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))
        rng = random.Random(seed)
        boots = sorted(
            sum(rng.choice(a) for _ in a) / len(a) -
            sum(rng.choice(b) for _ in b) / len(b)
            for _ in range(n_boot))
        lo, hi = boots[int(0.025 * n_boot)], boots[int(0.975 * n_boot)]
        name = {"abstain": "declines"}.get(o, o)
        print(f"    {name:<9} {100 * ma:+8.1f} pts (n={len(a)})  "
              f"{100 * mb:+8.1f} pts (n={len(b)})  {100 * (ma - mb):+6.1f} "
              f"[{100 * lo:+5.1f}, {100 * hi:+5.1f}]  {p:.3g}")


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", action="append", required=True)
    ap.add_argument("--min-sibling", type=int, default=0,
                    help="sibling distractors needed; 0 means all of them, "
                         "read from the file")
    ap.add_argument("--pool", action="store_true",
                    help="also average the page effect over all given "
                         "models, per question")
    a = ap.parse_args()
    per_model = []

    for path in a.csv:
        if not os.path.exists(path):
            print(f"skip {path} -- not found")
            continue
        with open(path, encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        if not rows:
            continue
        n_dis = int(rows[0]["n_options"]) - 2       # minus true, minus decline
        need = a.min_sibling or n_dis
        print(f"\n{'=' * 78}\n{os.path.basename(path)}")

        for cond in ("passage", "closed"):
            allr = [r for r in rows if r["condition"] == cond]
            if not allr:
                continue
            sib = [r for r in allr if int(r["n_sibling"]) >= need]
            table(allr, f"{cond.upper()}, all questions")
            res = table(sib, f"{cond.upper()}, only questions whose "
                             f"{n_dis} distractors are all siblings")
            if cond == "passage" and "category" in res and "silent" in res:
                (n1, k1), (n2, k2) = res["category"], res["silent"]
                t = two_prop(k1["wrong"], n1, k2["wrong"], n2)
                if t:
                    print(f"\n    wrong-answer rate, family-only minus silent, "
                          f"all-sibling only: {t[0]:+.1f} points  "
                          f"z={t[1]:+.2f}  p={t[2]:.3g}")
                    verdict = ("holds" if t[2] < 0.05 and t[0] > 0 else
                               "does NOT hold")
                    print(f"    the headline {verdict} when the distractors "
                          f"are matched")
                d = two_prop(k1["abstain"], n1, k2["abstain"], n2)
                if d:
                    print(f"    decline rate, family-only minus silent, "
                          f"all-sibling only: {d[0]:+.1f} points  "
                          f"z={d[1]:+.2f}  p={d[2]:.3g}")
                    verdict = ("holds" if d[2] < 0.05 and d[0] < 0 else
                               "does NOT hold")
                    print(f"    'a family-only page suppresses declining' "
                          f"{verdict} when the distractors are matched")
                for rel in sorted({r["relation"] for r in sib}):
                    c = [r for r in sib if r["relation"] == rel and
                         r["group"] == "category"]
                    s = [r for r in sib if r["relation"] == rel and
                         r["group"] == "silent"]
                    if c and s:
                        wc = sum(r["outcome"] == "wrong" for r in c)
                        ws = sum(r["outcome"] == "wrong" for r in s)
                        print(f"      {rel:<18} family-only wrong "
                              f"{100 * wc / len(c):5.1f}% (n={len(c)})   "
                              f"silent wrong {100 * ws / len(s):5.1f}% "
                              f"(n={len(s)})")
        did(rows, need)
        per_model.append(item_changes(rows, need))
    if a.pool and len(per_model) > 1:
        pooled(per_model)


if __name__ == "__main__":
    main()
