#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Narrow with the ontology, then let the other end of the fact choose.

The recovery test showed two things. Expanding the family named on the
drug's page gives a short list that usually contains the answer, and the
model cannot pick the right member from that list. This asks whether text
written about the candidates, rather than about the drug, can do the
picking. A page about ulcerative colitis may name the drug even though the
drug's page names only "colitis".

It runs in three parts, and the first needs no network.

1. HOW THE LIST IS BUILT. Two ways, reported side by side.

   oracle  The family is found by climbing from the true answer and asking
           which of its ancestors the page mentions. This is what
           recover.py did. It is an upper bound: a real system does not
           know the true answer when it chooses which family to expand.

   page    Every disease category mentioned anywhere on the drug's page is
           expanded, and the lists are merged. No knowledge of the answer
           is used. This is the honest version of "narrowing works", and
           the number to report.

   Categories whose expansion alone exceeds --max-set are skipped, since a
   page mentioning "cancer" would otherwise contribute every cancer. A
   merged list longer than --max-set counts as too broad to use.

2. EVIDENCE FROM THE CANDIDATE'S END (needs --fetch on a login node).

   wiki      the candidate disease's Wikipedia article names the drug
   wiki_rel  ... within a few sentences of a word fitting the relation
             ("treat", "therapy" for indications; "contraindicated",
             "avoid", "risk" for contraindications)
   pubmed    the number of PubMed records whose title or abstract names
             both the drug and the candidate alongside such a word

   The ontology is what makes these queries possible: it turns one vague
   question into a short list of specific ones.

3. CHOOSING. Each signal is tried as a picker on its own, plus a combined
   one. A pick counts as correct if it is ANY disease the drug truly has
   that relation with, according to the full edge files, because the
   question "which disease is this drug used to treat" has every true
   indication as a right answer. The strict score (only the one sampled
   target) is reported as well.

With --recover-csv it also rescores recover.py's picks the same way. That
matters: recover.py counted a pick of another true indication as wrong for
the family-list conditions, while its random controls were built to avoid
true indications. The family list is made of siblings, so it contains other
true answers far more often, and the original scoring was biased against
it.

    # list building only; no network, a minute
    python3 candidate_check.py --scored me_bal_union.csv \\
        --edges pkg_ind_d2d.csv pkg_con_d2dis.csv \\
        --ancestors mondo_child_parent.csv --wiki-cache wiki_cache \\
        --extra-text pubmed_cache --names-cache gbif_cache \\
        --recover-csv recover_Qwen2.5-7B-Instruct_clean.csv

    # then on a login node: fetch candidate pages and PubMed counts
    python3 candidate_check.py ... --fetch --pubmed --contact you@rpi.edu

