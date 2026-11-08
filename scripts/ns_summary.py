#!/usr/bin/env python3
"""Collect the NeusymBridge headline numbers that come straight from CSVs.

The abstention and recovery results are paired and bootstrapped in
abstain_report.py and candidate_check.py; their logs are listed at the end.

    python3 ns_summary.py --work work --small-tag Qwen2.5-0.5B-Instruct \
        --large-tag Qwen2.5-7B-Instruct --out results/SUMMARY.md

Standard library only.
"""

import argparse
import csv
import os
from collections import defaultdict


def load(path):
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def band(t):
    t = int(t)
    return "named" if t <= 2 else ("family only" if t == 3 else "silent")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--work", default="work")
    ap.add_argument("--small-tag", default="Qwen2.5-0.5B-Instruct")
    ap.add_argument("--large-tag", default="Qwen2.5-7B-Instruct")
    ap.add_argument("--out", default="SUMMARY.md")
    a = ap.parse_args()
    W = lambda f: os.path.join(a.work, f)          # noqa: E731
    L = ["# NeusymBridge results summary", "",
         "Recomputed from the per-edge CSV files in `work/`. "
         "Detailed logs are in `results/`.", ""]

    small = load(W(f"p1_edges_d2_{a.small_tag}.csv"))
    if small:
        n = len(small)
        box = defaultdict(int)
        for r in small:
            box[(int(r["tier"]) <= 2, int(float(r["mc_correct"])) == 1)] += 1
        L += [f"## How much of the graph text reaches ({a.small_tag}, {n:,} edges)", "",
              "| | Model knows it | Model does not |", "|---|---|---|",
              f"| Text names it | {100 * box[(True, True)] / n:.1f}% | {100 * box[(True, False)] / n:.1f}% |",
              f"| Text does not | {100 * box[(False, True)] / n:.1f}% | {100 * box[(False, False)] / n:.1f}% |",
              ""]
        silent = [r for r in small if int(r["tier"]) > 2]
        if silent:
            k = sum(int(float(r["mc_correct"])) for r in silent)
            L += [f"Accuracy on facts the text does not name: {100 * k / len(silent):.1f}% "
                  f"(chance 20%).", ""]

    large = load(W(f"p1_edges_d2_{a.large_tag}.csv"))
    if large:
        L += [f"## Does a family name alone help? ({a.large_tag}, closed book)", "",
              "| Relation | named | family only | silent |", "|---|---|---|---|"]
        cell = defaultdict(lambda: [0, 0])
        for r in large:
            c = cell[(r["relation"], band(r["tier"]))]
            c[0] += int(float(r["mc_correct"]))
            c[1] += 1
        for rel in sorted({r["relation"] for r in large}):
            parts = []
            for b in ("named", "family only", "silent"):
                k, m = cell[(rel, b)]
                parts.append(f"{100 * k / m:.2f}% (n={m})" if m else "-")
            L.append(f"| {rel} | " + " | ".join(parts) + " |")
        L += ["", "Stratified odds ratios: `results/tier_cliff_*.txt`.", ""]

    q = load(W("me_bal_union.csv"))
    if q:
        mix = defaultdict(int)
        for r in q:
            mix[band(r["tier"])] += 1
        L += ["## Question pool (drug-matched sample, Wikipedia + PubMed)", "",
              "| Group | edges |", "|---|---|"]
        for b in ("named", "family only", "silent"):
            L.append(f"| {b} | {mix[b]:,} |")
        L.append("")

    L += ["## Where the other numbers are", "",
          "| Paper item | File |", "|---|---|",
          "| Four-box table, both cuts | `results/four_boxes_*.txt` |",
          "| Family-only vs silent vs named, stratified by relation | `results/tier_cliff_*.txt` |",
          "| Abstention, per model | `results/abstain_report_<model>.txt` |",
          "| Abstention, pooled over the 7-8B models (difference in differences) | `results/abstain_report_pooled.txt` |",
          "| Recovery: list coverage, page-built lists, choosing a member, end to end | `results/candidate_check_wiki.txt` |",
          "| Page-built lists from Wikipedia + PubMed | `results/candidate_check_all.txt` |",
          "| Fan-out of MONDO families | `results/fanout.txt` |",
          "| MONDO table size | `results/mondo_parents.txt` |", ""]

    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
