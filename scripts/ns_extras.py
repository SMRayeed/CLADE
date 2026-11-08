#!/usr/bin/env python3
"""Additional NeusymBridge analyses on the abstention questions.

All three use the questions whose four distractors all come from the
answer's MONDO neighborhood (n_sibling == 4), the set behind the paper's
main result (106 named, 215 family-only, 160 silent).

1. Confidence. With the page, among answered questions: precision, mean
   confidence of right and wrong answers, and how well confidence separates
   them (AUROC). Risk-coverage points come from answering only the most
   confident questions.

2. Family size. Family-only questions are split into thirds by the size of
   the answer's family list (given-family list from the recovery run). For
   each third, the page effect on declines (with page minus closed book) is
   compared with the same effect on silent questions, averaged over the
   pooled models, with a 95% bootstrap interval over questions.

4. Counterfactual page edit. The same named questions with the answer's
   name replaced by its MONDO parent, or with the sentences naming it
   removed (abstain_probe.py --edit). This holds the drug, the question
   and the options fixed and changes one phrase of the page.

3. Prompting baseline. The same questions with one added instruction to
   decline when the passage names only a broad category (abstain_probe.py
   --instruct). Outcomes with the page are compared with the base prompt,
   question by question.

Writes a markdown report (--out) and the numbers for the figures (--json).
"""
import argparse
import csv
import json
import os
import random
from collections import defaultdict

GROUPS = [("named", "named"), ("category", "family only"), ("silent", "silent")]


def load(path, condition=None, all_sibling=True):
    out = {}
    for r in csv.DictReader(open(path, encoding="utf-8")):
        if all_sibling and int(r.get("n_sibling", 4) or 0) != 4:
            continue
        if condition and r["condition"] != condition:
            continue
        out[(r["id"], r["condition"])] = r
    return out


def tag_of(path):
    b = os.path.basename(path)
    for pre, suf in (("abstain_", "_instruct.csv"), ("abstain_", "_clean.csv")):
        if b.startswith(pre) and b.endswith(suf):
            return b[len(pre):-len(suf)]
    return b


def auroc(pos, neg):
    if not pos or not neg:
        return float("nan")
    allv = sorted([(v, 1) for v in pos] + [(v, 0) for v in neg])
    # average ranks for ties
    ranks, i = {}, 0
    rank_sum = 0.0
    while i < len(allv):
        j = i
        while j < len(allv) and allv[j][0] == allv[i][0]:
            j += 1
        r = (i + j + 1) / 2.0
        for k in range(i, j):
            if allv[k][1] == 1:
                rank_sum += r
        i = j
    n1, n0 = len(pos), len(neg)
    return (rank_sum - n1 * (n1 + 1) / 2) / (n1 * n0)


def boot(vals, B=5000, seed=0):
    if not vals:
        return (float("nan"),) * 3
    rng = random.Random(seed)
    n = len(vals)
    m = sum(vals) / n
    bs = sorted(sum(vals[rng.randrange(n)] for _ in range(n)) / n for _ in range(B))
    return m, bs[int(0.025 * B)], bs[int(0.975 * B) - 1]


def boot_diff(a, b, B=5000, seed=1):
    rng = random.Random(seed)
    m = sum(a) / len(a) - sum(b) / len(b)
    ds = []
    for _ in range(B):
        x = [a[rng.randrange(len(a))] for _ in a]
        y = [b[rng.randrange(len(b))] for _ in b]
        ds.append(sum(x) / len(x) - sum(y) / len(y))
    ds.sort()
    p = 2 * min(sum(d <= 0 for d in ds), sum(d >= 0 for d in ds)) / B
    return m, ds[int(0.025 * B)], ds[int(0.975 * B) - 1], min(1.0, p)


