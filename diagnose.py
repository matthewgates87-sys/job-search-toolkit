#!/usr/bin/env python3
"""
diagnose.py — checks WHY the job search returns results (or doesn't).
Tests each company board one by one and reports exactly what it finds.

RUN (PowerShell):  python diagnose.py
"""
import json, os, ssl, urllib.request, urllib.error, re

CONFIG="config.json"
CTX=ssl.create_default_context(); CTX.check_hostname=False; CTX.verify_mode=ssl.CERT_NONE
UA={'User-Agent':'Mozilla/5.0 (job search diagnostic)'}

def fetch(url):
    req=urllib.request.Request(url,headers=UA)
    with urllib.request.urlopen(req,timeout=20,context=CTX) as r:
        return r.read().decode('utf-8','replace')


def test_apis(cfg):
    print("\n3) Testing job APIs (the big volume sources):\n")
    import urllib.parse
    any_on = False

    # --- Adzuna ---
    az = cfg.get("adzuna", {})
    if (az.get("app_id") or "").strip() and (az.get("app_key") or "").strip():
        any_on = True
        try:
            p = {"app_id": az["app_id"], "app_key": az["app_key"], "results_per_page": 10,
                 "what_or": "sales", "where": str(az.get("zip", "")), "distance": az.get("distance_miles", 50),
                 "content-type": "application/json"}
            d = json.loads(fetch("https://api.adzuna.com/v1/api/jobs/us/search/1?" + urllib.parse.urlencode(p)))
            print(f"   Adzuna       OK - {d.get('count','?')} total jobs near {az.get('zip')}")
        except urllib.error.HTTPError as e:
            print(f"   Adzuna       X HTTP {e.code} - check app_id/app_key")
        except Exception as e:
            print(f"   Adzuna       X {type(e).__name__}")
    else:
        print("   Adzuna       - not configured (free key: developer.adzuna.com)")

    # --- USAJobs ---
    uj = cfg.get("usajobs", {})
    if (uj.get("api_key") or "").strip() and (uj.get("user_agent") or "").strip():
        any_on = True
        try:
            hdrs = {"Host": "data.usajobs.gov", "User-Agent": uj["user_agent"],
                    "Authorization-Key": uj["api_key"]}
            url = "https://data.usajobs.gov/api/search?" + urllib.parse.urlencode(
                {"Keyword": "sales", "ResultsPerPage": "5"})
            req = urllib.request.Request(url, headers=hdrs)
            with urllib.request.urlopen(req, timeout=20, context=CTX) as r:
                d = json.loads(r.read().decode("utf-8", "replace"))
            n = d.get("SearchResult", {}).get("SearchResultCount", "?")
            print(f"   USAJobs      OK - {n} federal sales jobs found")
        except urllib.error.HTTPError as e:
            print(f"   USAJobs      X HTTP {e.code} - check api_key + user_agent (must be your reg. email)")
        except Exception as e:
            print(f"   USAJobs      X {type(e).__name__}")
    else:
        print("   USAJobs      - not configured (free key: developer.usajobs.gov)")

    # --- Jooble ---
    jb = cfg.get("jooble", {})
    if (jb.get("api_key") or "").strip():
        any_on = True
        try:
            payload = json.dumps({"keywords": "sales", "location": jb.get("location", "")}).encode()
            req = urllib.request.Request(f"https://jooble.org/api/{jb['api_key']}", data=payload,
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=20, context=CTX) as r:
                d = json.loads(r.read().decode("utf-8", "replace"))
            print(f"   Jooble       OK - {d.get('totalCount','?')} jobs found")
        except urllib.error.HTTPError as e:
            print(f"   Jooble       X HTTP {e.code} - check api_key")
        except Exception as e:
            print(f"   Jooble       X {type(e).__name__}")
    else:
        print("   Jooble       - not configured (free key: jooble.org/api/about)")

    # --- JSearch ---
    js = cfg.get("jsearch", {})
    if (js.get("api_key") or "").strip():
        any_on = True
        try:
            hdrs = {"X-RapidAPI-Key": js["api_key"], "X-RapidAPI-Host": "jsearch.p.rapidapi.com"}
            url = "https://jsearch.p.rapidapi.com/search?" + urllib.parse.urlencode(
                {"query": "sales in " + js.get("location", "Los Angeles"), "page": "1", "num_pages": "1"})
            req = urllib.request.Request(url, headers=hdrs)
            with urllib.request.urlopen(req, timeout=25, context=CTX) as r:
                d = json.loads(r.read().decode("utf-8", "replace"))
            print(f"   JSearch      OK - {len(d.get('data', []))} jobs on page 1 (Google Jobs)")
        except urllib.error.HTTPError as e:
            print(f"   JSearch      X HTTP {e.code} - check RapidAPI key / subscription")
        except Exception as e:
            print(f"   JSearch      X {type(e).__name__}")
    else:
        print("   JSearch      - not configured (rapidapi.com -> JSearch by OpenWeb Ninja)")

    if not any_on:
        print("\n   !! NO APIs CONFIGURED. This is where the volume comes from -")
        print("      company boards alone are a small slice of the market.")
        print("      Add keys to config.json, then re-run this.")
    return any_on

