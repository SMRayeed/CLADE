#!/usr/bin/env python3
"""
Turn the GloBI interaction dump into the two files the abstention test reads.

    globi_edges.csv         source, target, relation   (species -> species)
    globi_child_parent.csv  child, parent              (species -> genus ->
                                                        family -> order -> class)

The taxonomy table plays the role MONDO plays for diseases: a family-only page
is one that names the target's genus or family but not the species, and the
distractors are the target's siblings (other species of the same genus, then
of the same family).

Only species-level names are kept on both sides ("Genus epithet", no "sp.",
no hybrids, no numbers), because a question about a genus has no single
answer. Where GloBI gives a taxon two different parents, the parent seen most
often is kept, so the table is a tree and climbing it never walks sideways.

    python3 globi_prep.py --tsv interactions.tsv.gz \\
        --relations eats,preysOn,parasiteOf,pollinates \\
        --edges-out globi_edges.csv --taxonomy-out globi_child_parent.csv

The dump is streamed, so memory stays small; a full pass takes 15-40 minutes.
Standard library only.
"""

import argparse
import csv
import gzip
import io
import re
import sys
import time
from collections import Counter, defaultdict

BINOMIAL = re.compile(r"^[A-Z][a-z]+ [a-z][a-z-]+$")
RANKS = ["species", "genus", "family", "order", "class"]


def species_name(name):
    name = (name or "").strip()
    return name if BINOMIAL.match(name) and " sp" not in name else ""


def ladder(path_names, path_ranks, fallback):
    """{rank: name} from GloBI's pipe-separated path columns, with the
    per-rank columns as a fallback."""
    out = {}
    names = [x.strip() for x in (path_names or "").split("|")]
    ranks = [x.strip().lower() for x in (path_ranks or "").split("|")]
    if len(names) == len(ranks):
        for n, r in zip(names, ranks):
            if r in RANKS and n:
                out[r] = n
    for r, v in fallback.items():
        if v and r not in out:
            out[r] = v.strip()
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tsv", required=True, help="interactions.tsv.gz from GloBI")
    ap.add_argument("--relations", default="eats,preysOn,parasiteOf,pollinates")
    ap.add_argument("--edges-out", default="globi_edges.csv")
    ap.add_argument("--taxonomy-out", default="globi_child_parent.csv")
    ap.add_argument("--limit", type=int, default=0, help="stop after N rows (testing)")
    a = ap.parse_args()
    want = {r.strip() for r in a.relations.split(",") if r.strip()}

    opener = gzip.open if a.tsv.endswith(".gz") else open
    fh = io.TextIOWrapper(opener(a.tsv, "rb"), encoding="utf-8", errors="replace")
    header = fh.readline().rstrip("\n").split("\t")
    col = {c: i for i, c in enumerate(header)}
    need = ["sourceTaxonName", "targetTaxonName", "interactionTypeName"]
    miss = [c for c in need if c not in col]
    if miss:
        sys.exit(f"{a.tsv} lacks columns {miss}. Its columns are:\n  "
                 + ", ".join(header[:60]))

    def g(parts, name):
        i = col.get(name)
        return parts[i] if i is not None and i < len(parts) else ""

    edges = defaultdict(int)
    parent_votes = defaultdict(Counter)
    n_rows = n_rel = 0
    t0 = time.time()
    for line in fh:
        n_rows += 1
        if a.limit and n_rows > a.limit:
            break
        if n_rows % 2_000_000 == 0:
            print(f"  {n_rows / 1e6:.0f}M rows, {len(edges):,} edges kept, "
                  f"{time.time() - t0:.0f}s", file=sys.stderr, flush=True)
        parts = line.rstrip("\n").split("\t")
        rel = g(parts, "interactionTypeName")
        if rel not in want:
            continue
        n_rel += 1
        sides = {}
        for side in ("source", "target"):
            lad = ladder(g(parts, f"{side}TaxonPathNames"),
                         g(parts, f"{side}TaxonPathRankNames"),
                         {r: g(parts, f"{side}Taxon{r.capitalize()}Name") for r in RANKS})
            sp = species_name(lad.get("species", "")) or species_name(g(parts, f"{side}TaxonName"))
            sides[side] = (sp, lad)
        s, t = sides["source"][0], sides["target"][0]
        if not s or not t or s == t:
            continue
        edges[(s, t, rel)] += 1
        lad = dict(sides["target"][1])
        lad["species"] = t
        # genus of a binomial is its first word, whatever the path says
        lad["genus"] = t.split()[0]
        chain = [lad.get(r, "") for r in RANKS]
        for child, parent in zip(chain, chain[1:]):
            if child and parent and child.lower() != parent.lower():
                parent_votes[child][parent] += 1

    with open(a.edges_out, "w", newline="", encoding="utf-8") as out:
        w = csv.writer(out)
        w.writerow(["source", "target", "relation", "n_records"])
        for (s, t, r), n in sorted(edges.items()):
            w.writerow([s, t, r, n])

    # one parent per child, the most frequent; drop pairs that would make a
    # two-way loop
    parent = {c: v.most_common(1)[0][0] for c, v in parent_votes.items()}
    rows = [(c, p) for c, p in parent.items() if parent.get(p) != c]
    with open(a.taxonomy_out, "w", newline="", encoding="utf-8") as out:
        w = csv.writer(out)
        w.writerow(["child", "parent"])
        w.writerows(sorted(rows))

    print(f"\nread {n_rows:,} rows; {n_rel:,} in the chosen relations")
    print(f"wrote {a.edges_out}: {len(edges):,} species-to-species edges")
    by = Counter(r for (_s, _t, r) in edges)
    for r in sorted(want):
        srcs = {s for (s, _t, rr) in edges if rr == r}
        print(f"  {r:<14} {by.get(r, 0):>9,} edges  {len(srcs):>7,} sources")
    genera = Counter(p for c, p in rows if BINOMIAL.match(c))
    with_family = sum(1 for c, p in rows if not BINOMIAL.match(c) and " " not in c)
    if not with_family:
        print("WARNING: no genus -> family rows; the dump has no usable path or "
              "family columns, so 'family only' means 'genus only'")
    print(f"wrote {a.taxonomy_out}: {len(rows):,} child-parent rows; "
          f"{sum(1 for v in genera.values() if v >= 2):,} genera with two or more species")


if __name__ == "__main__":
    main()
