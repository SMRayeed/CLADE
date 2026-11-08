import sys, matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
out=sys.argv[1]
plt.rcParams.update({"font.family":"DejaVu Sans","font.size":10})
fig,(a,b)=plt.subplots(1,2,figsize=(10.6,3.6),gridspec_kw={"width_ratios":[1.5,1]})
rows=[("Declines: family-only\nvs. silent page",-13.8,-20.3,-7.5,-14.3,-18.7,-9.6),
      ("Wrong answers: family-only\nvs. silent page",7.7,1.2,14.0,11.6,7.5,15.4),
      ("Declines: page edited to\nfamily vs. fact removed",-17.4,-23.6,-11.5,-27.7,-32.2,-23.5)]
cP,cG="#2E7BE0","#1AA874"
for i,(lab,p,pl,ph,g,gl,gh) in enumerate(rows):
    y=len(rows)-1-i
    a.errorbar(p,y+.15,xerr=[[p-pl],[ph-p]],fmt="o",color=cP,capsize=3,ms=7,label="PrimeKG (drugs)" if i==0 else None)
    a.errorbar(g,y-.15,xerr=[[g-gl],[gh-g]],fmt="s",color=cG,capsize=3,ms=7,label="GloBI (species)" if i==0 else None)
a.axvline(0,color="#555",ls="--",lw=1)
a.set_yticks(range(len(rows)));a.set_yticklabels([r[0] for r in rows][::-1])
a.set_xlabel("change in percentage points (95% CI)");a.set_title("Same effect in both domains",fontweight="bold")
a.legend(loc="lower right",frameon=False,fontsize=9);a.grid(axis="x",alpha=.3)
for s in ("top","right"): a.spines[s].set_visible(False); b.spines[s].set_visible(False)
d=[("PrimeKG",(0.73,0.87),(0.59,0.72)),("GloBI",(0.82,0.86),(0.52,0.68))]
for i,(n,nm,fm) in enumerate(d):
    b.plot(nm,[i+.12]*2,color="#7B5BD6",lw=8,solid_capstyle="round",label="named page" if i==0 else None)
    b.plot(fm,[i-.12]*2,color="#F07537",lw=8,solid_capstyle="round",label="family-only page" if i==0 else None)
b.axvline(.5,color="#555",ls="--",lw=1);b.text(.505,-.45,"coin flip",fontsize=8,color="#555")
b.set_yticks([0,1]);b.set_yticklabels([x[0] for x in d]);b.set_xlim(.45,.92);b.set_ylim(-.5,1.6)
b.set_xlabel("AUROC of confidence (range over models)");b.set_title("Confidence stops helping",fontweight="bold")
b.legend(loc="upper right",frameon=False,fontsize=9);b.grid(axis="x",alpha=.3)
plt.tight_layout();plt.savefig(out,dpi=200,facecolor="white")
