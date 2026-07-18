#!/usr/bin/env python3
"""
export_jds.py — dump your found roles into batch files you paste into Claude.

WHY: Job Hub's fit % is keyword overlap, not judgment. It says 100% on roles
that are actually a poor fit. This lets Claude read the real descriptions and
tell you which are worth your time.

FLOW:
  1. python export_jds.py            -> creates review_batch_1.txt, _2.txt, ...
  2. Paste one batch into your "Job Triage" Claude Project.
  3. Claude returns a verdict list. Save its reply into verdicts.txt
     (append each batch's reply to the same file).
  4. python import_verdicts.py       -> marks the good ones in Job Hub.
  5. In Job Hub, use the "Reviewed" filter to see only APPLY/MAYBE roles.

RUN:  python export_jds.py [--min-fit 50] [--per-batch 25]
"""
import json, os, sys, re

CACHE="found_roles.json"
OUT_PREFIX="review_batch_"

def load_roles():
    if not os.path.exists(CACHE):
        print(f"No {CACHE} found. Run job_hub.py and Refresh first."); sys.exit(1)
    d=json.load(open(CACHE,encoding="utf-8"))
    return d.get("roles",[])

def role_id(r):
    """Stable short id so verdicts can be matched back."""
    base=f"{r.get('co','')}|{r.get('title','')}|{r.get('loc','')}"
    h=0
    for ch in base: h=(h*31+ord(ch)) & 0xFFFFFFFF
    return f"{h:08x}"

def main():
    args=sys.argv[1:]
    min_fit=0; per_batch=25
    if "--min-fit" in args: min_fit=int(args[args.index("--min-fit")+1])
    if "--per-batch" in args: per_batch=int(args[args.index("--per-batch")+1])

    roles=load_roles()
    roles=[r for r in roles if (r.get("fit") or 0)>=min_fit]
    # skip ones with no usable description
    usable=[r for r in roles if len((r.get("desc") or ""))>200]
    thin=len(roles)-len(usable)

    if not usable:
        print("No roles with usable descriptions. Re-run a Refresh in job_hub")
        print("(older caches didn't store descriptions).")
        sys.exit(0)

    print(f"\n  {len(usable)} roles to review"
          + (f"  ({thin} skipped — description too thin)" if thin else ""))
    print(f"  Writing batches of {per_batch}...\n")

    # clear old batches
    for f in os.listdir("."):
        if f.startswith(OUT_PREFIX) and f.endswith(".txt"): os.remove(f)

    n=0
    for i in range(0, len(usable), per_batch):
        n+=1
        chunk=usable[i:i+per_batch]
        lines=[f"BATCH {n} — {len(chunk)} roles. Give a verdict for each ID.\n"]
        for r in chunk:
            rid=role_id(r)
            desc=(r.get("desc") or "").strip()
            lines.append("="*60)
            lines.append(f"ID: {rid}")
            lines.append(f"COMPANY: {r.get('co','')}")
            lines.append(f"TITLE: {r.get('title','')}")
            lines.append(f"LOCATION: {r.get('loc','')}  |  TYPE: {r.get('wt','')}")
            lines.append(f"DESCRIPTION: {desc}")
            lines.append("")
        fn=f"{OUT_PREFIX}{n}.txt"
        open(fn,"w",encoding="utf-8").write("\n".join(lines))
        print(f"    {fn}  ({len(chunk)} roles)")

    print(f"\n  Done — {n} batch file(s).")
    print("  Paste each into your Job Triage Claude Project, save the replies")
    print("  into verdicts.txt, then run:  python import_verdicts.py\n")

if __name__=="__main__":
    main()
