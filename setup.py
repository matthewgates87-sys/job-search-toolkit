#!/usr/bin/env python3
"""
setup.py — first-time setup. Run this ONCE before using the tools.

It:
  1. Checks your resume file exists.
  2. Reads it and auto-fills the "what to score jobs against" keywords.
  3. Creates your personal config.json from the template.
  4. Detects the job/experience sections in your resume (so the resume
     tailor knows where bullets can go).

RUN (Windows PowerShell):   python setup.py
Then follow the prompts. You can re-run it any time to refresh.
"""
import json, os, sys

TEMPLATE="config.template.json"
CONFIG="config.json"

def main():
    print("\n=== Job Search Toolkit — Setup ===\n")

    # 1. load or start config
    if os.path.exists(CONFIG):
        cfg=json.load(open(CONFIG))
        print(f"Found existing {CONFIG} — updating it.")
    elif os.path.exists(TEMPLATE):
        cfg=json.load(open(TEMPLATE))
        print(f"Creating {CONFIG} from template.")
    else:
        print(f"ERROR: {TEMPLATE} not found. Keep all toolkit files in one folder.")
        sys.exit(1)

    # 2. resume file
    resume=cfg.get("resume_file","master.docx")
    if not os.path.exists(resume):
        print(f"\n⚠ Resume file '{resume}' not found in this folder.")
        entered=input("  Type your resume's exact filename (e.g. My_Resume.docx): ").strip()
        if entered: resume=entered; cfg["resume_file"]=resume
    if not os.path.exists(resume):
        print(f"  Still can't find '{resume}'. Add it to this folder and re-run setup.")
        sys.exit(1)
    print(f"✓ Resume: {resume}")

    # 3. name
    if cfg.get("name","Your Name")=="Your Name":
        nm=input("\nYour name (for tailored resume filenames): ").strip()
        if nm: cfg["name"]=nm

    # 4. auto-extract resume keywords for scoring
    try:
        import resume_engine as eng
        text=eng.extract_text(resume)
        cfg.setdefault("resume_keywords",{})["text"]=text[:6000]
        print(f"✓ Read resume text for scoring ({len(text)} chars).")
        roles=eng.detect_roles(resume)
        if roles:
            print(f"✓ Detected {len(roles)} experience sections the tailor can add bullets under:")
            for r in roles: print(f"    - {r['label']}")
        else:
            print("⚠ Couldn't auto-detect experience sections. The resume tailor will")
            print("  still run but may need the anchors set manually. This can happen")
            print("  with unusual resume layouts.")
    except Exception as e:
        print(f"⚠ Could not fully read resume: {e}")

    # 5. quick preferences (optional, press Enter to skip)
    print("\nResume variants (for fast applying at volume):")
    print("  You can use up to 3 reusable resumes. If you only have one, just press")
    print("  Enter for each and it'll use your master for all of them.")
    cfg.setdefault("resume_variants",{})
    for label in ["Account Executive","Solutions Consultant / SE","Director / Leadership"]:
        cur=cfg["resume_variants"].get(label,resume)
        ans=input(f"  Resume file for '{label}' [{cur}]: ").strip()
        cfg["resume_variants"][label]=ans if ans else cur

    print("\nOptional preferences (press Enter to keep defaults):")
    roles_in=input("  Job title words you want (comma-separated) [keep current]: ").strip()
    if roles_in:
        cfg["target_roles"]["include"]=[x.strip().lower() for x in roles_in.split(",") if x.strip()]
    locs_in=input("  Preferred locations (comma-separated, blank = anywhere): ").strip()
    if locs_in:
        cfg["locations"]["preferred"]=[x.strip() for x in locs_in.split(",") if x.strip()]

    json.dump(cfg,open(CONFIG,"w"),indent=2)
    print(f"\n✓ Saved {CONFIG}. You're ready.")
    print("  Next: run  python job_hub.py   to find and track jobs.")
    print("        run  python resume_tailor.py   to format tailored resumes.\n")

if __name__=="__main__":
    main()