Everything fetched is cached, so a rerun is free and an interrupted fetch
resumes. Needs name_tiers.py, router.py, recover.py and second_corpus.py
beside it. Standard library otherwise.
"""

import argparse
import csv
import glob
import json
import math
import os
import re
import statistics
import sys
import time
import urllib.parse
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import name_tiers as nt
    from recover import clean_wikitext
    from router import expand, mcnemar, wilson
    from second_corpus import RawFetcher, EUTILS
except ImportError as e:
    sys.exit(f"name_tiers.py, router.py, recover.py and second_corpus.py "
             f"have to sit beside this script: {e}")

csv.field_size_limit(min(2**31 - 1, sys.maxsize))

CUES = {
    "indication": ["treat", "therap", "indicated", "used for", "used in",
                   "management of", "first-line", "first line", "drug of choice"],
    "contraindication": ["contraindicat", "avoid", "should not", "must not",
                         "not be used", "caution", "risk", "worsen",
                         "exacerbat", "adverse", "warning", "induced"],
    "off-label use": ["off-label", "off label", "treat", "therap", "used for"],
}
PM_QUAL = {
    "indication": "(treat*[tiab] OR therap*[tiab] OR efficac*[tiab])",
    "contraindication": ("(contraindicat*[tiab] OR adverse[tiab] OR "
                         "toxicit*[tiab] OR \"side effect\"[tiab] OR "
                         "\"side effects\"[tiab] OR induced[tiab])"),
    "off-label use": "(\"off-label\"[tiab] OR treat*[tiab] OR therap*[tiab])",
}
QUALIFIER = re.compile(r"\s*\((?:disease|disorder|finding|"
                       r"morphologic abnormality)\)\s*$", re.I)


def wiki_title(name):
    return QUALIFIER.sub("", name).strip()


def toks(s):
    return re.findall(r"[a-z0-9]+", s.lower())


def ngram_index(text, max_n):
    """Every word sequence up to max_n long, plus a singular form of each."""
    w = toks(text)
    out = set()
    for n in range(1, max_n + 1):
        for i in range(len(w) - n + 1):
            g = tuple(w[i:i + n])
            out.add(g)
            last = g[-1]
            if len(last) > 3 and last.endswith("s"):
                out.add(g[:-1] + (last[:-1],))
    return out


def read_full_partners(paths, c_src, c_tgt, c_rel):
    part = defaultdict(set)
    for path in paths:
        if not os.path.exists(path):
            sys.exit(f"missing: {path}")
        with open(path, newline="", encoding="utf-8", errors="replace") as fh:
            rd = csv.DictReader(fh)
            for need in (c_src, c_tgt, c_rel):
                if need not in (rd.fieldnames or []):
                    sys.exit(f"{path} has no column {need}")
            for r in rd:
                s_, t_ = (r.get(c_src) or "").strip(), (r.get(c_tgt) or "").strip()
                if s_ and t_:
                    part[((r.get(c_rel) or "").strip(), s_)].add(t_.lower())
    return part


PICK_ASK = ("The answer is one specific disease. Which of these disease "
            "categories from the passage contains it?")


def pick_family(a, items, children, partners, nt):
    """Step 2 of the hand-off: of the families the page names, which one is
    the question about? A model reads the page and picks one; three rules
    that read no meaning are reported beside it. The chosen family is
    expanded into the 'llm' list, which the evidence pickers then score
    like the other lists."""
    import random
    from abstain_probe import LetterScorer, question_for, LETTERS
    from recover import snippet

    def covers(it, fam):
        lst = expand(fam, children, a.expand_depth)
        truth = partners[(it["rel"], it["src"])]
        return (it["tgt"].lower() in {c.lower() for c in lst},
                bool(truth & {c.lower() for c in lst}))

    k = max(2, min(a.max_fams, len(LETTERS)))
    picks = {}
    if a.family_picks:
        with open(a.family_picks, encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                picks[(r["source"], r["target"], r["relation"])] = r["pick"]
        print(f"\n  read {len(picks):,} family picks from {a.family_picks}")
    else:
        todo = [it for it in items if len(it.get("fams") or []) >= 1]
        prompts, nl = [], []
        for it in todo:
            fams = it["fams"][:k]
            it["_shown"] = fams
            if len(fams) == 1:
                continue
            page = snippet(it["text_for_pick"], fams, lead=400, win=150, cap=1800)
            opts = "\n".join(f"{LETTERS[i]}. {f}" for i, f in enumerate(fams))
            prompts.append(f"Passage:\n{page}\n\nQuestion: "
                           f"{question_for(it['rel'], it['src'])}\n{PICK_ASK}\n"
                           f"Options:\n{opts}\n"
                           f"Answer with the letter of one option only.")
            nl.append(len(fams))
        multi = [it for it in todo if len(it["_shown"]) > 1]
        print(f"\n  scoring {len(prompts):,} pages with {a.pick_model} "
              f"({len(todo) - len(multi):,} pages name one usable family)",
              file=sys.stderr)
        sc = LetterScorer(a.pick_model, a.threads, a.batch_size)
        got = sc.score(prompts, nl) if prompts else []
        rows = []
        for it in todo:
            fams = it["_shown"]
            if len(fams) == 1:
                lp = [0.0]
            else:
                lp = got[multi.index(it)]
            best = max(range(len(fams)), key=lambda i: lp[i])
            picks[(it["src"], it["tgt"], it["rel"])] = fams[best]
            rows.append({"source": it["src"], "target": it["tgt"],
                         "relation": it["rel"], "n_found": len(it["fams"]),
                         "n_shown": len(fams), "shown": json.dumps(fams),
                         "pick": fams[best],
                         "p_pick": round(math.exp(lp[best]), 4)})
        with open(a.picks_out, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) if rows else ["source"])
            w.writeheader()
            w.writerows(rows)
        print(f"  wrote {a.picks_out}: {len(rows):,} picks")

    # how often does each way of choosing land on a family that holds the answer?
    rng = random.Random(a.seed if hasattr(a, "seed") else 0)
    n = len(items)
    tally = defaultdict(lambda: [0, 0])
    for it in items:
        fams = (it.get("fams") or [])[:k]
        if not fams:
            continue
        rules = {"model": picks.get((it["src"], it["tgt"], it["rel"])),
                 "first mentioned": fams[0],
                 "smallest family": min(fams, key=lambda f: (
                     len(expand(f, children, a.expand_depth)), f)),
                 "random": rng.choice(fams)}
        for name, f in rules.items():
            if f:
                t_, any_ = covers(it, f)
                tally[name][0] += t_
                tally[name][1] += any_
        hit = [covers(it, f) for f in fams]
        tally["any shown family (ceiling)"][0] += any(h[0] for h in hit)
        tally["any shown family (ceiling)"][1] += any(h[1] for h in hit)
    print(f"\nSTEP 2: WHICH FAMILY ON THE PAGE?   (percent of all {n:,} "
          f"family-only edges; at most {k} families shown)")
    print("    rule                           list holds sampled answer   any true answer")
    for name in ("model", "first mentioned", "smallest family", "random",
                 "any shown family (ceiling)"):
        t_, any_ = tally[name]
        print(f"    {name:<30} {100 * t_ / n:13.1f}%   {100 * any_ / n:13.1f}%")
    for it in items:
        f = picks.get((it["src"], it["tgt"], it["rel"]))
        it["llm"] = sorted(expand(f, children, a.expand_depth))[:a.max_candidates] if f else None


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scored", required=True)
    ap.add_argument("--edges", nargs="+", required=True,
                    help="FULL edge files, to know every true partner")
    ap.add_argument("--col-source", default="x_name")
    ap.add_argument("--col-target", default="y_name")
    ap.add_argument("--col-relation", default="display_relation")
    ap.add_argument("--ancestors", required=True)
    ap.add_argument("--ancestor-cols", default="")
    ap.add_argument("--flip-ancestors", action="store_true")
    ap.add_argument("--wiki-cache", default="wiki_cache")
    ap.add_argument("--extra-text", nargs="*", default=[])
    ap.add_argument("--names-cache", default="gbif_cache")
    ap.add_argument("--cand-cache", default="candidate_wiki_cache",
                    help="where candidate disease articles are kept")
    ap.add_argument("--pubmed-cache", default="pubmed_pairs.jsonl")
    ap.add_argument("--expand-depth", type=int, default=2)
    ap.add_argument("--max-candidates", type=int, default=64,
                    help="the oracle list cap, as in recover.py")
    ap.add_argument("--max-set", type=int, default=64,
                    help="page-built lists longer than this are too broad")
    ap.add_argument("--page-text", choices=["wiki", "all"], default="wiki",
                    help="scan only the drug's article for categories, or "
                         "the article plus --extra-text")
    ap.add_argument("--recover-csv", default="")
    ap.add_argument("--fetch", action="store_true",
                    help="fetch missing candidate articles (login node)")
    ap.add_argument("--pubmed", action="store_true",
                    help="fetch missing PubMed pair counts (login node)")
    ap.add_argument("--pubmed-mode", choices=["oracle", "page", "both"],
                    default="both")
    ap.add_argument("--popularity", action="store_true",
                    help="also count each candidate's PubMed papers without "
                         "the drug, to test whether the pair signal is more "
                         "than picking the most-studied disease")
    ap.add_argument("--api-key", default="")
    ap.add_argument("--rps", type=float, default=0.0)
    ap.add_argument("--contact", default="")
    ap.add_argument("--limit", type=int, default=0)
    # step 2 of the hand-off: which family on the page holds the answer?
    ap.add_argument("--pick-model", default="",
                    help="score the families found on the page with this model "
                         "and write --picks-out (compute node; no network)")
    ap.add_argument("--picks-out", default="family_picks.csv")
    ap.add_argument("--family-picks", default="",
                    help="a --picks-out file; adds 'llm' lists (the chosen "
                         "family, expanded) next to the oracle and page lists")
    ap.add_argument("--max-fams", type=int, default=10,
                    help="families offered to the model, at most 10 (letters A-J)")
    ap.add_argument("--threads", type=int, default=0)
    ap.add_argument("--batch-size", type=int, default=4)
    ap.add_argument("--out", default="candidate_check.csv")
    a = ap.parse_args()

    for p in (a.scored, a.ancestors):
        if not os.path.exists(p):
            sys.exit(f"missing: {p}")
    if not os.path.isdir(a.wiki_cache):
        sys.exit(f"no article cache at {a.wiki_cache}")

    with open(a.scored, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    anc = nt.load_ancestors(a.ancestors, a.ancestor_cols, a.flip_ancestors)
    children = defaultdict(set)
    for ch, ps in anc.items():
        for p in ps:
            children[p].add(ch)
    partners = read_full_partners(a.edges, a.col_source, a.col_target,
                                  a.col_relation)

    def drug_names(d):
        n = dict(nt.read_names(a.names_cache, "redir", d) or nt.EMPTY)
        n["synonyms"], n["ancestors"] = [], []
        return [x for x in nt.tier_sets(d, n)[2] if len(x) >= 4]

    def raw_text(src, extra):
        parts = []
        t = nt.read_article(a.wiki_cache, src)
        if t:
            parts.append(t)
        if extra:
            for d in a.extra_text:
                for p in sorted(glob.glob(os.path.join(d, nt._safe(src) + "*.txt"))):
                    with open(p, encoding="utf-8", errors="replace") as fh:
                        parts.append(fh.read())
        return "\n\n".join(parts) if parts else None

    # ---------------------------------------- the edges, as recover.py saw them
    items = []
    for r in rows:
        if str(r.get("tier", "")).strip() != "3":
            continue
        src, tgt, rel = r["source"], r["target"], r["relation"]
        text = raw_text(src, True)
        if text is None:
            continue
        ancs = [x["scientific"] for x in nt.climb(tgt, anc, a.expand_depth)]
        matched = [x for x in ancs
                   if x and not nt.too_generic(x) and nt.mentions(text, x)]
        if not matched:
            continue
        best = None
        for x in matched:
            s_ = expand(x, children, a.expand_depth)
            if best is None or len(s_) < len(best):
                best = s_
        oracle = sorted(best)[:a.max_candidates]
        if len(oracle) < 2:
            continue
        items.append({"src": src, "tgt": tgt, "rel": rel, "oracle": oracle})
    if a.limit:
        items = items[:a.limit]
    print(f"\n{len(items):,} family-only edges, the same set recover.py scores")

    # ------------------------------------------------------ page-built lists
    cats = [p for p, cs in children.items()
            if len(cs) >= 2 and not nt.too_generic(p)]
    cat_toks = {p: tuple(toks(p)) for p in cats}
    cat_size = {p: len(expand(p, children, a.expand_depth)) for p in cats}
    max_n = min(8, max((len(t) for t in cat_toks.values()), default=1))
    print(f"  {len(cats):,} ontology categories can be read off a page")

    broad = 0
    for it in items:
        text = raw_text(it["src"], a.page_text == "all") or ""
        grams = ngram_index(clean_wikitext(text), max_n)
        found = [p for p in cats if cat_toks[p] in grams]
        usable = [p for p in found if cat_size[p] <= a.max_set]
        union = set()
        for p in usable:
            union |= expand(p, children, a.expand_depth)
        it["page_cats"] = len(found)
        it["page_usable"] = len(usable)
        # the usable families in the order the page first mentions them
        clean = clean_wikitext(text).lower()
        pos = {}
        for p in usable:
            m = re.search(r"\b" + r"\W+".join(map(re.escape, cat_toks[p])) + r"s?\b",
                          clean)
            pos[p] = m.start() if m else len(clean)
        it["fams"] = sorted(usable, key=lambda p: (pos[p], p))
        it["text_for_pick"] = text
        if len(union) > a.max_set:
            it["page"] = None
            broad += 1
        else:
            it["page"] = sorted(union)

    def list_stats(name, key):
        have = [it for it in items if it.get(key)]
        sizes = [len(it[key]) for it in have]
        hit_t = sum(1 for it in have
                    if it["tgt"].lower() in {c.lower() for c in it[key]})
        hit_any = sum(1 for it in have if partners[(it["rel"], it["src"])]
                      & {c.lower() for c in it[key]})
        n = len(items)
        print(f"  {name:<7} usable lists {len(have):>4,} of {n:,}   "
              f"contains the sampled answer {100 * hit_t / n:5.1f}%   "
              f"any true answer {100 * hit_any / n:5.1f}%   "
              f"size median {statistics.median(sizes) if sizes else 0:>4.0f}"
              f"  mean {statistics.fmean(sizes) if sizes else 0:5.1f}")

    print("\nHOW GOOD IS THE LIST?   (percent of all family-only edges)")
    list_stats("oracle", "oracle")
    list_stats("page", "page")
    if broad:
        print(f"  {broad:,} page-built lists exceeded {a.max_set} candidates "
              f"and count as too broad")
    cats_per = [it["page_cats"] for it in items]
    print(f"  categories found per page: median "
          f"{statistics.median(cats_per) if cats_per else 0:.0f}, "
          f"usable after the size cap: median "
          f"{statistics.median([it['page_usable'] for it in items]) if items else 0:.0f}")
    print("\n  The oracle row is what recover.py assumed. The page row is what a")
    print("  system that does not know the answer actually gets.")

    # ------------------------------------------- step 2: choose the family
    if a.pick_model or a.family_picks:
        pick_family(a, items, children, partners, nt)
        list_stats("llm", "llm")
        if a.pick_model and not a.family_picks:
            return

    # --------------------------------------------------------------- fetch
    want_oracle = a.pubmed_mode in ("oracle", "both")
    want_page = a.pubmed_mode in ("page", "both")
    all_cands = set()
    pairs = set()
    for it in items:
        for key, want in (("oracle", want_oracle), ("page", want_page),
                          ("llm", want_page)):
            lst = it.get(key) or []
            all_cands.update(lst)
            if want:
                pairs.update((it["src"], it["rel"], c) for c in lst)
    titles = sorted({wiki_title(c) for c in all_cands})
    have_pages = sum(1 for t in titles
                     if nt.read_article(a.cand_cache, t) is not None)
    print(f"\nCANDIDATE ARTICLES   {len(titles):,} distinct, "
          f"{have_pages:,} cached")
    if a.fetch:
        missing = [t for t in titles if nt.read_article(a.cand_cache, t) is None]
        if missing:
            print(f"  fetching {len(missing):,} at about 3 per second ...",
                  file=sys.stderr)
            fx = nt.Fetcher(rps=3.0, contact=a.contact)
            nt.fetch_articles(fx, missing, a.cand_cache, batch=8)
            print(f"  {fx.report()}", file=sys.stderr)
    elif have_pages < len(titles):
        print(f"  {len(titles) - have_pages:,} not cached; add --fetch on a "
              f"login node")

    pm = {}
    if os.path.exists(a.pubmed_cache):
        with open(a.pubmed_cache, encoding="utf-8") as fh:
            for line in fh:
                try:
                    d = json.loads(line)
                    pm[d["q"]] = d["n"]
                except (ValueError, KeyError):
                    continue

    def pm_query(src, rel, cand):
        qual = PM_QUAL.get(rel, "")
        q = (f'"{src.replace(chr(34), "")}"[tiab] AND '
             f'"{wiki_title(cand).replace(chr(34), "")}"[tiab]')
        return q + (f" AND {qual}" if qual else "")

    def pop_query(cand):
        return f'"{wiki_title(cand).replace(chr(34), "")}"[tiab]'

    queries = {pm_query(*p) for p in pairs}
    if a.popularity:
        queries |= {pop_query(c) for (_, _, c) in pairs}
    queries = sorted(queries)
    todo_q = [q for q in queries if q not in pm]
    rps = a.rps or (8.0 if a.api_key else 2.5)
    print(f"\nPUBMED PAIR COUNTS   {len(queries):,} queries, "
          f"{len(queries) - len(todo_q):,} cached")
    if todo_q and not a.pubmed:
        print(f"  {len(todo_q):,} not cached; add --pubmed on a login node "
              f"(about {len(todo_q) / rps / 60:.0f} min at {rps:.1f}/s"
              f"{'' if a.api_key else '; an NCBI API key makes it 3x faster'})")
    if todo_q and a.pubmed:
        fx = RawFetcher(rps=rps, contact=a.contact)
        key = f"&api_key={a.api_key}" if a.api_key else ""
        t0 = time.time()
        with open(a.pubmed_cache, "a", encoding="utf-8") as fh:
            for i, q in enumerate(todo_q):
                url = (f"{EUTILS}/esearch.fcgi?db=pubmed&rettype=count"
                       f"&retmode=json&term={urllib.parse.quote(q)}{key}")
                body = fx.get(url)
                if body is None:
                    continue                    # unknown; retried next run
                try:
                    n = int(json.loads(body)["esearchresult"]["count"])
                except (ValueError, KeyError, TypeError):
                    continue
                pm[q] = n
                fh.write(json.dumps({"q": q, "n": n}) + "\n")
                if (i + 1) % 100 == 0:
                    fh.flush()
                    left = (len(todo_q) - i - 1) / max(
                        1e-9, (i + 1) / (time.time() - t0)) / 60
                    print(f"    {i + 1:,}/{len(todo_q):,}, about {left:.0f} "
                          f"min left", file=sys.stderr, flush=True)
        print(f"  {fx.report()}", file=sys.stderr)

    # --------------------------------------------------------------- evidence
    page_cache = {}

    def cand_page(c):
        t = wiki_title(c)
        if t not in page_cache:
            raw = nt.read_article(a.cand_cache, t)
            page_cache[t] = clean_wikitext(raw) if raw else None
        return page_cache[t]

    def evidence(it, c):
        names = it.setdefault("_names", drug_names(it["src"]))
        page = cand_page(c)
        w = wr = 0
        if page:
            low = page.lower()
            for nm in names:
                if not nt.mentions(page, nm):
                    continue
                w = 1
                pat = r"\b" + re.escape(nm.lower()) + r"s?\b"
                for m in re.finditer(pat, low):
                    win = low[max(0, m.start() - 250): m.end() + 250]
                    if any(cue in win for cue in CUES.get(it["rel"], [])):
                        wr = 1
                        break
                if wr:
                    break
        q = pm_query(it["src"], it["rel"], c)
        return {"page": page is not None and page != "", "wiki": w,
                "wiki_rel": wr, "pubmed": pm.get(q),
                "pop": pm.get(pop_query(c))}

    def choose(ev, signal):
        """Pick the single best candidate, or None if no signal or a tie."""
        if signal == "wiki":
            sc = {c: e["wiki_rel"] * 2 + e["wiki"] for c, e in ev.items()}
        elif signal == "pubmed":
            sc = {c: (e["pubmed"] or 0) for c, e in ev.items()}
        elif signal == "popular":
            # ignores the drug: the most-studied disease in the list
            sc = {c: (e["pop"] or 0) for c, e in ev.items()}
        elif signal == "pubmed_norm":
            # share of the disease's papers that also name the drug
            sc = {c: ((e["pubmed"] or 0) / (e["pop"] or 1)) if e["pop"]
                  else 0 for c, e in ev.items()}
        else:
            sc = {c: 2 * e["wiki_rel"] + e["wiki"] +
                  math.log1p(e["pubmed"] or 0) for c, e in ev.items()}
        top = max(sc.values()) if sc else 0
        if top <= 0:
            return None, "none"
        best = [c for c, v in sc.items() if v == top]
        return (best[0], "pick") if len(best) == 1 else (None, "tie")

    print(f"\n{'=' * 78}\nCHOOSING FROM THE CANDIDATE'S END")
    records = []
    for mode in ("oracle", "page", "llm"):
        sel = [it for it in items if it.get(mode)]
        if not sel:
            continue
        cover = {"page": 0, "wiki": 0, "pubmed_known": 0}
        sigs = ["wiki", "pubmed", "combined"]
        if a.popularity:
            sigs += ["popular", "pubmed_norm"]
        tallies = {s: defaultdict(int) for s in sigs}
        set_hit = set_n = 0
        set_sizes = []
        for it in sel:
            ev = {c: evidence(it, c) for c in it[mode]}
            truth = partners[(it["rel"], it["src"])]
            cover["page"] += sum(e["page"] for e in ev.values())
            cover["wiki"] += sum(e["wiki"] for e in ev.values())
            cover["pubmed_known"] += sum(e["pubmed"] is not None
                                         for e in ev.values())
            rec = {"mode": mode, "source": it["src"], "target": it["tgt"],
                   "relation": it["rel"], "list_size": len(it[mode]),
                   "true_in_list": len(truth & {c.lower() for c in it[mode]})}
            for s in sigs:
                pick, status = choose(ev, s)
                tallies[s][status] += 1
                if pick is not None:
                    ok_any = pick.lower() in truth
                    ok_strict = pick.lower() == it["tgt"].lower()
                    tallies[s]["any"] += ok_any
                    tallies[s]["strict"] += ok_strict
                rec[f"pick_{s}"] = pick or ""
                rec[f"status_{s}"] = status
                rec[f"correct_{s}"] = int(pick is not None and
                                          pick.lower() in truth)
            # the evidence-narrowed list: every candidate with any signal
            kept = [c for c, e in ev.items()
                    if e["wiki"] or (e["pubmed"] or 0) > 0]
            if kept:
                set_n += 1
                set_sizes.append(len(kept))
                set_hit += bool(truth & {c.lower() for c in kept})
            rec["evidence_set_size"] = len(kept)
            rec["evidence_set_has_true"] = int(bool(
                truth & {c.lower() for c in kept}))
            it[f"_rec_{mode}"] = rec
            records.append(rec)

        n_c = sum(len(it[mode]) for it in sel)
        print(f"\n  {mode.upper()} lists   {len(sel):,} edges, "
              f"{n_c:,} candidates")
        print(f"    candidates with a Wikipedia article        "
              f"{100 * cover['page'] / n_c:5.1f}%")
        print(f"    candidates whose article names the drug    "
              f"{100 * cover['wiki'] / n_c:5.1f}%")
        print(f"    candidates with a PubMed count fetched     "
              f"{100 * cover['pubmed_known'] / n_c:5.1f}%")
        print("    signal     picks    ties   no signal   right when it picks"
              "      right over all edges")
        for s in sigs:
            t = tallies[s]
            picks = t["pick"]
            p_any = wilson(t["any"], picks)[0] if picks else 0
            print(f"    {s:<11} {picks:>4,} {t['tie']:>7,} {t['none']:>10,}"
                  f"      {p_any:5.1f}% (sampled only "
                  f"{100 * t['strict'] / picks if picks else 0:5.1f}%)"
                  f"   {100 * t['any'] / len(sel):5.1f}%")
        if set_n:
            print(f"    evidence-narrowed list: {set_n:,} edges, median size "
                  f"{statistics.median(set_sizes):.0f}, contains a true "
                  f"answer {100 * set_hit / set_n:5.1f}%")

    # ------------------------------------- end to end, with no oracle at all
    if any(it.get("llm") for it in items):
        n = len(items)
        print(f"\n{'=' * 78}\nEND TO END, NO ORACLE   ({n:,} family-only edges; "
              f"a fact with no usable list counts as a miss)")
        print("    list built from    signal      right over all edges")
        for mode in ("page", "llm"):
            for s_ in ("combined", "popular"):
                ok = sum(int((it.get(f"_rec_{mode}") or {}).get(f"correct_{s_}", 0))
                         for it in items)
                print(f"    {mode:<18} {s_:<11} {100 * ok / n:6.1f}%")

    # ------------------------------------------- recover.py, rescored fairly
    if a.recover_csv:
        if not os.path.exists(a.recover_csv):
            print(f"\nskip rescoring: {a.recover_csv} not found")
        else:
            with open(a.recover_csv, encoding="utf-8") as fh:
                rc = list(csv.DictReader(fh))
            by_edge = {(it["src"], it["tgt"], it["rel"]): it for it in items}
            conds = [c[5:] for c in rc[0] if c.startswith("pick_")]
            print(f"\n{'=' * 78}\nRECOVER.PY, RESCORED   "
                  f"{os.path.basename(a.recover_csv)}")
            print("  A pick of any true partner counts as right, for every "
                  "condition alike.")
            got = {c: [0, 0] for c in conds}
            multi = []
            fused = [0, 0]
            disc = [0, 0]
            same = [0, 0]           # evidence+fallback vs the model alone
            real = 0                # page-built list, evidence pick only
            for r in rc:
                truth = partners[(r["relation"], r["source"])]
                it = by_edge.get((r["source"], r["target"], r["relation"]))
                if it:
                    multi.append(len(truth & {c.lower() for c in it["oracle"]}))
                for c in conds:
                    pk = (r.get(f"pick_{c}") or "").lower()
                    got[c][0] += int(r.get(f"hit_{c}", 0) or 0)
                    got[c][1] += int(bool(pk) and pk in truth)
                # evidence first, the model's family-list pick otherwise
                rec = it.get("_rec_oracle") if it else None
                ep = (rec or {}).get("pick_combined") or ""
                final = (ep or r.get("pick_ours") or "").lower()
                ok = int(bool(final) and final in truth)
                fused[0] += ok
                fused[1] += 1
                rag_ok = int((r.get("pick_rag_pool") or "").lower() in truth)
                disc[0] += int(ok and not rag_ok)
                disc[1] += int(rag_ok and not ok)
                ours_ok = int((r.get("pick_ours") or "").lower() in truth)
                same[0] += int(ok and not ours_ok)
                same[1] += int(ours_ok and not ok)
                prec = it.get("_rec_page") if it else None
                pp = ((prec or {}).get("pick_combined") or "").lower()
                real += int(bool(pp) and pp in truth)
            n = len(rc)
            print("    condition     as scored before   any true answer")
            for c in conds:
                print(f"    {c:<12} {100 * got[c][0] / n:13.1f}%  "
                      f"{100 * got[c][1] / n:14.1f}%")
            if multi:
                print(f"\n    true answers inside the family list: mean "
                      f"{statistics.fmean(multi):.2f}, and "
                      f"{100 * sum(m > 1 for m in multi) / len(multi):.1f}% "
                      f"of lists hold more than one")
            print(f"\n    candidate evidence first, model pick as fallback: "
                  f"{100 * fused[0] / max(1, fused[1]):5.1f}%")
            m = mcnemar(disc[0], disc[1])
            print(f"    against page-in-prompt (rag_pool): this only "
                  f"{disc[0]:,}, rag_pool only {disc[1]:,}, "
                  f"p={m['p']:.3g}")
            m2 = mcnemar(same[0], same[1])
            print(f"    against the model alone on the same family list "
                  f"(ours): this only {same[0]:,}, ours only {same[1]:,}, "
                  f"p={m2['p']:.3g}")
            print(f"\n    end to end, no oracle: family list built from the "
                  f"page, evidence pick,\n    nothing otherwise: "
                  f"{100 * real / max(1, n):5.1f}% of {n:,} edges "
                  f"(rag_pool {100 * got.get('rag_pool', [0, 0])[1] / max(1, n):.1f}%)")
            print("    rag_pool's lists are the answer among random diseases, "
                  "so the page's family\n    name lets it eliminate; the "
                  "comparison is reported, not endorsed.")

    if records:
        cols = list(records[0].keys())
        with open(a.out, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            w.writerows(records)
        print(f"\nwrote {a.out}: {len(records):,} rows")


if __name__ == "__main__":
    main()