def main():
    print("\n=== Job Search Diagnostic ===\n")
    if not os.path.exists(CONFIG):
        print("X No config.json found. Run  python setup.py  first.\n"); return
    cfg=json.load(open(CONFIG))
    comp=cfg.get("companies",{})
    gh=comp.get("greenhouse",[]); lv=comp.get("lever",[]); ash=comp.get("ashby",[])
    inc=cfg.get("target_roles",{}).get("include",[])
    print(f"Config loaded. Companies: {len(gh)} Greenhouse, {len(lv)} Lever, {len(ash)} Ashby")
    print(f"Role filter includes: {', '.join(inc[:6])}{'…' if len(inc)>6 else ''}\n")

    # 1) internet reachability
    print("1) Testing internet access to a job board...")
    try:
        fetch("https://boards-api.greenhouse.io/v1/boards/anthropic/jobs")
        print("   OK - can reach Greenhouse.\n")
    except urllib.error.HTTPError as e:
        print(f"   Reached server, got HTTP {e.code} (that's fine for this test).\n")
    except Exception as e:
        print(f"   X CANNOT reach job boards: {type(e).__name__}: {e}")
        print("     -> This is a network/firewall/proxy issue on your computer or")
        print("        company network. The tool can't pull jobs without board access.\n")
        return

    # 2) per-company check
    total_titles=0; total_matches=0; reachable=0
    SALES=re.compile('|'.join(re.escape(w) for w in inc),re.I) if inc else re.compile('sales',re.I)

    def check(url, extract):
        nonlocal reachable,total_titles,total_matches
        try:
            data=fetch(url); titles=extract(data)
            reachable+=1; total_titles+=len(titles)
            m=[t for t in titles if SALES.search(t)]; total_matches+=len(m)
            return len(titles),len(m)
        except urllib.error.HTTPError as e:
            return f"HTTP {e.code}",0
        except Exception as e:
            return type(e).__name__,0

    print("2) Checking each company board (total roles / matching your filter):\n")
    for tok in gh:
        n,m=check(f"https://boards-api.greenhouse.io/v1/boards/{tok}/jobs",
                  lambda d:[j.get("title","") for j in json.loads(d).get("jobs",[])])
        print(f"   Greenhouse/{tok:22} {n if isinstance(n,str) else str(n)+' roles':>12}  {m if not isinstance(n,str) else ''} match")
    for tok in lv:
        n,m=check(f"https://api.lever.co/v0/postings/{tok}?mode=json",
                  lambda d:[j.get("text","") for j in json.loads(d)])
        print(f"   Lever/{tok:27} {n if isinstance(n,str) else str(n)+' roles':>12}  {m if not isinstance(n,str) else ''} match")
    for tok in ash:
        n,m=check(f"https://api.ashbyhq.com/posting-api/job-board/{tok}",
                  lambda d:[j.get("title","") for j in json.loads(d).get("jobs",[])])
        print(f"   Ashby/{tok:27} {n if isinstance(n,str) else str(n)+' roles':>12}  {m if not isinstance(n,str) else ''} match")

    test_apis(cfg)

    print(f"\n=== Summary ===")
    print(f"  Boards reachable: {reachable} of {len(gh)+len(lv)+len(ash)}")
    print(f"  Total roles seen: {total_titles}")
    print(f"  Matching your role filter: {total_matches}")
    if total_matches==0:
        print("\n  No matches. Likely causes:")
        if reachable==0:
            print("   - No boards reachable -> network/proxy blocking the connections.")
        elif total_titles==0:
            print("   - Boards reachable but returned 0 roles -> company slugs may be wrong")
            print("     (the slug is the word in their careers URL, e.g. boards.greenhouse.io/THIS).")
        else:
            print("   - Boards have roles, but none match your filter words.")
            print("     -> Widen 'target_roles.include' in config.json (add terms like your")
            print("        target titles), or the companies may not have sales roles open.")
    else:
        print(f"\n  Looks healthy - Job Hub should show ~{total_matches} roles after Refresh.")
    print()

if __name__=="__main__":
    main()
