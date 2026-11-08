#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
E4. Whether expanding a named category is cheap enough to be a method.

The paper's middle branch rests on one claim: when an article names only the
parent category of the true target, the ontology can list that category's
members and the true target will be among them, in a set small enough to
score. Neither half of that is obvious. If categories carry hundreds of
children the branch costs more than it saves, and if the true target is
usually absent from the expansion the branch cannot work at all.

This script measures both halves on real data and reports them together,
because either one alone is misleading. It answers three questions.

  1. Fan-out. For every parent in the ontology, how many children does it
     carry? The distribution, not the mean, is what matters: a long tail of
     large categories is affordable if the median is two.

  2. Recall. For the edges that actually landed at tier 3, which ancestor
     matched the article, and is the true target among that ancestor's
     children? This is the ceiling on the middle branch. The branch cannot
     beat it, and any accuracy figure quoted without it is unanchored.

  3. The trade between the two. Expansion depth buys recall and costs
     candidates. Both are reported at depth 1, 2 and 3 so the choice is
     visible rather than assumed.

The matched ancestor is recovered rather than read from the edge file,
because the build stage records only the tier it reached, not which name got
it there. Recovery uses the same article cache and the same matching rule as
the build, so a tier-3 edge here is a tier-3 edge there.

    python3 fanout.py --ancestors mondo_child_parent.csv

    python3 fanout.py --ancestors mondo_child_parent.csv \\
        --scored matched_edges.csv --wiki-cache wiki_cache \\
        --csv fanout_recall.csv

