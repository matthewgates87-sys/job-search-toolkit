#!/usr/bin/env python3
"""
expand_companies.py — grow your company list with VERIFIED slugs.

Two ways it helps:
  1. VERIFY: tests every company slug already in config.json and reports which
     ones actually work (so you can prune the dead 404s).
  2. DISCOVER: given a list of candidate company slugs (from you or a file),
     it tests each and adds the working ones to config.json.

This does NOT scrape private data — it only checks whether each company's PUBLIC
job board responds, the same public endpoints the job hub already uses.

RUN (PowerShell):
    python expand_companies.py                 # verify current config slugs
    python expand_companies.py candidates.txt   # test slugs from a file, add working ones

candidates.txt format: one entry per line as  ats,slug   e.g.
    greenhouse,stripe
    lever,brex
    ashby,notion
(If you omit the ats, it tries all three.)
"""
import json, os, ssl, sys, urllib.request, urllib.error, time

CONFIG="config.json"
CTX=ssl.create_default_context(); CTX.check_hostname=False; CTX.verify_mode=ssl.CERT_NONE
UA={'User-Agent':'Mozilla/5.0 (company slug verifier)'}

ENDPOINTS={
 "greenhouse": lambda s: f"https://boards-api.greenhouse.io/v1/boards/{s}/jobs",
 "lever":      lambda s: f"https://api.lever.co/v0/postings/{s}?mode=json&limit=1",
 "ashby":      lambda s: f"https://api.ashbyhq.com/posting-api/job-board/{s}",
}

def test_slug(ats, slug):
    """Return job count if the board is live, else None."""
    try:
        req=urllib.request.Request(ENDPOINTS[ats](slug),headers=UA)
        with urllib.request.urlopen(req,timeout=15,context=CTX) as r:
            d=json.loads(r.read().decode('utf-8','replace'))
        if ats=="greenhouse": return len(d.get("jobs",[]))
        if ats=="lever":      return len(d) if isinstance(d,list) else 0
        if ats=="ashby":      return len(d.get("jobs",[]))
    except Exception:
        return None

def verify_current():
    cfg=json.load(open(CONFIG))
    comp=cfg.get("companies",{})
    print("\nVerifying current company slugs...\n")
    kept={"greenhouse":[],"lever":[],"ashby":[]}
    dead=[]
    for ats in ["greenhouse","lever","ashby"]:
        for slug in comp.get(ats,[]):
            n=test_slug(ats,slug)
            if n is None:
                dead.append(f"{ats}/{slug}"); print(f"  DEAD  {ats}/{slug}")
            else:
                kept[ats].append(slug); print(f"  OK    {ats}/{slug}  ({n} jobs)")
            time.sleep(0.05)
    print(f"\n  {sum(len(v) for v in kept.values())} live, {len(dead)} dead.")
    if dead:
        ans=input("  Remove the dead ones from config.json? (y/N): ").strip().lower()
        if ans=="y":
            for k in kept: comp[k]=kept[k]
            cfg["companies"]=comp; cfg["companies"].setdefault("_comment","")
            json.dump(cfg,open(CONFIG,"w"),indent=2)
            print("  Pruned. config.json updated.")

def discover(path):
    cfg=json.load(open(CONFIG))
    comp=cfg.get("companies",{})
    for k in ["greenhouse","lever","ashby"]: comp.setdefault(k,[])
    existing={k:set(comp[k]) for k in comp if isinstance(comp[k],list)}
    added=0
    print(f"\nTesting candidate slugs from {path}...\n")
    for line in open(path):
        line=line.strip()
        if not line or line.startswith("#"): continue
        if "," in line: ats,slug=[x.strip() for x in line.split(",",1)]; tries=[ats]
        else: slug=line; tries=["greenhouse","lever","ashby"]
        for ats in tries:
            if ats not in ENDPOINTS: continue
            if slug in existing.get(ats,set()): break
            n=test_slug(ats,slug)
            if n is not None and n>0:
                comp[ats].append(slug); existing[ats].add(slug); added+=1
                print(f"  ADDED {ats}/{slug}  ({n} jobs)"); break
            elif n is not None:
                print(f"  empty {ats}/{slug}")
            time.sleep(0.05)
    if added:
        cfg["companies"]=comp
        json.dump(cfg,open(CONFIG,"w"),indent=2)
        print(f"\n  Added {added} working companies to config.json.")
    else:
        print("\n  No new working companies found.")

if __name__=="__main__":
    if not os.path.exists(CONFIG):
        print("No config.json — run setup.py first."); sys.exit(1)
    if len(sys.argv)>1 and os.path.exists(sys.argv[1]):
        discover(sys.argv[1])
    else:
        verify_current()
