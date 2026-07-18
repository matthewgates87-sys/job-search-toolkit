#!/usr/bin/env python3
"""
import_verdicts.py — read Claude's triage replies and mark your roles.

Paste all of Claude's verdict replies into  verdicts.txt  (append each batch).
Expected lines look like:

    a1b2c3d4 | APPLY | Strong AE fit, LA hybrid, ROI-led sale
    e5f6a7b8 | SKIP  | Requires 5yrs healthcare IT you don't have
    99aa11bb | MAYBE | Vague JD, possible ghost posting

RUN:  python import_verdicts.py
Then in Job Hub use the "Reviewed" dropdown to see only APPLY / MAYBE.
"""
import json, os, re, sys

CACHE="found_roles.json"
VERDICTS="verdicts.txt"

def role_id(r):
    base=f"{r.get('co','')}|{r.get('title','')}|{r.get('loc','')}"
    h=0
    for ch in base: h=(h*31+ord(ch)) & 0xFFFFFFFF
    return f"{h:08x}"

LINE=re.compile(r'^\s*([0-9a-f]{8})\s*[|:\-]\s*(APPLY|MAYBE|SKIP)\s*[|:\-]?\s*(.*)$', re.I)

def main():
    if not os.path.exists(CACHE):
        print(f"No {CACHE}. Run job_hub.py and Refresh first."); sys.exit(1)
    if not os.path.exists(VERDICTS):
        print(f"No {VERDICTS} found.\n")
        print("  Create it: paste Claude's verdict replies into a file named")
        print("  verdicts.txt in this folder, then re-run this.\n")
        sys.exit(1)

    d=json.load(open(CACHE,encoding="utf-8"))
    roles=d.get("roles",[])
    by_id={role_id(r):r for r in roles}

    found=0; unmatched=0
    counts={"APPLY":0,"MAYBE":0,"SKIP":0}
    for line in open(VERDICTS,encoding="utf-8"):
        m=LINE.match(line.strip())
        if not m: continue
        rid,verdict,why=m.group(1).lower(),m.group(2).upper(),m.group(3).strip()
        r=by_id.get(rid)
        if not r: unmatched+=1; continue
        r["verdict"]=verdict
        r["verdict_why"]=why[:200]
        counts[verdict]+=1; found+=1

    if not found:
        print("  No verdict lines recognized.")
        print("  Expected format:  a1b2c3d4 | APPLY | short reason\n")
        sys.exit(1)

    d["roles"]=roles
    json.dump(d,open(CACHE,"w",encoding="utf-8"))
    print(f"\n  Marked {found} roles:")
    for k,v in counts.items(): print(f"    {k:6} {v}")
    if unmatched: print(f"  ({unmatched} IDs didn't match — from an older pull?)")
    reviewed=sum(1 for r in roles if r.get("verdict"))
    print(f"\n  {reviewed} of {len(roles)} roles now reviewed.")
    print("  Restart job_hub.py and use the 'Reviewed' filter.\n")

if __name__=="__main__":
    main()
