#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
E3. Where the cliff falls, tested inside each relation.

The four-box split puts tier 3 on the "text silent" side, and that is a
choice rather than a fact. It rests on a claim that has to be tested: an
article naming only the target's parent category behaves, from the model's
side, like an article naming nothing at all. If that is right, tier 3 sits
beside tier 4 and the split is justified. If tier 3 sits beside tiers 0 to 2
instead, the split is wrong and two thirds of the graph is not out of reach.

The test has to run inside each relation and then pool with relation as a
stratum. Relations differ in both how often they reach tier 3 and how well
the model does on them, so a pooled comparison that ignores relation can
reverse the sign of the within-relation effect. That is what happened to the
pooled tier-3-against-tier-4 figure the earlier run printed, and it is why
that figure does not appear in the paper.

Two comparisons are reported for each relation.

    tier 3 against tiers 0-2    the gap the claim predicts
    tier 3 against tier 4       the gap the claim predicts to be absent

A result supports the split when the first is large and the second is near
zero. Failing to reject the second is not proof it is zero, so the interval
is printed beside it: a null with an interval from -1 to +2 points rules out
the effect, and a null with an interval from -15 to +15 rules out nothing.

    python3 tier_cliff.py --scored p1_edges_d2_Qwen2.5-7B-Instruct.csv

    python3 tier_cliff.py \\
        --scored p1_edges_d2_Qwen2.5-7B-Instruct.csv \\
        --scored het_edges_Qwen2.5-7B-Instruct.csv \\
        --csv cliff.csv

