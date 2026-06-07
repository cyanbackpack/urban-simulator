import json, numpy as np
t=json.load(open("terrain_lake_core.json"))
CELL=t["cell_size_m"]; W=t["width"]; H=t["height"]
g=np.array([list(r) for r in t["rows"]])
def rect(cx,cy,wkm,hkm):
    w,h=wkm*500,hkm*500
    return [[cx-w,cy-h],[cx+w,cy-h],[cx+w,cy+h],[cx-w,cy+h]]
def buildable(poly):
    xs=[p[0] for p in poly]; ys=[p[1] for p in poly]
    x0,x1=int(min(xs)//CELL),int(max(xs)//CELL); y0,y1=int(min(ys)//CELL),int(max(ys)//CELL)
    for y in range(max(0,y0),min(H,y1+1)):
        for x in range(max(0,x0),min(W,x1+1)):
            if g[y,x] in ("~","^"): return False
    return True
cand=[
 ("CBD",54000,57000,5,5),("COMMERCIAL",54000,63000,10,3),("COMMERCIAL",46000,57000,4,6),
 ("RES_HIGH",64000,58000,7,8),("RES_MED",15000,55000,10,16),("RES_MED",90000,52000,8,12),
 ("RES_LOW",50000,68000,28,5),("SUBURB",15000,20000,12,16),
 ("UNIVERSITY",70000,68000,5,5),("MEDICAL",63000,68000,4,4),
 ("INDUSTRIAL",86000,71000,6,5),("LOGISTICS",92000,71000,5,5),
 ("PARK",14000,32000,5,5),("PARK",90000,20000,8,6),
 ("PARK",60000,63000,3,3),("PARK",24000,55000,3,3),
]
zones=[]; dropped=[]
for u,cx,cy,wk,hk in cand:
    p=rect(cx,cy,wk,hk)
    (zones if buildable(p) else dropped).append((u,cx,cy))
    if buildable(p): zones.append({"use":u,"polygon":p}) if False else None
zones=[{"use":u,"polygon":rect(cx,cy,wk,hk)} for (u,cx,cy,wk,hk) in cand if buildable(rect(cx,cy,wk,hk))]
print("dropped:", [(u,cx,cy) for (u,cx,cy,wk,hk) in cand if not buildable(rect(cx,cy,wk,hk))])
facilities=[{"type":"airport","x":12000,"y":8000},{"type":"power","x":97000,"y":72000}]
transit=[{"type":"subway","path":[[12000,57000],[54000,57000],[84000,52000]]},
         {"type":"subway","path":[[54000,55000],[54000,70000]]},
         {"type":"highway","path":[[2000,66000],[98000,66000]]}]
for x in range(4000,97000,4000): transit.append({"type":"arterial","path":[[x,4000],[x,72000]]})
for y in range(4000,73000,4000): transit.append({"type":"arterial","path":[[4000,y],[96000,y]]})
stations=[{"x":x,"y":57000,"type":"subway"} for x in (16000,30000,54000,68000,82000)]
hubs=[{"x":54000,"y":57000},{"x":84000,"y":52000}]
sub={"zones":zones,"facilities":facilities,"transit":transit,"stations":stations,"hubs":hubs}
json.dump(sub,open("submission_lakecore3.json","w"))
import score_v2 as S
r=S.run(t,sub)
print(r["status"], r.get("score"), r.get("grade"), "event", r.get("event_score"))
if r["status"]!="OK": print(r["reasons"])
else:
    for e in r["events"]: print("  ",e["type"],e["net"])
