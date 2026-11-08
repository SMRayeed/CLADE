#!/usr/bin/env python3
"""Synthetic GloBI dump, Wikipedia cache and name cache for `globi.sh --smoke`.

Each consumer's article names some of its partners in full, some only by
genus or family, and leaves the rest out, so all three question groups
occur. Only the plumbing is under test; the numbers mean nothing.
"""
import argparse
import gzip
import json
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import name_tiers as nt  # noqa: E402

SYL = ["ba", "ca", "da", "fe", "go", "hi", "lu", "ma", "no", "pi", "ra", "si", "to", "vu", "xe", "zo"]


def word(rng, n):
    return "".join(rng.choice(SYL) for _ in range(n))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    rng = random.Random(a.seed)
    os.makedirs(a.data, exist_ok=True)

    # prey / host / plant taxonomy: 4 orders x 3 families x 4 genera x 6 species
    taxa = []
    for o in range(4):
        order = word(rng, 3).capitalize() + "ales"
        for f in range(3):
            fam = word(rng, 3).capitalize() + "idae"
            for g in range(4):
                genus = word(rng, 3).capitalize()
                for s in range(6):
                    taxa.append((f"{genus} {word(rng, 3)}", genus, fam, order))
    by_genus = {}
    for t in taxa:
        by_genus.setdefault(t[1], []).append(t)
    consumers = [(f"{word(rng, 3).capitalize()} {word(rng, 3)}") for _ in range(160)]
    rels = ["eats", "preysOn", "parasiteOf", "pollinates"]

    cols = ["sourceTaxonName", "sourceTaxonRank", "sourceTaxonPathNames",
            "sourceTaxonPathRankNames", "interactionTypeName", "targetTaxonName",
            "targetTaxonRank", "targetTaxonPathNames", "targetTaxonPathRankNames",
            "targetTaxonGenusName", "targetTaxonFamilyName"]
    rows, articles = [], {}
    for c in consumers:
        sentences = [f"{c} is a species described from field surveys."]
        for rel in rels:
            for t in rng.sample(taxa, 3):
                sp, genus, fam, order = t
                rows.append([c, "species", f"Animalia | {c.split()[0]} | {c}",
                             "kingdom | genus | species", rel, sp, "species",
                             f"Plantae | {order} | {fam} | {genus} | {sp}",
                             "kingdom | order | family | genus | species", genus, fam])
                mode = rng.random()
                if mode < 0.33:
                    sentences.append(f"It is recorded to {rel} {sp} in the wild.")
                elif mode < 0.66:
                    sentences.append(f"It is associated with members of the genus {genus}.")
        sentences += [f"The species {c} is common in its range and has been studied often."] * 4
        articles[c] = " ".join(sentences)
    # a few genus-level rows, which must be dropped
    rows.append([consumers[0], "species", "", "", "eats", "Quercus", "genus", "", "", "", ""])

    with gzip.open(os.path.join(a.data, "interactions.tsv.gz"), "wt", encoding="utf-8") as fh:
        fh.write("\t".join(cols) + "\n")
        for r in rows:
            fh.write("\t".join(r) + "\n")
    for c, txt in articles.items():
        nt.write_article(os.path.join(a.work, "wiki_cache"), c, txt)
    for t in taxa:
        nt.write_names(os.path.join(a.work, "gbif_cache"), "redir", t[0], dict(nt.EMPTY))
    print(f"fixture: {len(rows):,} interactions, {len(articles)} articles, {len(taxa)} taxa")


if __name__ == "__main__":
    main()