Standard library only.
"""

import argparse
import csv
import math
import os
import sys
from collections import defaultdict

csv.field_size_limit(min(2**31 - 1, sys.maxsize))

LABEL = {0: "exact name", 1: "+synonym", 2: "+common name",
         3: "ancestor only", 4: "not named at all"}


def norm_cdf(z):
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def two_sided(z):
    return 2.0 * (1.0 - norm_cdf(abs(z)))


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (100 * p, 100 * max(0.0, c - h), 100 * min(1.0, c + h))


def diff_test(k1, n1, k2, n2):
    """Two-proportion difference, its Wald interval, and a pooled-variance z.

    The interval uses the unpooled variance because it describes the
    difference; the test statistic uses the pooled variance because it is
    computed under the null that the two rates are equal.
    """
    if n1 == 0 or n2 == 0:
        return None
    p1, p2 = k1 / n1, k2 / n2
    d = p1 - p2
    se_u = math.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)
    pp = (k1 + k2) / (n1 + n2)
    se_p = math.sqrt(pp * (1 - pp) * (1 / n1 + 1 / n2))
    z = d / se_p if se_p > 0 else 0.0
    return {"d": 100 * d, "lo": 100 * (d - 1.96 * se_u),
            "hi": 100 * (d + 1.96 * se_u), "z": z, "p": two_sided(z),
            "n1": n1, "n2": n2, "p1": 100 * p1, "p2": 100 * p2}


def mantel_haenszel(strata):
    """strata is a list of (A, B, C, D): exposed hit/miss, unexposed hit/miss.

    Returns the pooled odds ratio with a Robins-Breslow-Greenland interval
    and the continuity-corrected chi-square. Strata too small to contribute
    are dropped rather than pooled, since pooling them is the error this
    function exists to avoid.
    """
    num = den = 0.0
    chi_num = chi_den = 0.0
    p_sum = q_sum = pr_sum = ps_qr_sum = qs_sum = 0.0
    used = 0
    for A, B, C, D in strata:
        n = A + B + C + D
        if n < 2 or (A + B) == 0 or (C + D) == 0:
            continue
        used += 1
        R = A * D / n
        S = B * C / n
        num += R
        den += S
        e = (A + B) * (A + C) / n
        var = (A + B) * (C + D) * (A + C) * (B + D) / (n * n * (n - 1))
        chi_num += A - e
        chi_den += var
        P = (A + D) / n
        Q = (B + C) / n
        p_sum += P * R
        pr_sum += R
        ps_qr_sum += P * S + Q * R
        qs_sum += Q * S
        q_sum += S
    if used == 0 or den == 0 or num == 0:
        return None
    or_mh = num / den
    var_log = (p_sum / (2 * pr_sum * pr_sum)
               + ps_qr_sum / (2 * pr_sum * q_sum)
               + qs_sum / (2 * q_sum * q_sum))
    se = math.sqrt(var_log) if var_log > 0 else 0.0
    chi = ((abs(chi_num) - 0.5) ** 2 / chi_den) if chi_den > 0 else 0.0
    z = math.sqrt(chi)
    return {"or": or_mh, "lo": or_mh * math.exp(-1.96 * se),
            "hi": or_mh * math.exp(1.96 * se), "chi": chi,
            "p": two_sided(z), "strata": used}


def load(paths):
    """Read every scored file that is there, and say which were not.

    A model that has not been probed yet leaves no file, and naming one
    should cost a line of output rather than the whole run: the comparison
    across the files that do exist is still the result being asked for.
    """
    present = [p for p in paths if os.path.exists(p)]
    for p in paths:
        if p not in present:
            print(f"skip {p} -- not built yet", file=sys.stderr)
    if not present:
        sys.exit("none of the scored files exist:\n  "
                 + "\n  ".join(paths)
                 + "\n\nList what is on disk with: ls -1 *_Qwen*.csv p1_scored*.csv")

    rows = []
    chance = None
    for path in present:
        with open(path, encoding="utf-8") as fh:
            rd = csv.DictReader(fh)
            got = list(rd)
        if not got:
            sys.exit(f"{path} has no rows")
        for need in ("tier", "mc_correct"):
            if need not in got[0]:
                sys.exit(f"{path} has no '{need}' column. Present: "
                         + ", ".join(sorted(got[0])))
        if chance is None and got[0].get("mc_n_choices"):
            try:
                chance = 100.0 / int(got[0]["mc_n_choices"])
            except (TypeError, ValueError):
                pass
        tag = path.rsplit("/", 1)[-1].replace(".csv", "")
        for r in got:
            try:
                r["_tier"] = int(r["tier"])
                r["_hit"] = int(r["mc_correct"])
            except (TypeError, ValueError):
                continue
            r["_file"] = tag
            rows.append(r)
    if not rows:
        sys.exit("no usable rows")
    return rows, chance, present


def band(rows, lo, hi):
    """(hits, n) for edges whose tier falls in [lo, hi]."""
    sel = [r for r in rows if lo <= r["_tier"] <= hi]
    return sum(r["_hit"] for r in sel), len(sel)


def report(name, rows, chance, min_n):
    print(f"\n{'=' * 72}\n{name}   n = {len(rows):,}")

    print("\n  accuracy by tier")
    for t in range(5):
        sel = [r for r in rows if r["_tier"] == t]
        if not sel:
            continue
        p, lo, hi = wilson(sum(r["_hit"] for r in sel), len(sel))
        cc = f"   chance-corrected {p - chance:+6.2f}" if chance else ""
        print(f"    tier {t} {LABEL[t]:<18} {p:6.2f}% [{lo:5.2f}-{hi:5.2f}]  "
              f"n={len(sel):>6,}{cc}")

    k3, n3 = band(rows, 3, 3)
    k02, n02 = band(rows, 0, 2)
    k4, n4 = band(rows, 4, 4)

    out = {"group": name, "n": len(rows), "n_named": n02, "n_t3": n3,
           "n_t4": n4}
    if min(n3, n02) < min_n:
        print(f"\n  too few edges to compare: tier 3 has {n3:,}, "
              f"tiers 0-2 have {n02:,}, and {min_n} of each is the floor")
        return out

    print("\n  tier 3 against tiers 0-2   (the claim predicts a large gap)")
    d = diff_test(k3, n3, k02, n02)
    print(f"    {d['p1']:6.2f}%  vs  {d['p2']:6.2f}%     "
          f"{d['d']:+6.2f} points  [{d['lo']:+6.2f}, {d['hi']:+6.2f}]  "
          f"z={d['z']:+.2f}  p={d['p']:.3g}")
    out.update({"d_named": round(d["d"], 3), "p_named": d["p"]})

    if n4 >= min_n:
        print("\n  tier 3 against tier 4      (the claim predicts no gap)")
        e = diff_test(k3, n3, k4, n4)
        print(f"    {e['p1']:6.2f}%  vs  {e['p2']:6.2f}%     "
              f"{e['d']:+6.2f} points  [{e['lo']:+6.2f}, {e['hi']:+6.2f}]  "
              f"z={e['z']:+.2f}  p={e['p']:.3g}")
        width = e["hi"] - e["lo"]
        if e["p"] >= 0.05:
            if width <= 10:
                print(f"    a null with an interval {width:.1f} points wide, "
                      f"so the effect is bounded small")
            else:
                print(f"    a null with an interval {width:.1f} points wide, "
                      f"which is too loose to bound anything;\n"
                      f"    this group is underpowered rather than flat")
        out.update({"d_silent": round(e["d"], 3), "p_silent": e["p"],
                    "ci_width": round(width, 2)})
    else:
        print(f"\n  tier 4 has {n4:,} edges, below the {min_n} floor, so the "
              f"second comparison is skipped")
    return out


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scored", action="append", required=True,
                    help="repeatable; one scored file per graph or model")
    ap.add_argument("--min-n", type=int, default=25,
                    help="smallest cell that gets a test")
    ap.add_argument("--csv", default="")
    a = ap.parse_args()

    rows, chance, present = load(a.scored)
    if chance:
        print(f"chance = {chance:.2f}%   files = {len(present)}")

    out = []
    by = defaultdict(list)
    for r in rows:
        key = r.get("relation", "?")
        if len(present) > 1:
            key = f"{r['_file']} / {key}"
        by[key].append(r)

    for key in sorted(by):
        out.append(report(key, by[key], chance, a.min_n))

    # Pooled, with relation as the stratum. This replaces the pooled block in
    # four_boxes.py, which crosses relations and can therefore reverse sign.
    print(f"\n{'=' * 72}\nPOOLED, RELATION AS STRATUM")
    for lab, lo, hi in (("tiers 0-2", 0, 2), ("tier 4", 4, 4)):
        strata = []
        for key in sorted(by):
            k3, n3 = band(by[key], 3, 3)
            k2, n2 = band(by[key], lo, hi)
            strata.append((k3, n3 - k3, k2, n2 - k2))
        mh = mantel_haenszel(strata)
        print(f"\n  tier 3 against {lab}")
        if not mh:
            print("    no stratum carries both cells")
            continue
        print(f"    odds ratio {mh['or']:.3f}  "
              f"[{mh['lo']:.3f}, {mh['hi']:.3f}]   "
              f"chi2={mh['chi']:.2f}  p={mh['p']:.3g}  "
              f"strata={mh['strata']}")
        if mh["lo"] <= 1.0 <= mh["hi"]:
            print("    the interval covers 1, so tier 3 is indistinguishable "
                  f"from {lab} here")
        else:
            side = "below" if mh["hi"] < 1.0 else "above"
            print(f"    the interval sits {side} 1, so tier 3 differs from "
                  f"{lab}")
        out.append({"group": f"POOLED vs {lab}", "or": round(mh["or"], 4),
                    "or_lo": round(mh["lo"], 4), "or_hi": round(mh["hi"], 4),
                    "p": mh["p"], "strata": mh["strata"]})

    print("\nThe split that the four-box table uses holds when tier 3 differs")
    print("from tiers 0-2 and does not differ from tier 4. Both halves have")
    print("to be reported; the second is the one a reviewer will check.")

    if a.csv and out:
        cols = []
        for d in out:
            for k in d:
                if k not in cols:
                    cols.append(k)
        with open(a.csv, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            w.writerows(out)
        print(f"\nwrote {a.csv}")


if __name__ == "__main__":
    main()