Needs name_tiers.py beside it. Standard library otherwise.
"""

import argparse
import csv
import os
import statistics
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import name_tiers as nt
except ImportError as e:
    sys.exit(f"name_tiers.py has to sit beside this script: {e}")

csv.field_size_limit(min(2**31 - 1, sys.maxsize))


def pct(xs, q):
    """Percentile by nearest rank, which needs no interpolation argument."""
    if not xs:
        return 0
    s = sorted(xs)
    i = min(len(s) - 1, max(0, int(round(q / 100.0 * (len(s) - 1)))))
    return s[i]


def describe_fanout(anc):
    """anc is child -> [parent]. Reverse it and report the parent side."""
    children = defaultdict(set)
    for ch, parents in anc.items():
        for p in parents:
            children[p].add(ch)
    sizes = [len(v) for v in children.values()]
    amb = [n for n in sizes if n >= 2]

    print(f"\nFAN-OUT   {len(children):,} parents, {len(anc):,} children")
    print(f"  parents with one child only   {len(sizes) - len(amb):>7,}  "
          f"{100 * (len(sizes) - len(amb)) / max(1, len(sizes)):5.1f}%")
    print(f"  parents with two or more      {len(amb):>7,}  "
          f"{100 * len(amb) / max(1, len(sizes)):5.1f}%")
    if amb:
        print("\n  children per parent, counting only the ambiguous parents")
        print(f"    median {statistics.median(amb):>6.1f}")
        print(f"    mean   {statistics.fmean(amb):>6.1f}")
        for q in (75, 90, 95, 99):
            print(f"    p{q:<3}  {pct(amb, q):>6,}")
        print(f"    max    {max(amb):>6,}")
        big = sorted(children, key=lambda k: -len(children[k]))[:5]
        print("\n  the five widest parents")
        for p in big:
            print(f"    {len(children[p]):>5,}  {p}")
    return children


def expand(name, children, depth):
    """Descendants of `name` down `depth` levels, excluding `name`."""
    out, frontier, seen = set(), [name], {name.lower()}
    for _ in range(depth):
        nxt = []
        for n in frontier:
            for c in children.get(n, ()):
                if c.lower() in seen:
                    continue
                seen.add(c.lower())
                out.add(c)
                nxt.append(c)
        frontier = nxt
        if not frontier:
            break
    return out


def recall(rows, anc, children, cache, climb_depth, depths, out_csv):
    """For tier-3 edges: which ancestor matched, and does it recover the target."""
    tier3 = [r for r in rows if int(r.get("tier", 4)) == 3]
    print(f"\nRECALL    {len(tier3):,} edges at tier 3 "
          f"of {len(rows):,} scored")
    if not tier3:
        print("  nothing at tier 3 in this file, so the middle branch has no")
        print("  material here. Check that the build ran with --ancestors.")
        return []

    missing_art = 0
    recovered = []
    for r in tier3:
        src, tgt = r["source"], r["target"]
        text = nt.read_article(cache, src)
        if text is None:
            missing_art += 1
            continue
        # Which ancestors of the target does the article name? The build
        # reached tier 3, so at least one of them should, and the ones that
        # do are the only categories the method can read off the page.
        ancs = [a["scientific"] for a in nt.climb(tgt, anc, depth=climb_depth)]
        hit = [a for a in ancs
               if a and not nt.too_generic(a) and nt.mentions(text, a)]
        recovered.append({"row": r, "matched": hit, "n_anc": len(ancs)})

    if missing_art:
        print(f"  {missing_art:,} sources have no cached article and are dropped")
    usable = [x for x in recovered if x["matched"]]
    print(f"  {len(usable):,} of {len(recovered):,} tier-3 edges have a "
          f"recoverable category name")
    if len(usable) < len(recovered):
        print(f"  the other {len(recovered) - len(usable):,} matched on a name "
              f"this pass calls too generic, or on a\n  vernacular the climb "
              f"does not carry; they are counted as branch-3 failures below")
    if not usable:
        return []

    print("\n  depth   recall   candidates: median  mean   p90    max")
    out = []
    for d in depths:
        hits, sizes = 0, []
        for x in usable:
            tgt = x["row"]["target"]
            # The narrowest matched category is the one a method would use,
            # since it gives the smallest candidate set. Taking the union of
            # every matched ancestor would buy recall with candidates the
            # method has no reason to pay for.
            best, bestset = None, None
            for a in x["matched"]:
                s = expand(a, children, d)
                if bestset is None or len(s) < len(bestset):
                    best, bestset = a, s
            if bestset is None:
                continue
            sizes.append(len(bestset))
            low = {c.lower() for c in bestset}
            if tgt.lower() in low:
                hits += 1
            x[f"hit_d{d}"] = int(tgt.lower() in low)
            x[f"n_d{d}"] = len(bestset)
            x["narrowest"] = best
        p, lo, hi = nt.wilson(hits, len(usable))
        print(f"    {d}    {p:6.2f}% [{lo:5.2f}-{hi:5.2f}]   "
              f"{statistics.median(sizes) if sizes else 0:>6.1f} "
              f"{statistics.fmean(sizes) if sizes else 0:>6.1f} "
              f"{pct(sizes, 90):>6,} {max(sizes) if sizes else 0:>6,}")
        out.append({"depth": d, "recall": round(p, 3), "lo": round(lo, 3),
                    "hi": round(hi, 3), "n": len(usable),
                    "cand_median": statistics.median(sizes) if sizes else 0,
                    "cand_mean": round(statistics.fmean(sizes), 2) if sizes else 0,
                    "cand_p90": pct(sizes, 90),
                    "cand_max": max(sizes) if sizes else 0})

    print("\n  Read the two columns together. Recall is the ceiling on the")
    print("  middle branch and candidates is what each item costs to score.")
    print("  A depth that lifts recall by a point and triples the candidate")
    print("  set is not worth taking.")

    if out_csv:
        with open(out_csv, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(out[0].keys()))
            w.writeheader()
            w.writerows(out)
        print(f"\n  wrote {out_csv}")

    # Per-edge detail, so the router can be checked against the ceiling later.
    if out_csv:
        det = out_csv.replace(".csv", "_edges.csv")
        cols = (["id", "relation", "source", "target", "narrowest"]
                + [f"hit_d{d}" for d in depths] + [f"n_d{d}" for d in depths])
        with open(det, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            for x in usable:
                rec = {k: x["row"].get(k, "") for k in
                       ("id", "relation", "source", "target")}
                rec["narrowest"] = x.get("narrowest", "")
                for d in depths:
                    rec[f"hit_d{d}"] = x.get(f"hit_d{d}", "")
                    rec[f"n_d{d}"] = x.get(f"n_d{d}", "")
                w.writerow(rec)
        print(f"  wrote {det}: one row per tier-3 edge")
    return out


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ancestors", required=True,
                    help="child,parent table, as passed to the build stage")
    ap.add_argument("--ancestor-cols", default="")
    ap.add_argument("--flip-ancestors", action="store_true")
    ap.add_argument("--scored", default="",
                    help="an edge or scored file; without it only fan-out runs")
    ap.add_argument("--wiki-cache", default="wiki_cache")
    ap.add_argument("--climb-depth", type=int, default=2,
                    help="must match the --ancestor-depth the build used")
    ap.add_argument("--depths", default="1,2,3",
                    help="expansion depths to report")
    ap.add_argument("--csv", default="")
    a = ap.parse_args()

    anc = nt.load_ancestors(a.ancestors, a.ancestor_cols, a.flip_ancestors)
    if not anc:
        sys.exit("the ancestor table is empty")
    children = describe_fanout(anc)

    if a.scored:
        if not os.path.exists(a.scored):
            sys.exit(f"missing: {a.scored}")
        with open(a.scored, encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        for need in ("source", "target", "tier"):
            if rows and need not in rows[0]:
                sys.exit(f"{a.scored} has no '{need}' column. Present: "
                         + ", ".join(sorted(rows[0])))
        if not os.path.isdir(a.wiki_cache):
            sys.exit(f"no article cache at {a.wiki_cache}; recall needs the "
                     f"same cache the build used")
        depths = [int(x) for x in a.depths.split(",") if x.strip()]
        recall(rows, anc, children, a.wiki_cache, a.climb_depth, depths, a.csv)


if __name__ == "__main__":
    main()