# ------------------------------------------------------------------ 1
def confidence(files):
    js, md = {}, ["## 1. Confidence of answers with the page", "",
                  "| Model | Page | Answered | Precision | Conf. right | Conf. wrong | AUROC |",
                  "|---|---|---|---|---|---|---|"]
    for f in files:
        m = tag_of(f)
        rows = load(f, "passage")
        js[m] = {}
        for g, gname in GROUPS:
            ans = [r for r in rows.values() if r["group"] == g and r["outcome"] != "abstain"]
            right = [float(r["p_pick"]) for r in ans if r["outcome"] == "correct"]
            wrong = [float(r["p_pick"]) for r in ans if r["outcome"] == "wrong"]
            n_all = sum(1 for r in rows.values() if r["group"] == g)
            prec = 100 * len(right) / max(1, len(ans))
            au = auroc(right, wrong)
            # risk-coverage over all questions of the group: answer the most
            # confident fraction, decline the rest (a model decline stays a decline)
            ranked = sorted(ans, key=lambda r: -float(r["p_pick"]))
            curve = []
            for k in range(1, len(ranked) + 1):
                if k == len(ranked) or k % max(1, len(ranked) // 20) == 0:
                    c = sum(r["outcome"] == "correct" for r in ranked[:k])
                    curve.append([round(100 * k / max(1, n_all), 2), round(100 * c / k, 2)])
            js[m][g] = {"n": n_all, "answered": len(ans), "precision": round(prec, 2),
                        "conf_right": round(sum(right) / len(right), 3) if right else None,
                        "conf_wrong": round(sum(wrong) / len(wrong), 3) if wrong else None,
                        "auroc": round(au, 3), "risk_coverage": curve}
            cr = f"{sum(right) / len(right):.2f}" if right else "–"
            cw = f"{sum(wrong) / len(wrong):.2f}" if wrong else "–"
            md.append(f"| {m} | {gname} | {len(ans)}/{n_all} | {prec:.1f} | {cr} | {cw} | {au:.2f} |")
    md.append("")
    return js, md


# ------------------------------------------------------------------ 2
def family_size(files, pool, recover):
    if not recover or not os.path.exists(recover):
        return {}, ["## 2. Family size", "", "recovery output missing; skipped", ""]
    k_of = {}
    for r in csv.DictReader(open(recover, encoding="utf-8")):
        k_of[(r["source"], r["target"], r["relation"])] = int(r["k"])
    per = {}
    for f in files:
        m = tag_of(f)
        if m not in pool:
            continue
        rows = load(f)
        by = defaultdict(dict)
        for (qid, cond), r in rows.items():
            by[qid][cond] = r
        per[m] = by
    if not per:
        return {}, ["## 2. Family size", "", "no pooled model outputs; skipped", ""]
    models = sorted(per)
    common = sorted(set.intersection(*(set(per[m]) for m in models)))  # fixed order for the bootstrap

    def eff(qid, what):
        """page effect on `what` (decline/wrong/correct), averaged over models"""
        out = 'abstain' if what == 'decline' else what
        v = 0.0
        for m in models:
            d = per[m][qid]
            v += 100 * ((d["passage"]["outcome"] == out) - (d["closed"]["outcome"] == out))
        return v / len(models)

    ref = per[models[0]]
    fam, sil = [], []
    for q in common:
        if "passage" not in ref[q] or "closed" not in ref[q]:
            continue
        r = ref[q]["passage"]
        if r["group"] == "category":
            k = k_of.get((r["source"], r["target"], r["relation"]))
            if k is not None:
                fam.append((k, q))
        elif r["group"] == "silent":
            sil.append(q)
    if len(fam) < 9:
        return {}, ["## 2. Family size", "", f"only {len(fam)} family-only questions matched; skipped", ""]
    fam.sort()
    cuts = [fam[len(fam) // 3][0], fam[2 * len(fam) // 3][0]]
    bins = [("small", [q for k, q in fam if k <= cuts[0]]),
            ("medium", [q for k, q in fam if cuts[0] < k <= cuts[1]]),
            ("large", [q for k, q in fam if k > cuts[1]])]
    sil_dec = [eff(q, "decline") for q in sil]
    js = {"cuts": cuts, "models": models, "bins": {}}
    md = ["## 2. Decline effect by family size", "",
          f"Pooled over {', '.join(models)}. Family list size from the recovery run "
          f"(thirds: up to {cuts[0]}, {cuts[0] + 1} to {cuts[1]}, above {cuts[1]} members). "
          f"Effect = (page effect on declines, family-only) minus (same, silent); points, 95% CI.", "",
          "| Family size | n | Members (median) | Decline effect vs silent | Wrong with page |",
          "|---|---|---|---|---|"]
    for name, qs in bins:
        if not qs:
            continue
        d = [eff(q, "decline") for q in qs]
        m, lo, hi, p = boot_diff(d, sil_dec)
        wrong = 100 * sum(sum(per[mm][q]["passage"]["outcome"] == "wrong" for mm in models) / len(models)
                          for q in qs) / len(qs)
        ks = sorted(k for k, q in fam if q in set(qs))
        js["bins"][name] = {"n": len(qs), "median_k": ks[len(ks) // 2], "decline_effect": [round(m, 2), round(lo, 2), round(hi, 2)],
                            "p": round(p, 4), "wrong_with_page": round(wrong, 2)}
        md.append(f"| {name} | {len(qs)} | {ks[len(ks) // 2]} | {m:+.1f} [{lo:+.1f}, {hi:+.1f}], p={p:.3f} | {wrong:.1f}% |")
    md.append("")
    return js, md


# ------------------------------------------------------------------ 3
def instruct(base_files, inst_files):
    base = {tag_of(f): load(f, "passage") for f in base_files}
    js, md = {"per_model": {}, "pooled": {}}, [
        "## 3. Prompting baseline: tell the model to decline on a broad category", "",
        "With the page, base prompt vs. prompt with the instruction (%). Change in points, "
        "95% bootstrap CI over questions.", "",
        "| Model | Page | n | Declines base → instr. | Correct base → instr. | Wrong base → instr. | Precision base → instr. |",
        "|---|---|---|---|---|---|---|"]
    pooled = defaultdict(lambda: defaultdict(list))
    for f in inst_files:
        m = tag_of(f)
        if m not in base:
            continue
        ins = load(f, "passage")
        js["per_model"][m] = {}
        for g, gname in GROUPS:
            qs = [k for k in ins if ins[k]["group"] == g and k in base[m]]
            if not qs:
                continue

            def rate(src, out):
                return 100 * sum(src[k]["outcome"] == out for k in qs) / len(qs)

            def prec(src):
                a = [k for k in qs if src[k]["outcome"] != "abstain"]
                return 100 * sum(src[k]["outcome"] == "correct" for k in a) / max(1, len(a))
            cell = {}
            for out in ("abstain", "correct", "wrong"):
                d = [100 * ((ins[k]["outcome"] == out) - (base[m][k]["outcome"] == out)) for k in qs]
                mu, lo, hi = boot(d)
                cell[out] = {"base": round(rate(base[m], out), 2), "instruct": round(rate(ins, out), 2),
                             "change": [round(mu, 2), round(lo, 2), round(hi, 2)]}
                for k, v in zip(qs, d):
                    pooled[g][(k, out)].append(v)
            cell["precision"] = {"base": round(prec(base[m]), 2), "instruct": round(prec(ins), 2)}
            js["per_model"][m][g] = dict(cell, n=len(qs))
            md.append(f"| {m} | {gname} | {len(qs)} | {cell['abstain']['base']:.1f} → {cell['abstain']['instruct']:.1f} | "
                      f"{cell['correct']['base']:.1f} → {cell['correct']['instruct']:.1f} | "
                      f"{cell['wrong']['base']:.1f} → {cell['wrong']['instruct']:.1f} | "
                      f"{cell['precision']['base']:.1f} → {cell['precision']['instruct']:.1f} |")
    md += ["", "Pooled over models (each question averaged over the models that ran it):", "",
           "| Page | Declines change | Correct change | Wrong change |", "|---|---|---|---|"]
    for g, gname in GROUPS:
        row = []
        for out in ("abstain", "correct", "wrong"):
            vals = [sum(v) / len(v) for (k, o), v in pooled[g].items() if o == out]
            mu, lo, hi = boot(vals)
            js["pooled"].setdefault(g, {})[out] = [round(mu, 2), round(lo, 2), round(hi, 2)]
            row.append(f"{mu:+.1f} [{lo:+.1f}, {hi:+.1f}]")
        md.append(f"| {gname} | " + " | ".join(row) + " |")
    md.append("")
    return js, md


# ------------------------------------------------------------------ 4
def counterfactual(base_files, fam_files, rem_files, pool):
    """Same named questions, three versions of the page: original, the
    answer's name replaced by its MONDO parent, and the sentences naming it
    removed. All named questions are used (not only all-sibling ones)."""
    def by_tag(files, suffix):
        out = {}
        for f in files:
            b = os.path.basename(f)
            out[b[len("abstain_"):-len(suffix)]] = {r["id"]: r for r in csv.DictReader(open(f, encoding="utf-8"))
                                                    if r["condition"] == "passage"}
        return out
    orig = {}
    for f in base_files:
        t = tag_of(f)
        orig[t] = {r["id"]: r for r in csv.DictReader(open(f, encoding="utf-8"))
                   if r["condition"] == "passage" and r["group"] == "named"}
    fam = by_tag(fam_files, "_edit_family.csv")
    rem = by_tag(rem_files, "_edit_remove.csv")
    models = sorted(t for t in fam if t in rem and t in orig)
    js = {"per_model": {}, "pooled": {}}
    md = ["## 4. Counterfactual page edit (same named questions)", "",
          "Original page names the answer; *family* replaces every mention with its MONDO "
          "parent; *removed* deletes the sentences that mention it. Rates with the page (%).", "",
          "| Model | n | Version | Declines | Correct | Wrong | Precision |", "|---|---|---|---|---|---|---|"]
    pooled = defaultdict(lambda: defaultdict(list))
    for m in models:
        ids = sorted(set(orig[m]) & set(fam[m]) & set(rem[m]))
        if not ids:
            continue
        js["per_model"][m] = {"n": len(ids)}
        for name, src in (("original", orig[m]), ("family", fam[m]), ("removed", rem[m])):
            dec = 100 * sum(src[i]["outcome"] == "abstain" for i in ids) / len(ids)
            cor = 100 * sum(src[i]["outcome"] == "correct" for i in ids) / len(ids)
            wr = 100 * sum(src[i]["outcome"] == "wrong" for i in ids) / len(ids)
            prec = 100 * cor / max(1e-9, cor + wr)
            js["per_model"][m][name] = {"declines": round(dec, 2), "correct": round(cor, 2),
                                        "wrong": round(wr, 2), "precision": round(prec, 2)}
            md.append(f"| {m} | {len(ids)} | {name} | {dec:.1f} | {cor:.1f} | {wr:.1f} | {prec:.1f} |")
        if m in pool:
            for i in ids:
                for out in ("abstain", "wrong", "correct"):
                    pooled[out][i].append((100 * (fam[m][i]["outcome"] == out) - 100 * (rem[m][i]["outcome"] == out),
                                           100 * (fam[m][i]["outcome"] == out) - 100 * (orig[m][i]["outcome"] == out)))
    if pooled:
        md += ["", f"Pooled over {', '.join(m for m in models if m in pool)}: change in points "
                   "(each question averaged over models), 95% bootstrap CI.", "",
               "| Outcome | Family minus removed | Family minus original |", "|---|---|---|"]
        for out, label in (("abstain", "Declines"), ("wrong", "Wrong"), ("correct", "Correct")):
            a = [sum(v[0] for v in vs) / len(vs) for vs in pooled[out].values()]
            b = [sum(v[1] for v in vs) / len(vs) for vs in pooled[out].values()]
            ma, la, ha = boot(a)
            mb, lb, hb = boot(b, seed=2)
            js["pooled"][out] = {"family_minus_removed": [round(ma, 2), round(la, 2), round(ha, 2)],
                                 "family_minus_original": [round(mb, 2), round(lb, 2), round(hb, 2)],
                                 "n": len(a)}
            md.append(f"| {label} | {ma:+.1f} [{la:+.1f}, {ha:+.1f}] | {mb:+.1f} [{lb:+.1f}, {hb:+.1f}] |")
    md.append("")
    return js, md


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--abstain", nargs="*", default=[], help="abstain_<model>_clean.csv files")
    ap.add_argument("--instruct", nargs="*", default=[], help="abstain_<model>_instruct.csv files")
    ap.add_argument("--pool", nargs="*", default=[], help="model tags pooled in sections 2 and 4")
    ap.add_argument("--edit-family", nargs="*", default=[], help="abstain_<model>_edit_family.csv")
    ap.add_argument("--edit-remove", nargs="*", default=[], help="abstain_<model>_edit_remove.csv")
    ap.add_argument("--recover", default="", help="recover_<model>_clean.csv")
    ap.add_argument("--out", default="EXTRAS.md")
    ap.add_argument("--json", default="extras.json")
    a = ap.parse_args()

    base = [f for f in a.abstain if os.path.exists(f)]
    inst = [f for f in a.instruct if os.path.exists(f)]
    md, js = ["# NeusymBridge additional analyses", ""], {}
    if base:
        js["confidence"], l1 = confidence(base)
        js["family_size"], l2 = family_size(base, set(a.pool), a.recover)
        md += l1 + l2
    if inst:
        js["instruct"], l3 = instruct(base, inst)
        md += l3
    ef = [f for f in a.edit_family if os.path.exists(f)]
    er = [f for f in a.edit_remove if os.path.exists(f)]
    if base and ef and er:
        js["counterfactual"], l4 = counterfactual(base, ef, er, set(a.pool))
        md += l4
    with open(a.out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(md) + "\n")
    with open(a.json, "w", encoding="utf-8") as fh:
        json.dump(js, fh, indent=2)
    print("\n".join(md))
    print(f"wrote {a.out} and {a.json}")


if __name__ == "__main__":
    main()
