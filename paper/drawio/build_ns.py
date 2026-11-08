"""draw.io figures for the NeusymBridge paper (fig_concept, fig_edit)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_drawio import *   # D, colors, F

HERE = os.path.dirname(os.path.abspath(__file__))
RED, RED_D = "#E5484D", "#C9353A"
HL = "background-color:#FFE7A3;padding:0 2px;border-radius:3px;"


def concept():
    d = D("concept", 1400, 440)
    # 1 question & retrieval
    d.panel(6, 6, 300, 428, 1, "Retriever agent", PURPLE, PURPLE_D, PURPLE_L)
    d.avatar(60, 96, 30, "person", "User", PURPLE, PURPLE_D, PURPLE_L)
    d.v(104, 56, 192, 70, "shape=callout;perimeter=calloutPerimeter;direction=west;position=0.3;position2=0.5;"
        "base=14;size=14;rounded=1;arcSize=16;html=1;fillColor=#FFFFFF;strokeColor=#C9C2EA;shadow=1;"
        f"whiteSpace=wrap;fontFamily={F};fontSize=14;fontStyle=2;fontColor={INK};spacingLeft=14;",
        "“What does lovastatin treat?”")
    rt = d.avatar(60, 214, 30, "robot", "Retriever", PURPLE, PURPLE_D, PURPLE_L, badge="magnifying_glass_tilted_right")
    d.icon("globe_with_meridians", 104, 176, 26); d.code(136, 177, 160, 24, "wiki", "page", '"lovastatin"', fs=10.5)
    d.icon("books", 104, 210, 26); d.code(136, 211, 160, 24, "pubmed", "search", "drug", fs=10.5)
    pg = d.card(18, 274, 278, 150, ec="#C9C2EA", lw=1.3)
    d.icon("page_facing_up", 26, 282, 30)
    d.text(62, 282, 226, 30, "<b>Retrieved page</b> · true and relevant", fs=12, al="left")
    d.text(30, 316, 256, 66, f"“Lovastatin is a statin used to treat <span style='{HL}'><b>hyperlipidemia</b></span> "
           "and to lower cardiovascular risk.”", fs=12.5, i=True, al="left", va="top")
    d.text(30, 388, 256, 30, "graph answer: <b>familial hyperlipidemia</b>", fs=11.5, col=PURPLE_D, al="left")
    d.chevron(307, 207)

    # 2 page-type check
    d.panel(324, 6, 300, 428, 2, "Checker agent", SLATE, SLATE_D, "#F2F4F7")
    d.avatar(386, 100, 36, "detective", "Checker", SLATE, SLATE_D, "#EEF1F5")
    d.text(434, 60, 182, 70, "Does the page name the <b>answer</b>, only its <b>family</b>, or <b>nothing</b>?",
           fs=12, al="left", col=INK)
    rows = [("named → answer", "precision 84–95%", GREEN, GREEN_D, "check_mark_button", 1),
            ("family only → resolvable", "precision 45–59%", GOLD, "#C48A0E", "puzzle_piece", 2.4),
            ("silent → decline", "nothing to resolve", GREY, "#80868B", "cross_mark", 1)]
    fam = None
    for k, (a, b, c, cd, ic, lw) in enumerate(rows):
        y = 168 + k * 68
        cid = d.card(336, y, 276, 58, ec=c, lw=lw)
        if k == 1: fam = cid
        d.v(336, y, 10, 58, f"rounded=1;absoluteArcSize=1;arcSize=8;html=1;fillColor={c};strokeColor=none;")
        d.icon(ic, 354, y + 13, 32)
        d.text(396, y + 6, 210, 24, a, fs=13, b=True, al="left")
        d.text(396, y + 30, 210, 22, b, fs=11.5, col=INK2, al="left")
    clade = d.card(344, 372, 268, 54, ec=RED, lw=1.6, fc="#FFF1F1")
    d.icon("warning", 352, 383, 30)
    d.text(390, 374, 218, 50, "<b><font color='#C9353A'>CLADE</font></b>: readers skip the check and answer "
           "anyway, precision 45–59% (species 22–28%)", fs=11, al="left", col=INK)
    d.link(fam, clade, RED, 1.8, dashed=1, pts=[(330, 265), (330, 399)],
           extra="exitX=0;exitY=0.5;entryX=0;entryY=0.5;")
    d.chevron(625, 207)

    # 3 ontology agent
    d.panel(642, 6, 370, 428, 3, "Ontology agent", BLUE, BLUE_D, "#F7FAFF")
    on = d.avatar(700, 100, 34, "robot", "Ontology", BLUE, BLUE_D, BLUE_L, badge="file_cabinet")
    d.code(746, 62, 256, 26, "mondo", "children", '"hyperlipidemia", depth=2', fs=10.5)
    d.text(746, 92, 256, 40, "the family name indexes a short, finite candidate list", fs=11.5, col=BLUE_D, i=True, al="left")
    root = d.chip(660, 176, 150, 32, "hyperlipidemia", GOLD, "#C48A0E", fs=12.5)
    kids = [("familial hyperlipidemia", GREEN, GREEN_D), ("familial combined", BLUE, BLUE_D),
            ("hypertriglyceridemia", BLUE, BLUE_D), ("+ 11 more members", "#A9C9F5", "#8DB5EE")]
    kid0 = None
    for k, (s_, c, cd) in enumerate(kids):
        cid = d.chip(840, 140 + k * 36, 162, 26, s_, c, cd, fs=11.5)
        kid0 = kid0 or cid
        d.link(root, cid, BLUE, 1.2, extra="exitX=1;exitY=0.5;entryX=0;entryY=0.5;", es="elbowEdgeStyle")
    d.icon("check_mark_button", 990, 132, 18)
    d.text(660, 214, 150, 40, "MONDO, 2 levels down", fs=10.5, col=BLUE_D, i=True)
    d.card(656, 296, 344, 58, ec=GREEN, lw=1.3)
    d.icon("check_mark_button", 664, 309, 32)
    d.text(704, 298, 290, 54, "<b>family given:</b> the list holds the answer <b>98.5%</b> of the time, median 14 candidates",
           fs=11.5, al="left")
    d.card(656, 364, 344, 60, ec=ORANGE, lw=1.3)
    d.icon("warning", 664, 378, 32)
    d.text(704, 366, 290, 56, "<b>family read off the page:</b> only <b>19.8%</b>; pages name many categories, the bottleneck",
           fs=11.5, al="left")
    d.link(fam, on, GOLD, 2.2, extra="exitX=1;exitY=0.5;entryX=0;entryY=0.5;")
    d.chevron(1013, 207)

    # 4 chooser agent
    d.panel(1030, 6, 364, 428, 4, "Chooser agent", GREEN, GREEN_D, GREEN_L)
    ch = d.avatar(1088, 100, 34, "robot", "Chooser", GREEN, GREEN_D, GREEN_L, badge="balance_scale")
    d.text(1136, 62, 250, 40, "accuracy when choosing within the given family", fs=11.5, col=GREEN_D, b=True, al="left")
    bars = [("bar_chart", "popularity prior", 46.8, GREEN), ("books", "evidence, then model", 41.7, "#3FBF8F"),
            ("robot", "model alone", 35.9, "#8FD9B9"), ("books", "PubMed co-mention", 35.9, "#8FD9B9"),
            ("page_facing_up", "page in prompt (RAG)", 32.7, GREY)]
    for k, (ic, s, v, c) in enumerate(bars):
        y = 170 + k * 27
        d.icon(ic, 1042, y + 1, 22)
        d.text(1070, y, 138, 24, s, fs=11, al="left")
        d.v(1210, y + 3, round(v / 50 * 130), 18, f"rounded=1;arcSize=30;html=1;fillColor={c};strokeColor=none;")
        d.text(1214 + round(v / 50 * 130), y, 50, 24, f"{v:.1f}%", fs=11, b=True, al="left")
    d.link(kid0, ch, GREEN, 1.6, extra="exitX=1;exitY=0.5;entryX=0;entryY=0.5;")
    d.card(1042, 310, 340, 114, ec=GREEN, lw=1.6)
    d.icon("check_mark_button", 1052, 320, 34)
    d.text(1094, 316, 280, 20, "ANSWER, OR HAND BACK THE LIST", fs=11, col=GREEN_D, b=True, al="left")
    d.text(1094, 338, 280, 26, "familial hyperlipidemia", fs=14, b=True, al="left")
    d.chip(1094, 368, 200, 22, "MONDO family + PubMed", GREEN_L, GREEN_L, fs=11, fc=GREEN_D, shadow=0)
    d.text(1094, 394, 280, 26, "answer only when one candidate clearly leads", fs=10.5, col=INK2, i=True, al="left")
    d.save(os.path.join(HERE, "fig_concept.drawio"))


def edit():
    d = D("edit", 600, 400)
    d.panel(4, 4, 592, 392, "", "One question, three versions of its page", SLATE, SLATE_D, "#F7F8FA")
    d.icon("robot", 556, 10, 30)
    rows = [("original", GREEN, GREEN_D, "check_mark_button",
             [f"treat <span style='{HL}'><b>familial hyperlipidemia</b></span>",
              f"feeds on <span style='{HL}'><b>A. plantaginifolia</b></span>"],
             [(70.2, 10.5, 19.2), (63.8, 6.9, 29.3)], ""),
            ("family", GOLD, "#C48A0E", "puzzle_piece",
             [f"treat <span style='{HL}'><b>hyperlipidemia</b></span>",
              f"feeds on <span style='{HL}'><b>Antennaria</b></span>"],
             [(49.3, 20.0, 30.8), (32.9, 18.1, 49.0)], "wrong vs original: +9.5 / +11.1"),
            ("removed", GREY, "#80868B", "cross_mark",
             ["<s>sentence deleted</s>", ""],
             [(36.9, 14.9, 48.2), (11.9, 11.3, 76.8)], "declines, family − removed: −17.4 / −27.7")]
    for k, (tag, c, cd, ic, snips, bars, note) in enumerate(rows):
        y = 52 + k * 104
        d.card(14, y, 236, 92, ec=c, lw=2 if k == 1 else 1.2)
        d.chip(24, y + 8, 110, 26, tag, c, cd, fs=14)
        d.icon(ic, 214, y + 8, 24)
        d.text(24, y + 40, 222, 22, "“… " + snips[0] + "”", fs=12.5, i=True, al="left")
        if snips[1]:
            d.text(24, y + 62, 222, 22, "“… " + snips[1] + "”", fs=12.5, i=True, al="left")
        for j, ((cor, wr, de), lab) in enumerate(zip(bars, ["disease", "species"])):
            yy = y + 6 + j * 30
            d.text(260, yy, 62, 26, lab, fs=12, b=True, al="left", col=INK2)
            W, x = 268, 324
            for v, col in [(cor, GREEN), (wr, RED), (de, GREY)]:
                w = round(W * v / 100)
                d.v(x, yy, w, 26, f"rounded=0;html=1;fillColor={col};strokeColor=#FFFFFF;strokeWidth=1;"
                    f"fontColor=#FFFFFF;fontFamily={F};fontSize=12.5;fontStyle=1;", f"{v:.0f}" if w > 20 else "")
                x += w
        if note:
            d.text(260, y + 66, 336, 24, note, fs=12.5, col=cd if k == 1 else INK2, b=True, al="left")
    for k, (lab, col) in enumerate([("correct", GREEN), ("wrong", RED), ("declines", GREY)]):
        d.v(262 + k * 110, 365, 16, 16, f"rounded=1;html=1;fillColor={col};strokeColor=none;")
        d.text(284 + k * 110, 360, 86, 26, lab, fs=14, al="left")
    d.text(14, 360, 244, 26, "% of questions, with the page", fs=13, col=INK2, i=True, al="left")
    d.save(os.path.join(HERE, "fig_edit.drawio"))


concept(); edit(); print("ok")
