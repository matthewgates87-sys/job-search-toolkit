#!/usr/bin/env python3
"""
job_hub.py  —  Find + Track, in one app  (Matthew Gates)
--------------------------------------------------------
Merges the job finder and the application tracker into a single tool with
two tabs that share one pipeline:

  FIND    - pulls live sales roles from public boards (Greenhouse, Lever,
            Ashby), scores each against your resume, filters by role /
            location / work-type / fit. One click adds a role to your
            pipeline (with the tailored-resume filename auto-generated).

  PIPELINE- your application tracker: stages (To apply -> Applied -> Screen
            -> Interview -> Offer / Rejected), follow-up reminders, notes,
            the auto-named resume file per application.

One data file:  applications.json  (saved locally, survives restarts).

RUN (Windows PowerShell):   python job_hub.py
Browser opens automatically. To stop: Ctrl+C.
First launch does a live pull (a few minutes). Use "Refresh roles" anytime.
Nothing is uploaded; everything runs on your computer.
"""

import http.server, socketserver, json, os, re, ssl, urllib.request, urllib.error
import datetime, webbrowser, threading, time

PORT = 8756
DATA = "applications.json"
CACHE = "found_roles.json"
CONFIG = "config.json"

STAGES = ["To apply","Applied","Screen","Interview","Offer","Rejected"]

# ---------- load everything from config.json ----------
def load_config():
    if not os.path.exists(CONFIG): return None
    return json.load(open(CONFIG,encoding="utf-8"))

_cfg = load_config() or {}
_companies = _cfg.get("companies",{})
GREENHOUSE = _companies.get("greenhouse",[])
LEVER      = _companies.get("lever",[])
ASHBY      = _companies.get("ashby",[])

_include = _cfg.get("target_roles",{}).get("include",
           ["account executive","sales","solutions consultant","solutions engineer","business development"])
_exclude = _cfg.get("target_roles",{}).get("exclude",
           ["software engineer","data scientist","recruiter","designer"])

def _mk_pattern(words):
    parts=[re.escape(w).replace(r'\ ',r'[\s-]+') for w in words]
    return re.compile(r'\b('+'|'.join(parts)+r')\b', re.I) if parts else re.compile(r'$^')

SALES = _mk_pattern(_include)
DROP  = _mk_pattern(_exclude)

RESUME = _cfg.get("resume_keywords",{}).get("text","") or """
sales account executive solutions consultant business development revenue quota
enterprise saas consultative discovery closing negotiation pipeline forecasting
"""
KEYWORDS = [
 ("Consultative selling",["consultative","solution selling","value selling","value-based"]),
 ("Discovery",["discovery","needs analysis","qualification"]),
 ("ROI / business case",["roi","business case","payback","tco","cost-benefit","value realization"]),
 ("Enterprise",["enterprise","large accounts","strategic accounts","field sales"]),
 ("Mid-market",["mid-market","midmarket","smb","commercial segment"]),
 ("SaaS",["saas","cloud software","subscription"]),
 ("AI / ML",["ai","artificial intelligence","machine learning","genai","generative","llm"]),
 ("Automation / workflow",["automation","workflow","process","rpa","orchestration"]),
 ("Salesforce / CRM",["salesforce","crm","hubspot","pipeline"]),
 ("Quota / new business",["quota","new business","net-new","hunter","revenue","bookings"]),
 ("Account expansion",["expansion","upsell","cross-sell","land and expand","renewal"]),
 ("C-level",["c-level","c-suite","executive","vp","cxo","decision-makers"]),
 ("Closing / negotiation",["sales cycle","closing","close","negotiation","deal"]),
 ("Forecasting",["forecast","forecasting","pipeline hygiene"]),
 ("Demos / pre-sales",["demo","demonstration","pre-sales","presales","poc","proof of concept"]),
 ("Solution architecture",["solution architecture","solution design","technical solution","integration"]),
 ("Team leadership",["team leadership","player-coach","coaching","enablement","mentor","manager"]),
 ("GTM / territory",["territory","go-to-market","gtm","prospecting","outbound"]),
 ("Methodology",["meddic","meddpicc","challenger","sandler","force management"]),
]
CTX=ssl.create_default_context(); CTX.check_hostname=False; CTX.verify_mode=ssl.CERT_NONE
UA={'User-Agent':'Mozilla/5.0 (personal job search)'}
def fetch(url):
    req=urllib.request.Request(url,headers=UA)
    with urllib.request.urlopen(req,timeout=25,context=CTX) as r: return r.read().decode('utf-8','replace')
def keep(t): return bool(SALES.search(t)) and not DROP.search(t)
def norm(s): return (' '+s.lower()+' ').replace('\xa0',' ')
def hasterm(hay,t): t=t.lower(); return (' '+t+' ') in hay or (' '+t) in hay or (t+' ') in hay
RES_N=norm(re.sub(r'\s+',' ',RESUME))
def score_text(text):
    jd=norm(re.sub(r'<[^>]+>',' ',text)); jd=re.sub(r'\s+',' ',jd)
    rel=[];hits=[]
    for label,terms in KEYWORDS:
        if any(hasterm(jd,t) for t in terms):
            rel.append(label)
            if any(hasterm(RES_N,t) for t in terms): hits.append(label)
    return (round(100*len(hits)/len(rel)) if rel else 0), [l for l in rel if l not in hits][:6]
HYB=re.compile(r'\bhybrid\b',re.I);REM=re.compile(r'\bremote\b',re.I);ONS=re.compile(r'\b(on[- ]?site|in[- ]office|in person)\b',re.I)

# ---------- location relevance filter (applied at pull time) ----------
# Cities near the user's zip, grouped by approx distance band.
LA_CITY_BANDS={
10:["montrose","la crescenta","glendale","la canada","la cañada","flintridge","tujunga",
    "sunland","altadena","eagle rock","highland park","verdugo city","sun valley"],
15:["pasadena","south pasadena","burbank","north hollywood","atwater village","silver lake",
    "los feliz","san marino","sierra madre","toluca lake","studio city","universal city",
    "glassell park","mount washington","alhambra","monterey park","echo park"],
20:["los angeles","downtown la","hollywood","west hollywood","sherman oaks","van nuys",
    "arcadia","monrovia","temple city","rosemead","el monte","el sereno","boyle heights",
    "commerce","vernon","valley village","north hills","panorama city","encino","san fernando",
    "sylmar","mission hills","granada hills","duarte","irwindale","baldwin park"],
25:["beverly hills","century city","westwood","culver city","santa monica","brentwood",
    "tarzana","reseda","northridge","chatsworth","canoga park","woodland hills","winnetka",
    "west covina","covina","azusa","glendora","montebello","pico rivera","whittier",
    "downey","bell","bell gardens","huntington park","maywood","santa clarita","valencia",
    "newhall","saugus","marina del rey","playa vista","playa del rey","mar vista","venice"],
30:["inglewood","hawthorne","el segundo","manhattan beach","hermosa beach","gardena",
    "compton","norwalk","cerritos","la mirada","santa fe springs","city of industry",
    "walnut","diamond bar","rowland heights","hacienda heights","la puente","pomona","claremont",
    "san dimas","calabasas","agoura hills","malibu","topanga"],
35:["torrance","redondo beach","carson","lakewood","bellflower","paramount","artesia",
    "buena park","la habra","brea","fullerton","placentia","yorba linda","chino","chino hills",
    "ontario","upland","rancho cucamonga","montclair","thousand oaks","westlake village",
    "simi valley","moorpark"],
40:["long beach","san pedro","wilmington","harbor city","lomita","seal beach","los alamitos",
    "cypress","stanton","anaheim","orange","villa park","garden grove","fontana","rialto",
    "colton","camarillo","newbury park","port hueneme"],
45:["huntington beach","westminster","fountain valley","santa ana","tustin","costa mesa",
    "san bernardino","redlands","loma linda","oxnard","ventura","corona","norco"],
50:["irvine","newport beach","lake forest","mission viejo","laguna beach","laguna hills",
    "aliso viejo","riverside","moreno valley","perris","temecula","murrieta","palmdale",
    "lancaster","santa paula","fillmore","hesperia","victorville"],
}
NON_US_RE=re.compile(r'canada|\bcan\b|toronto|montr|quebec|british columbia|calgary|vancouver|'
    r'alberta|united kingdom|\buk\b|england|london|dublin|ireland|europe|emea|apac|\bindia\b|'
    r'australia|sydney|melbourne|germany|munich|berlin|france|paris|netherlands|amsterdam|'
    r'singapore|japan|tokyo|korea|seoul|brazil|mexico|china|hong kong|israel|tel aviv|'
    r'spain|madrid|italy|sweden|poland|denmark|norway|finland|switzerland|zurich|dubai|uae',re.I)

def _cities_within(miles):
    out=[]
    for band,lst in LA_CITY_BANDS.items():
        if int(band)<=miles: out+=lst
    return out

def is_local(loc, miles):
    if not loc: return False
    L=loc.lower()
    if NON_US_RE.search(L): return False
    return any(c in L for c in _cities_within(miles))

def is_remote_us(loc, wt):
    L=(loc or '').lower()
    remote = (wt=='Remote') or bool(re.search(r'\bremote\b|work from home|wfh|anywhere',L))
    if not remote: return False
    if NON_US_RE.search(L): return False
    m=re.search(r'remote\s*[-–—:]\s*([a-z .]+)',L)
    if m:
        scope=m.group(1).strip()
        if not re.match(r'^(us|u\.s\.|usa|united states|america|north america|nationwide|anywhere)\b',scope):
            return False
    return True

def location_relevant(loc, wt):
    """Keep only roles that are local (within radius) OR remote-US, per config."""
    f=_cfg.get("location_filter",{})
    if not f.get("enabled",True): return True
    miles=int(f.get("max_miles",50) or 50)
    keep_local=f.get("keep_local",True)
    keep_remote=f.get("keep_remote_us",True)
    if keep_local and is_local(loc,miles): return True
    if keep_remote and is_remote_us(loc,wt): return True
    return False

def worktype(loc,body):
    b=f"{loc} {body}"
    if HYB.search(b): return "Hybrid"
    if REM.search(b): return "Remote"
    if ONS.search(b): return "On-site"
    return "—"

def gh(tok):
    d=json.loads(fetch(f"https://boards-api.greenhouse.io/v1/boards/{tok}/jobs")); out=[]
    for j in d.get("jobs",[]):
        t=j.get("title","")
        if keep(t): out.append((t,(j.get("location") or {}).get("name","—"),j.get("absolute_url",""),
                                f"https://boards-api.greenhouse.io/v1/boards/{tok}/jobs/{j.get('id')}","Greenhouse"))
    return out
def lever(tok):
    d=json.loads(fetch(f"https://api.lever.co/v0/postings/{tok}?mode=json")); out=[]
    for j in d:
        t=j.get("text","")
        if keep(t):
            parts=[j.get("descriptionPlain","")]+[l.get("text","")+" "+str(l.get("content","")) for l in j.get("lists",[])]
            out.append((t,(j.get("categories") or {}).get("location","—"),j.get("hostedUrl",""),"BODY:"+" ".join(parts),"Lever"))
    return out
def ashby(tok):
    d=json.loads(fetch(f"https://api.ashbyhq.com/posting-api/job-board/{tok}")); out=[]
    for j in d.get("jobs",[]):
        t=j.get("title","")
        if keep(t):
            body=j.get("descriptionPlain","") or j.get("description","")
            out.append((t,j.get("location") or j.get("locationName","—"),j.get("jobUrl") or j.get("applyUrl",""),"BODY:"+body,"Ashby"))
    return out
def detail(ref):
    if ref.startswith("BODY:"): return ref[5:]
    try: return json.loads(fetch(ref)).get("content","")
    except Exception: return ""

def adzuna_search(progress=None):
    """Search the whole market via Adzuna by location+radius and (optionally) remote.
    Returns list of (co,title,loc,url,ref,src) tuples like the board fns."""
    az=_cfg.get("adzuna",{})
    app_id=(az.get("app_id","") or "").strip()
    app_key=(az.get("app_key","") or "").strip()
    if not app_id or not app_key: return []
    zipc=str(az.get("zip","")).strip()
    dist=int(az.get("distance_miles",50) or 50)
    max_pages=int(az.get("max_pages",5) or 5)
    include=_cfg.get("target_roles",{}).get("include",["sales"])
    out=[]
    import urllib.parse
    def run(where, whatq, remote=False):
        for page in range(1,max_pages+1):
            params={"app_id":app_id,"app_key":app_key,"results_per_page":50,
                    "what_or":whatq,"content-type":"application/json"}
            if where: params["where"]=where; params["distance"]=dist
            if remote: params["what_phrase"]="remote"
            url="https://api.adzuna.com/v1/api/jobs/us/search/%d?%s"%(page,urllib.parse.urlencode(params))
            try:
                d=json.loads(fetch(url))
            except Exception:
                break
            results=d.get("results",[])
            if not results: break
            for j in results:
                t=j.get("title","")
                if not keep(t): continue
                co=(j.get("company",{}) or {}).get("display_name","") or "—"
                loc=(j.get("location",{}) or {}).get("display_name","—")
                desc=j.get("description","")
                link=j.get("redirect_url","")
                out.append((co,t,loc,link,"BODY:"+desc,"Adzuna"))
            if len(results)<50: break
            time.sleep(0.1)
    whatq=" ".join(include[:5])
    if progress: progress(phase="boards",done=0,total=1,msg="Searching Adzuna (local + remote)…")
    # local by zip+radius
    if zipc: run(zipc, whatq, remote=False)
    # remote-US
    if az.get("also_remote",True): run("", whatq, remote=True)
    # dedupe within adzuna by (co,title,loc)
    seen=set(); uniq=[]
    for r in out:
        k=(r[0],r[1],r[2])
        if k not in seen: seen.add(k); uniq.append(r)
    return uniq


def _fetch_hdr(url, headers):
    req=urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=25, context=CTX) as r:
        return r.read().decode('utf-8','replace')

def usajobs_search(progress=None):
    """Federal jobs — real headcount, no phantom postings."""
    cfg=_cfg.get("usajobs",{})
    key=(cfg.get("api_key","") or "").strip()
    ua=(cfg.get("user_agent","") or "").strip()
    if not key or not ua: return []
    import urllib.parse
    include=_cfg.get("target_roles",{}).get("include",["sales"])
    loc=cfg.get("location","")
    rad=int(cfg.get("radius_miles",50) or 50)
    max_pages=int(cfg.get("max_pages",5) or 5)
    hdrs={"Host":"data.usajobs.gov","User-Agent":ua,"Authorization-Key":key}
    out=[]
    def run(kw, location=None, remote=False):
        for page in range(1,max_pages+1):
            p={"Keyword":kw,"ResultsPerPage":"500","Page":str(page)}
            if location: p["LocationName"]=location; p["Radius"]=str(rad)
            if remote: p["RemoteIndicator"]="True"
            url="https://data.usajobs.gov/api/search?"+urllib.parse.urlencode(p)
            try: d=json.loads(_fetch_hdr(url,hdrs))
            except Exception: break
            items=(d.get("SearchResult",{}) or {}).get("SearchResultItems",[])
            if not items: break
            for it in items:
                j=it.get("MatchedObjectDescriptor",{}) or {}
                t=j.get("PositionTitle","")
                if not keep(t): continue
                co=(j.get("OrganizationName","") or j.get("DepartmentName","") or "Federal")
                locs=j.get("PositionLocationDisplay","") or "—"
                url_j=j.get("PositionURI","")
                ui=j.get("UserArea",{}).get("Details",{}) if isinstance(j.get("UserArea"),dict) else {}
                desc=(j.get("QualificationSummary","") or "")+" "+str(ui.get("JobSummary",""))
                out.append((co,t,locs,url_j,"BODY:"+desc,"USAJobs"))
            if len(items)<500: break
            time.sleep(0.1)
    kw=" ".join(include[:3])
    if progress: progress(phase="boards",done=0,total=1,msg="Searching USAJobs (federal)…")
    if loc: run(kw, location=loc)
    if cfg.get("also_remote",True): run(kw, remote=True)
    seen=set(); uniq=[]
    for r in out:
        k=(r[0],r[1],r[2])
        if k not in seen: seen.add(k); uniq.append(r)
    return uniq

def jooble_search(progress=None):
    """Jooble aggregator — POST API."""
    cfg=_cfg.get("jooble",{})
    key=(cfg.get("api_key","") or "").strip()
    if not key: return []
    include=_cfg.get("target_roles",{}).get("include",["sales"])
    loc=cfg.get("location","")
    max_pages=int(cfg.get("max_pages",5) or 5)
    out=[]
    def run(kw, location):
        for page in range(1,max_pages+1):
            payload=json.dumps({"keywords":kw,"location":location,"page":str(page)}).encode()
            req=urllib.request.Request(f"https://jooble.org/api/{key}",data=payload,
                                       headers={"Content-Type":"application/json"})
            try:
                with urllib.request.urlopen(req,timeout=25,context=CTX) as r:
                    d=json.loads(r.read().decode('utf-8','replace'))
            except Exception: break
            jobs=d.get("jobs",[])
            if not jobs: break
            for j in jobs:
                t=j.get("title","")
                if not keep(t): continue
                out.append((j.get("company","") or "—", t, j.get("location","—"),
                            j.get("link",""), "BODY:"+(j.get("snippet","") or ""), "Jooble"))
            if len(jobs)<20: break
            time.sleep(0.1)
    kw=" ".join(include[:3])
    if progress: progress(phase="boards",done=0,total=1,msg="Searching Jooble…")
    if loc: run(kw, loc)
    if cfg.get("also_remote",True): run(kw, "Remote")
    seen=set(); uniq=[]
    for r in out:
        k=(r[0],r[1],r[2])
        if k not in seen: seen.add(k); uniq.append(r)
    return uniq

def jsearch_search(progress=None):
    """JSearch (RapidAPI) — taps Google Jobs, broadest single source."""
    cfg=_cfg.get("jsearch",{})
    key=(cfg.get("api_key","") or "").strip()
    if not key: return []
    import urllib.parse
    include=_cfg.get("target_roles",{}).get("include",["sales"])
    loc=cfg.get("location","")
    max_pages=int(cfg.get("max_pages",3) or 3)
    hdrs={"X-RapidAPI-Key":key,"X-RapidAPI-Host":"jsearch.p.rapidapi.com"}
    out=[]
    def run(q, remote=False):
        for page in range(1,max_pages+1):
            p={"query":q,"page":str(page),"num_pages":"1","country":"us"}
            if remote: p["remote_jobs_only"]="true"
            url="https://jsearch.p.rapidapi.com/search?"+urllib.parse.urlencode(p)
            try: d=json.loads(_fetch_hdr(url,hdrs))
            except Exception: break
            data=d.get("data",[])
            if not data: break
            for j in data:
                t=j.get("job_title","")
                if not keep(t): continue
                city=j.get("job_city") or ""; state=j.get("job_state") or ""
                loc_s=", ".join([x for x in [city,state] if x]) or ("Remote" if j.get("job_is_remote") else "—")
                out.append((j.get("employer_name","") or "—", t, loc_s,
                            j.get("job_apply_link","") or "", "BODY:"+(j.get("job_description","") or ""),
                            "JSearch"))
            time.sleep(0.2)
    kw=" ".join(include[:3])
    if progress: progress(phase="boards",done=0,total=1,msg="Searching JSearch (Google Jobs)…")
    if loc: run(f"{kw} in {loc}")
    if cfg.get("also_remote",True): run(f"{kw} remote", remote=True)
    seen=set(); uniq=[]
    for r in out:
        k=(r[0],r[1],r[2])
        if k not in seen: seen.add(k); uniq.append(r)
    return uniq

def pull_roles(progress=None):
    raw=[]; boards_ok=0; boards_empty=0; boards_fail=0
    allseeds=[(GREENHOUSE,gh,"Greenhouse"),(LEVER,lever,"Lever"),(ASHBY,ashby,"Ashby")]
    total_boards=sum(len(s) for s,_,_ in allseeds)
    done_boards=0
    if total_boards==0 and progress:
        progress(phase="boards",done=0,total=1,msg="No company boards listed — using APIs only.")
    for seeds,fn,srcname in allseeds:
        for tok in seeds:
            done_boards+=1
            if progress: progress(phase="boards",done=done_boards,total=total_boards,
                                   msg=f"Checking {srcname}: {tok}")
            try:
                got=list(fn(tok))
                if got: boards_ok+=1; raw+=[(tok,)+r for r in got]
                else: boards_empty+=1
            except Exception:
                boards_fail+=1
    # External APIs: search the WHOLE market, not just listed company boards
    api_counts={}
    for name,fn in [("Adzuna",adzuna_search),("USAJobs",usajobs_search),
                    ("Jooble",jooble_search),("JSearch",jsearch_search)]:
        try:
            rows=fn(progress)   # each returns (co,title,loc,url,ref,src)
            if rows:
                raw+=rows; api_counts[name]=len(rows)
        except Exception:
            pass
    az_count=sum(api_counts.values())
    if not raw:
        api_on=[k for k in ["adzuna","usajobs","jooble","jsearch"]
                if (_cfg.get(k,{}).get("api_key") or _cfg.get(k,{}).get("app_id"))]
        if progress: progress(phase="empty",
            msg=f"No matching roles found. Checked {total_boards} boards "
                f"({boards_fail} unreachable). APIs enabled: {', '.join(api_on) if api_on else 'NONE — add API keys in config.json for far more jobs'}.")
        json.dump({"roles":[],"pulled":datetime.datetime.now().isoformat()},open(CACHE,"w"))
        return []
    jobs=[]; skipped_loc=0
    N=len(raw)
    for n,(co,t,loc,url,ref,src) in enumerate(raw,1):
        if progress and (n%10==0 or n==N):
            progress(phase="scoring",done=n,total=N,msg=f"Scoring role {n} of {N}")
        body=detail(ref); fit,gaps=score_text(t+" "+body)
        wt_=worktype(loc,body)
        if not location_relevant(loc, wt_):
            skipped_loc+=1
            continue
        desc=re.sub(r'<[^>]+>',' ',body or '')
        desc=re.sub(r'\s+',' ',desc).strip()[:2500]
        jobs.append(dict(co=co,title=t,loc=loc or "—",url=url,src=src,fit=fit,wt=wt_,gaps=gaps,desc=desc))
        time.sleep(0.02)
    seen=set();uniq=[]
    for r in sorted(jobs,key=lambda x:-x["fit"]):
        k=(r["co"],r["title"],r["loc"])
        if k not in seen: seen.add(k);uniq.append(r)
    json.dump({"roles":uniq,"pulled":datetime.datetime.now().isoformat()},open(CACHE,"w"))
    if progress:
        parts=[f"{boards_ok} boards"]+[f"{k}: {v}" for k,v in api_counts.items()]
        if skipped_loc: parts.append(f"{skipped_loc} filtered out by location")
        progress(phase="done",done=len(uniq),total=len(uniq),
                 msg=f"Found {len(uniq)} roles ({', '.join(parts)}).")
    return uniq

# ---------- pipeline storage ----------
def load(): 
    try: return json.load(open(DATA,encoding="utf-8"))
    except Exception: return []
def save(rows): json.dump(rows,open(DATA,"w",encoding="utf-8"),indent=2)
def slug(s): return re.sub(r'-{2,}','-',re.sub(r'[^A-Za-z0-9]+','-',s or '').strip('-'))
def _lastname():
    nm=_cfg.get("name","Candidate")
    return slug(nm).split('-')[-1].title() if nm and nm!="Your Name" else "Resume"
def resume_name(co,role):
    return f"{_lastname()}_{slug(co).title().replace('-','')}_{slug(role)[:28]}_{datetime.date.today().isoformat()}.docx"
def new_id(rows): return (max([r.get('id',0) for r in rows])+1) if rows else 1
def load_cache():
    try:
        d=json.load(open(CACHE)); return d.get("roles",[]),d.get("pulled","")
    except Exception: return [],""

# background pull state
PULL={"running":False,"done":0,"total":0,"phase":"","msg":""}
def bg_pull():
    PULL.update(running=True,done=0,total=0,phase="starting",msg="Starting…")
    def prog(phase=None,done=0,total=0,msg=""):
        if phase: PULL["phase"]=phase
        PULL["done"]=done; PULL["total"]=total; PULL["msg"]=msg
    try: pull_roles(prog)
    except Exception as e:
        PULL.update(phase="error",msg=f"Pull failed: {e}")
    finally: PULL["running"]=False

class H(http.server.BaseHTTPRequestHandler):
    def log_message(self,*a): pass
    def _s(self,code,body,ctype="application/json"):
        self.send_response(code);self.send_header("Content-Type",ctype);self.send_header("Cache-Control","no-store");self.end_headers()
        self.wfile.write(body.encode() if isinstance(body,str) else body)
    def do_GET(self):
        if self.path=="/" or self.path.startswith("/?"): self._s(200,PAGE,"text/html");return
        if self.path=="/api/state":
            roles,pulled=load_cache()
            ncomp=len(GREENHOUSE)+len(LEVER)+len(ASHBY)
            loc=_cfg.get("locations",{})
            self._s(200,json.dumps({"rows":load(),"stages":STAGES,"roles":roles,"pulled":pulled,
                "pull":PULL,"configured":bool(_cfg),"n_companies":ncomp,
                "name":_cfg.get("name",""),
                "home_city":loc.get("home_city",""),"remote_scope":loc.get("remote_scope","US"),
                "variants":_cfg.get("resume_variants",{})}));return
        if self.path=="/api/pullstatus": self._s(200,json.dumps(PULL));return
        self._s(404,"{}")
    def do_POST(self):
        n=int(self.headers.get("Content-Length",0));body=json.loads(self.rfile.read(n) or "{}")
        rows=load()
        if self.path=="/api/refresh":
            if not PULL["running"]: threading.Thread(target=bg_pull,daemon=True).start()
            self._s(200,json.dumps({"started":True}));return
        if self.path=="/api/add":
            co=body.get("company","").strip();role=body.get("role","").strip()
            if not co or not role: self._s(400,json.dumps({"error":"company and role required"}));return
            # skip dupes
            if any((r["company"].lower()==co.lower() and r["role"].lower()==role.lower()) for r in rows):
                self._s(200,json.dumps({"ok":True,"dupe":True}));return
            rows.append({"id":new_id(rows),"company":co,"role":role,"loc":body.get("loc",""),
                "wt":body.get("wt",""),"fit":body.get("fit",""),"url":body.get("url",""),
                "stage":body.get("stage","To apply"),"resume":body.get("resume") or resume_name(co,role),
                "applied":body.get("applied",""),"next":body.get("next",""),"notes":body.get("notes",""),
                "created":datetime.date.today().isoformat()})
            save(rows);self._s(200,json.dumps({"ok":True}));return
        if self.path=="/api/update":
            for r in rows:
                if r["id"]==body.get("id"):
                    for k in ["stage","applied","next","notes","resume","fit","wt","loc","url","company","role"]:
                        if k in body: r[k]=body[k]
            save(rows);self._s(200,json.dumps({"ok":True}));return
        if self.path=="/api/delete":
            save([r for r in rows if r["id"]!=body.get("id")]);self._s(200,json.dumps({"ok":True}));return
        if self.path=="/api/clear":
            save([]);self._s(200,json.dumps({"ok":True}));return
        self._s(404,"{}")

PAGE = r"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Job Hub</title>
<style>
:root{--ink:#14202e;--soft:#4a5a6a;--paper:#eef0f4;--panel:#fff;--line:#dde0e8;
--pri:#3b4d8f;--pri-s:#e7ebf7;--go:#1f7a5c;--go-s:#e2f0ea;--warn:#c06a2a;--warn-s:#f7ece0;
--rej:#9a3b3b;--rej-s:#f3e3e3;--gold:#b8862a;--gold-s:#f6eed8;--low:#c0472f;
--mono:ui-monospace,'Cascadia Code',Menlo,monospace;--sans:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;
--serif:'Iowan Old Style','Palatino Linotype',Georgia,serif;}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font-family:var(--sans);line-height:1.5}
.wrap{max-width:1180px;margin:0 auto;padding:24px 20px 90px}
header{display:flex;align-items:flex-end;justify-content:space-between;gap:16px;flex-wrap:wrap;border-bottom:1px solid var(--line);padding-bottom:14px;margin-bottom:6px}
h1{font-family:var(--serif);font-size:26px;margin:0}h1 span{color:var(--pri)}
.sub{font-family:var(--mono);font-size:11px;text-transform:uppercase;letter-spacing:.09em;color:var(--soft);margin-top:3px}
.tabs{display:flex;gap:6px;margin:18px 0 20px}
.tab{padding:10px 20px;border-radius:9px 9px 0 0;border:1px solid var(--line);border-bottom:none;background:#e4e7ee;color:var(--soft);font-weight:600;font-size:14px;cursor:pointer}
.tab.active{background:var(--panel);color:var(--ink)}
.panelwrap{background:var(--panel);border:1px solid var(--line);border-radius:0 11px 11px 11px;padding:20px}
.controls{display:flex;gap:9px;flex-wrap:wrap;align-items:center;margin-bottom:16px}
input,select{font-family:var(--sans);font-size:14px;padding:9px 11px;border:1px solid var(--line);border-radius:8px;background:#fff}
#search,#psearch{flex:1;min-width:170px}
.btn{border:none;border-radius:8px;font-weight:600;cursor:pointer;padding:10px 16px;font-size:14px}
.btn.pri{background:var(--ink);color:#fff}.btn.pri:hover{background:var(--pri)}
.btn.ghost{background:#fff;border:1px solid var(--line);color:var(--ink)}
.count{font-size:13px;color:var(--soft);margin-left:auto}
table{width:100%;border-collapse:collapse}
th{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--pri);text-align:left;padding:10px;border-bottom:1px solid var(--line);cursor:pointer;white-space:nowrap}
td{padding:11px 10px;border-bottom:1px solid #eef0f4;font-size:14px;vertical-align:top}
tr:hover td{background:#fafbfd}
.co{font-weight:600;text-transform:capitalize;white-space:nowrap}
.role a{color:var(--ink);text-decoration:none;font-weight:500}.role a:hover{color:var(--pri);text-decoration:underline}
.gaps{display:block;font-size:11px;color:var(--warn);margin-top:2px}
.fit{font-family:var(--mono);font-weight:700;text-align:center;white-space:nowrap}
.wt{font-family:var(--mono);font-size:11px;padding:2px 8px;border-radius:10px;background:#eef1f6;color:var(--pri)}
.wt.Remote{background:var(--go-s);color:var(--go)}.wt.Hybrid{background:#e8eef6;color:#2d4a63}.wt.On-site{background:var(--warn-s);color:var(--warn)}
.addbtn{font-size:12px;font-family:var(--mono);background:var(--go);color:#fff;border:none;padding:6px 11px;border-radius:6px;cursor:pointer;white-space:nowrap}
.addbtn.in{background:#cbd3d0;cursor:default}
.funnel{display:grid;grid-template-columns:repeat(6,1fr);gap:8px;margin-bottom:18px}
.stat{background:#fafbfd;border:1px solid var(--line);border-radius:10px;padding:11px;cursor:pointer;text-align:center}
.stat.active{border-color:var(--pri);box-shadow:0 0 0 2px var(--pri-s)}
.stat .n{font-family:var(--serif);font-size:24px;font-weight:600}
.stat .l{font-size:10px;text-transform:uppercase;letter-spacing:.05em;color:var(--soft)}
@media(max-width:760px){.funnel{grid-template-columns:repeat(3,1fr)}}
.app{border:1px solid var(--line);border-radius:11px;padding:12px 14px;margin-bottom:9px;display:grid;grid-template-columns:52px 1fr auto;gap:13px;align-items:center}
.appfit{font-family:var(--mono);font-weight:700;text-align:center;border-radius:8px;padding:7px 0}
.resume{font-family:var(--mono);font-size:11px;color:var(--soft);cursor:pointer;border-bottom:1px dotted var(--soft)}
.resume:hover{color:var(--pri)}
.stage{font-weight:600;font-size:13px;padding:7px 9px;border-radius:8px;border:1px solid var(--line);cursor:pointer}
.s-Toapply{background:#f1f2f6;color:#555}.s-Applied{background:var(--pri-s);color:var(--pri)}.s-Screen{background:var(--gold-s);color:var(--gold)}
.s-Interview{background:var(--warn-s);color:var(--warn)}.s-Offer{background:var(--go-s);color:var(--go)}.s-Rejected{background:var(--rej-s);color:var(--rej)}
.icon{background:none;border:none;cursor:pointer;color:var(--soft);font-size:15px;padding:4px}.icon:hover{color:var(--pri)}
.next{font-size:11px;color:var(--warn);font-family:var(--mono)}.next.od{color:var(--rej);font-weight:700}
.meta{display:flex;gap:7px;flex-wrap:wrap;margin-top:5px;align-items:center}
.tag{font-family:var(--mono);font-size:10px;padding:2px 7px;border-radius:9px;background:#eef1f6;color:var(--pri)}
.empty{text-align:center;color:var(--soft);padding:44px 20px}
.pullbar{background:var(--pri-s);border-radius:9px;padding:11px 15px;margin-bottom:16px;font-size:13px;color:var(--pri);display:none}
.pullbar.show{display:block}
.scrim{position:fixed;inset:0;background:rgba(20,32,46,.4);display:none;align-items:center;justify-content:center;padding:20px;z-index:10}
.scrim.show{display:flex}
.modal{background:#fff;border-radius:15px;max-width:520px;width:100%;padding:22px;max-height:90vh;overflow:auto}
.modal h2{font-family:var(--serif);margin:0 0 12px}
.f{margin-bottom:12px}.f label{display:block;font-size:11px;font-weight:600;text-transform:uppercase;color:var(--soft);margin-bottom:4px}
.f input,.f select,.f textarea{width:100%;padding:9px 11px;border:1px solid var(--line);border-radius:8px;font-size:14px}
.r2{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.resumebox{background:var(--pri-s);border-radius:8px;padding:9px 11px;font-family:var(--mono);font-size:12px;color:var(--pri);word-break:break-all}
.ma{display:flex;gap:10px;justify-content:flex-end;margin-top:14px}
.toast{position:fixed;bottom:22px;left:50%;transform:translateX(-50%) translateY(20px);opacity:0;background:var(--ink);color:#fff;padding:11px 18px;border-radius:10px;font-size:14px;transition:.25s;z-index:20;pointer-events:none}
.toast.show{opacity:1;transform:translateX(-50%) translateY(0)}
</style></head><body><div class="wrap">
<header><div><h1>Job <span>Hub</span></h1><div class="sub" id="sub">loading…</div></div>
<button class="btn pri" onclick="openAdd()">+ Add manually</button></header>

<div class="tabs">
 <div class="tab active" id="tabFind" onclick="showTab('find')">Find roles</div>
 <div class="tab" id="tabPipe" onclick="showTab('pipe')">Pipeline</div>
</div>

<!-- FIND -->
<div class="panelwrap" id="find">
 <div class="pullbar" id="pullbar"></div>
 <div class="controls">
  <input id="search" placeholder="Search role, company, location…" oninput="renderFind()">
  <select id="wtF" onchange="renderFind()"><option value="">Any work-type</option><option>Remote</option><option>Hybrid</option><option>On-site</option></select>
  <select id="locF" onchange="renderFind()"><option value="">Any location</option><option value="__CITY__">Local (on-site/hybrid)</option><option value="__REMOTE__">Remote (US only)</option></select>
  <select id="radF" onchange="renderFind()" title="Radius from your zip"><option value="10">10 mi</option><option value="15">15 mi</option><option value="20">20 mi</option><option value="25" selected>25 mi</option><option value="30">30 mi</option><option value="35">35 mi</option><option value="40">40 mi</option><option value="45">45 mi</option><option value="50">50 mi</option></select>
  <select id="revF" onchange="renderFind()" title="Claude triage verdict"><option value="">Any review</option><option value="APPLY">APPLY only</option><option value="APPLY,MAYBE">APPLY + MAYBE</option><option value="unreviewed">Not reviewed</option></select>
  <select id="fitF" onchange="renderFind()"><option value="0">Any fit</option><option value="75">75%+</option><option value="60">60%+</option><option value="45">45%+</option></select>
  <button class="btn ghost" onclick="doRefresh()" id="refreshBtn">↻ Refresh roles</button>
 </div>
 <table><thead><tr>
  <th onclick="sortFind('fit')">Fit</th><th onclick="sortFind('co')">Company</th><th onclick="sortFind('title')">Role</th>
  <th onclick="sortFind('wt')">Type</th><th onclick="sortFind('loc')">Location</th><th></th>
 </tr></thead><tbody id="findBody"></tbody></table>
 <div class="empty" id="findEmpty" style="display:none"></div>
</div>

<!-- PIPELINE -->
<div class="panelwrap" id="pipe" style="display:none">
 <div class="funnel" id="funnel"></div>
 <div class="controls">
  <input id="psearch" placeholder="Search pipeline…" oninput="renderPipe()">
  <select id="pwtF" onchange="renderPipe()"><option value="">Any work-type</option><option>Remote</option><option>Hybrid</option><option>On-site</option></select>
  <button class="btn ghost" onclick="clearPipeFilters()">Clear filters</button>
  <button class="btn ghost" onclick="wipePipeline()" style="border-color:#d9b3b3;color:#9a3b3b">Clear pipeline</button>
 </div>
 <div id="pipeList"></div>
</div>

<div class="scrim" id="scrim"><div class="modal" id="modal"></div></div>
<div class="toast" id="toast"></div>
</div>
<script>
let ROWS=[],STAGES=[],ROLES=[],findSort="fit",findDir=-1,pipeStage="",editId=null;
let HOME_CITY="",REMOTE_SCOPE="US";
// City name -> match the city and its close variants (not the whole state,
// so 'Los Angeles' doesn't pull in every California role).
// Cities within ~50 miles of Montrose/91020 (Los Angeles metro). A role's
// location matches "my area" if it names any of these, OR names greater-LA /
// SoCal generally. Kept to SoCal terms so it doesn't catch other states.
const LA_CITIES={
  10:["montrose","la crescenta","glendale","la canada","la cañada","flintridge","tujunga","sunland","altadena","eagle rock","highland park","verdugo city","sun valley"],
  15:["pasadena","south pasadena","burbank","north hollywood","atwater village","silver lake","los feliz","echo park","san marino","sierra madre","toluca lake","studio city","universal city","glassell park","mount washington","alhambra","monterey park"],
  20:["los angeles","downtown la","hollywood","west hollywood","sherman oaks","van nuys","arcadia","monrovia","temple city","rosemead","el monte","el sereno","boyle heights","commerce","vernon","valley village","north hills","panorama city","encino","san fernando","sylmar","mission hills","granada hills","duarte","irwindale","baldwin park"],
  25:["beverly hills","century city","westwood","culver city","santa monica","brentwood","tarzana","reseda","northridge","chatsworth","canoga park","woodland hills","winnetka","west covina","covina","azusa","glendora","montebello","pico rivera","whittier","downey","bell","bell gardens","huntington park","maywood","santa clarita","valencia","newhall","saugus","marina del rey","playa vista","playa del rey","mar vista","venice"],
  30:["inglewood","hawthorne","el segundo","manhattan beach","hermosa beach","gardena","compton","norwalk","cerritos","la mirada","santa fe springs","industry","city of industry","walnut","diamond bar","rowland heights","hacienda heights","la puente","pomona","claremont","san dimas","calabasas","agoura hills","malibu","topanga","chatsworth"],
  35:["torrance","redondo beach","carson","lakewood","bellflower","paramount","artesia","buena park","la habra","brea","fullerton","placentia","yorba linda","chino","chino hills","ontario","upland","rancho cucamonga","montclair","thousand oaks","westlake village","simi valley","moorpark"],
  40:["long beach","san pedro","wilmington","harbor city","lomita","seal beach","los alamitos","cypress","stanton","anaheim","orange","villa park","garden grove","fontana","rialto","colton","camarillo","newbury park","port hueneme"],
  45:["huntington beach","westminster","fountain valley","santa ana","tustin","costa mesa","san bernardino","redlands","loma linda","oxnard","ventura","moorpark","corona","norco"],
  50:["irvine","newport beach","lake forest","mission viejo","laguna beach","laguna hills","aliso viejo","riverside","moreno valley","perris","temecula","murrieta","palmdale","lancaster","santa paula","fillmore","hesperia","victorville"],
};

// Roles are LOCAL if their location names a city within the selected radius.
// Never matches on bare state ("CA") — that's what pulled in SF/NY/Canada before.
const NON_US=/canada|\bcan\b|toronto|montr|quebec|british columbia|calgary|vancouver|alberta|united kingdom|\buk\b|england|london|dublin|ireland|europe|emea|apac|\bindia\b|australia|germany|france|netherlands|singapore|japan|brazil|mexico city/i;

function citiesWithin(miles){
  let out=[];
  for(const band of Object.keys(LA_CITIES)){
    if(parseInt(band,10)<=miles) out=out.concat(LA_CITIES[band]);
  }
  return out;
}
function matchesRadius(loc, miles){
  if(!loc)return false;
  const L=loc.toLowerCase();
  if(NON_US.test(L))return false;
  return citiesWithin(miles).some(c=>L.includes(c));
}
function isRemoteUS(loc,wt){
  const L=(loc||'').toLowerCase();
  const remote = wt==='Remote' || /\bremote\b|work from home|wfh|anywhere/i.test(L);
  if(!remote)return false;
  if(NON_US.test(L))return false;                       // named foreign country
  // "Remote - X" where X isn't US-ish -> reject (catches any country we didn't list)
  const m=L.match(/remote\s*[-–—:]\s*([a-z .]+)/);
  if(m){
    const scope=m[1].trim();
    if(!/^(us|u\.s\.|usa|united states|america|north america|nationwide|anywhere)\b/.test(scope))return false;
  }
  return true;
}

function toast(m){const t=document.getElementById('toast');t.textContent=m;t.classList.add('show');setTimeout(()=>t.classList.remove('show'),2000);}
async function api(p,m,b){const o={method:m||'GET',headers:{'Content-Type':'application/json'}};if(b)o.body=JSON.stringify(b);return (await fetch(p,o)).json();}
function sClass(s){return 's-'+s.replace(/\s/g,'');}
function fitCol(f){f=+f;if(!f)return{b:'#f1f2f6',c:'#888'};return f>=70?{b:'var(--go-s)',c:'var(--go)'}:f>=45?{b:'var(--warn-s)',c:'var(--warn)'}:{b:'var(--rej-s)',c:'var(--low)'};}
function daysTo(d){if(!d)return null;return Math.ceil((new Date(d)-new Date().setHours(0,0,0,0))/8.64e7);}

async function boot(){
  const d=await api('/api/state');
  ROWS=d.rows;STAGES=d.stages;ROLES=d.roles;
  if(d.name&&d.name!=='Your Name'){LASTNAME=d.name.replace(/[^A-Za-z0-9]+/g,'-').replace(/(^-|-$)/g,'').split('-').pop();LASTNAME=LASTNAME.charAt(0).toUpperCase()+LASTNAME.slice(1);}
  document.getElementById('sub').textContent=`${ROWS.length} tracked · ${ROLES.length} roles found`+(d.pulled?` · pulled ${d.pulled.slice(0,10)}`:'');
  HOME_CITY=(d.home_city||'').trim();REMOTE_SCOPE=(d.remote_scope||'US').trim();
  VARIANTS=d.variants||{};
  if(!ROLES.length){document.getElementById('findEmpty').style.display='block';document.getElementById('findEmpty').innerHTML='No roles pulled yet. Click <b>↻ Refresh roles</b> to pull live listings (takes a few minutes).';}
  renderFind();renderPipe();
  if(d.pull&&d.pull.running)watchPull();
}
function showTab(t){
  document.getElementById('find').style.display=t==='find'?'block':'none';
  document.getElementById('pipe').style.display=t==='pipe'?'block':'none';
  document.getElementById('tabFind').classList.toggle('active',t==='find');
  document.getElementById('tabPipe').classList.toggle('active',t==='pipe');
}
function tracked(co,title){return ROWS.some(r=>r.company.toLowerCase()===co.toLowerCase()&&r.role.toLowerCase()===title.toLowerCase());}

function sortFind(k){if(findSort===k)findDir*=-1;else{findSort=k;findDir=(k==='fit')?-1:1;}renderFind();}
function renderFind(){
  let rows=ROLES.slice();
  const q=document.getElementById('search').value.toLowerCase().trim();
  const wt=document.getElementById('wtF').value,lf=document.getElementById('locF').value,mf=+document.getElementById('fitF').value;
  if(q)rows=rows.filter(r=>(r.co+' '+r.title+' '+r.loc).toLowerCase().includes(q));
  if(wt)rows=rows.filter(r=>r.wt===wt);
  const radius=+(document.getElementById('radF')||{value:25}).value||25;
  if(lf==='__CITY__')rows=rows.filter(r=>matchesRadius(r.loc,radius)&&r.wt!=='Remote');
  else if(lf==='__REMOTE__')rows=rows.filter(r=>isRemoteUS(r.loc,r.wt));
  if(mf)rows=rows.filter(r=>r.fit>=mf);
  const rv=(document.getElementById('revF')||{value:''}).value;
  if(rv==='unreviewed')rows=rows.filter(r=>!r.verdict);
  else if(rv){const want=rv.split(',');rows=rows.filter(r=>r.verdict&&want.includes(r.verdict));}
  rows.sort((a,b)=>{let x=a[findSort],y=b[findSort];if(typeof x==='string'){x=x.toLowerCase();y=y.toLowerCase();}return x<y?-findDir:x>y?findDir:0;});
  const b=document.getElementById('findBody');
  window._shown=rows;   // lookup table so buttons pass an index, not embedded JSON
  b.innerHTML=rows.map((r,ri)=>{const fc=fitCol(r.fit),isin=tracked(r.co,r.title);
    return `<tr>
     <td class="fit" style="color:${fc.c}">${r.fit}%</td>
     <td class="co">${r.co}</td>
     <td class="role"><a href="${r.url}" target="_blank" rel="noopener">${r.title}</a>${r.verdict?`<span class="gaps" style="color:${r.verdict==='APPLY'?'var(--go)':r.verdict==='MAYBE'?'var(--warn)':'var(--rej)'};font-weight:600">${r.verdict}${r.verdict_why?' — '+r.verdict_why:''}</span>`:''}${r.gaps&&r.gaps.length?`<span class="gaps">gaps: ${r.gaps.join(' · ')}</span>`:''}</td>
     <td><span class="wt ${r.wt}">${r.wt}</span></td>
     <td style="color:var(--soft);font-size:13px">${r.loc}</td>
     <td>${isin?'<button class="addbtn in">✓ in pipeline</button>':`<button class="addbtn" onclick="applyRole(${ri})">Apply →</button>`}</td>
    </tr>`;}).join('');
  document.getElementById('findEmpty').style.display=rows.length?'none':(ROLES.length?'block':'block');
  if(rows.length&&ROLES.length)document.getElementById('findEmpty').style.display='none';
  else if(ROLES.length&&!rows.length){document.getElementById('findEmpty').style.display='block';document.getElementById('findEmpty').textContent='No roles match your filters.';}
}
let VARIANTS={};  // {label: filename}
function suggestVariant(title){
  const t=(title||'').toLowerCase();
  // map job title -> best-fit variant label present in VARIANTS
  const labels=Object.keys(VARIANTS);
  if(!labels.length)return null;
  const pick=(kw)=>labels.find(l=>kw.some(k=>l.toLowerCase().includes(k)));
  if(/solution|sales engineer|\bse\b|architect|technical|pre-?sales|consultant/.test(t)){
    const v=pick(['solution','se','consultant']);if(v)return v;
  }
  if(/director|head|vp|lead|manager|principal|senior manager/.test(t)){
    const v=pick(['director','leader']);if(v)return v;
  }
  const ae=pick(['account executive','ae']);if(ae)return ae;
  return labels[0];
}
async function applyRole(idx){
  const r=(window._shown||[])[idx];
  if(!r){toast('Could not read that role — try refreshing the page');return;}
  const labels=Object.keys(VARIANTS);
  let variantLabel=suggestVariant(r.title);
  // build a compact prompt letting them confirm/override the variant
  if(labels.length>1){
    const menu=labels.map((l,i)=>`${i+1}. ${l}${l===variantLabel?'  (suggested)':''}`).join('\n');
    const ans=prompt(`Apply to ${r.co} — ${r.title}\n\nWhich resume variant? Type a number:\n\n${menu}`,
      String(labels.indexOf(variantLabel)+1));
    if(ans===null)return;
    const idx=parseInt(ans,10)-1;
    if(idx>=0&&idx<labels.length)variantLabel=labels[idx];
  }
  const baseFile=(VARIANTS[variantLabel]||'').trim();
  const fname=suggestName(r.co,r.title);
  // copy the filename to save-as, open the posting, log as Applied
  try{await navigator.clipboard.writeText(fname);}catch(e){}
  if(r.url)window.open(r.url,'_blank','noopener');
  const today=new Date().toISOString().slice(0,10);
  const res=await api('/api/add','POST',{company:r.co,role:r.title,loc:r.loc,wt:r.wt,fit:r.fit,url:r.url,
    stage:'Applied',resume:fname,applied:today,notes:variantLabel?('Variant: '+variantLabel+(baseFile?(' ('+baseFile+')'):'')):''});
  if(res.dupe){toast('Already in your pipeline');return;}
  const d=await api('/api/state');ROWS=d.rows;renderFind();renderPipe();
  document.getElementById('sub').textContent=`${ROWS.length} tracked · ${ROLES.length} roles found`;
  toast('Applied → '+r.co+' · save resume as the copied filename · variant: '+(variantLabel||'default'));
}

async function doRefresh(){
  await api('/api/refresh','POST',{});
  document.getElementById('pullbar').classList.add('show');
  document.getElementById('refreshBtn').textContent='Pulling…';
  watchPull();
}
async function watchPull(){
  const bar=document.getElementById('pullbar');bar.classList.add('show');
  const tick=async()=>{
    let p;
    try{p=await api('/api/pullstatus');}catch(e){bar.innerHTML='⚠ Lost connection to the app. Is it still running in PowerShell?';return;}
    if(p.running){
      let label='Working…';
      if(p.phase==='boards')label=`Searching company boards — ${p.done}/${p.total}`;
      else if(p.phase==='scoring')label=`Scoring roles against your resume — ${p.done}/${p.total}`;
      else if(p.phase==='starting')label='Starting up…';
      const pct=p.total?Math.round(100*p.done/p.total):0;
      bar.innerHTML=`<div style="font-weight:600;margin-bottom:6px">${label}</div>`
        +`<div style="background:#d3daea;border-radius:6px;height:8px;overflow:hidden"><div style="background:var(--pri);height:100%;width:${pct}%;transition:width .3s"></div></div>`
        +`<div style="font-size:11px;color:var(--soft);margin-top:5px;font-family:var(--mono)">${p.msg||''}</div>`;
      setTimeout(tick,900);
    } else {
      const d=await api('/api/state');ROLES=d.roles;
      document.getElementById('refreshBtn').textContent='↻ Refresh roles';
      document.getElementById('sub').textContent=`${ROWS.length} tracked · ${ROLES.length} roles found`;
      renderFind();
      if(!ROLES.length){
        bar.style.background='var(--warn-s)';bar.style.color='#7a4318';
        bar.innerHTML=`<div style="font-weight:600">No roles found</div>`
          +`<div style="font-size:12px;margin-top:4px">${p.msg||'The search returned nothing.'}</div>`
          +`<div style="font-size:12px;margin-top:6px">Common causes: company slugs in config.json are wrong, your internet blocked the boards, or the role filters are too narrow. You can also add more companies to config.json.</div>`;
      } else {
        bar.style.background='var(--go-s)';bar.style.color='#195a4b';
        bar.innerHTML=`✓ ${p.msg||('Found '+ROLES.length+' roles.')} Showing them now.`;
        setTimeout(()=>{bar.classList.remove('show');bar.style.background='';bar.style.color='';},4000);
      }
    }
  };tick();
}

// PIPELINE
function renderPipe(){
  const c={};STAGES.forEach(s=>c[s]=0);ROWS.forEach(r=>c[r.stage]=(c[r.stage]||0)+1);
  document.getElementById('funnel').innerHTML=STAGES.map(s=>`<div class="stat ${pipeStage===s?'active':''}" onclick="togglePipe('${s}')"><div class="n">${c[s]||0}</div><div class="l">${s}</div></div>`).join('');
  const q=document.getElementById('psearch').value.toLowerCase().trim(),wt=document.getElementById('pwtF').value;
  let rows=ROWS.slice();
  if(pipeStage)rows=rows.filter(r=>r.stage===pipeStage);
  if(wt)rows=rows.filter(r=>r.wt===wt);
  if(q)rows=rows.filter(r=>(r.company+' '+r.role+' '+(r.loc||'')).toLowerCase().includes(q));
  const ord={};STAGES.forEach((s,i)=>ord[s]=i);
  rows.sort((a,b)=>(ord[a.stage]-ord[b.stage])||((+b.fit||0)-(+a.fit||0)));
  const list=document.getElementById('pipeList');
  if(!rows.length){list.innerHTML=`<div class="empty">${ROWS.length?'Nothing matches.':'No applications yet. Add roles from the Find tab.'}</div>`;return;}
  list.innerHTML=rows.map(r=>{const fc=fitCol(r.fit),dt=daysTo(r.next);
    const nx=r.next?`<span class="next ${dt<0?'od':''}">${dt<0?'follow-up overdue':dt===0?'follow up today':'follow up in '+dt+'d'}</span>`:'';
    return `<div class="app">
     <div class="appfit" style="background:${fc.b};color:${fc.c}">${r.fit?r.fit+'%':'—'}</div>
     <div><div style="font-weight:700">${r.company} ${r.url?`<a href="${r.url}" target="_blank" style="font-size:12px;color:var(--pri)">↗</a>`:''}</div>
       <div style="color:var(--soft);font-size:13.5px">${r.role}</div>
       <div class="meta">${r.wt?`<span class="tag">${r.wt}</span>`:''}${r.loc?`<span class="tag" style="background:#eee;color:#666">${r.loc}</span>`:''}
         <span class="resume" onclick="copyName('${r.resume}')" title="Copy filename">📄 ${r.resume}</span>${nx}</div></div>
     <div style="display:flex;gap:7px;align-items:center">
       <select class="stage ${sClass(r.stage)}" onchange="setStage(${r.id},this.value)">${STAGES.map(s=>`<option ${s===r.stage?'selected':''}>${s}</option>`).join('')}</select>
       <button class="icon" onclick="openEdit(${r.id})">✎</button><button class="icon" onclick="del(${r.id})">🗑</button></div>
    </div>`;}).join('');
}
function togglePipe(s){pipeStage=pipeStage===s?"":s;renderPipe();}
function clearPipeFilters(){pipeStage="";document.getElementById('psearch').value="";document.getElementById('pwtF').value="";renderPipe();}
async function wipePipeline(){
  if(!confirm(`Clear ALL ${ROWS.length} applications from your pipeline?\n\nThis cannot be undone. (Your found roles in the Find tab are NOT affected.)`))return;
  if(!confirm('Really clear everything? Last chance.'))return;
  await api('/api/clear','POST',{});ROWS=[];pipeStage="";renderPipe();renderFind();
  document.getElementById('sub').textContent=`${ROWS.length} tracked · ${ROLES.length} roles found`;
  toast('Pipeline cleared');
}
async function setStage(id,st){const patch={id,stage:st};const r=ROWS.find(x=>x.id===id);if(st==='Applied'&&r&&!r.applied)patch.applied=new Date().toISOString().slice(0,10);
  await api('/api/update','POST',patch);Object.assign(r,patch);renderPipe();toast('→ '+st);}
function copyName(n){navigator.clipboard.writeText(n);toast('Filename copied');}
function openAdd(){editId=null;showModal({stage:'To apply'});}
function openEdit(id){editId=id;showModal(ROWS.find(r=>r.id===id));}
let LASTNAME="Resume";
function suggestName(co,ro){const t=new Date().toISOString().slice(0,10);const c=(co||'').replace(/[^A-Za-z0-9]+/g,'-').replace(/(^-|-$)/g,'').split('-').map(w=>w.charAt(0).toUpperCase()+w.slice(1)).join('');const rr=(ro||'').replace(/[^A-Za-z0-9]+/g,'-').replace(/(^-|-$)/g,'').slice(0,28);return `${LASTNAME}_${c||'Company'}_${rr||'Role'}_${t}.docx`;}
function showModal(d){d=d||{};const isEdit=editId!==null;const m=document.getElementById('modal');
  m.innerHTML=`<h2>${isEdit?'Edit application':'Add application'}</h2>
   <div class="r2"><div class="f"><label>Company</label><input id="f_co" value="${d.company||''}" oninput="ln()"></div>
   <div class="f"><label>Role</label><input id="f_ro" value="${d.role||''}" oninput="ln()"></div></div>
   <div class="r2"><div class="f"><label>Location</label><input id="f_loc" value="${d.loc||''}"></div>
   <div class="f"><label>Work-type</label><select id="f_wt"><option value="">—</option>${['Remote','Hybrid','On-site'].map(x=>`<option ${d.wt===x?'selected':''}>${x}</option>`).join('')}</select></div></div>
   <div class="r2"><div class="f"><label>Fit %</label><input id="f_fit" value="${d.fit||''}"></div>
   <div class="f"><label>Stage</label><select id="f_stage">${STAGES.map(s=>`<option ${d.stage===s?'selected':''}>${s}</option>`).join('')}</select></div></div>
   <div class="f"><label>Job link</label><input id="f_url" value="${d.url||''}"></div>
   <div class="f"><label>Resume filename</label><div class="resumebox" id="rname">${d.resume||suggestName(d.company,d.role)}</div></div>
   <div class="r2"><div class="f"><label>Date applied</label><input id="f_applied" type="date" value="${d.applied||''}"></div>
   <div class="f"><label>Follow-up on</label><input id="f_next" type="date" value="${d.next||''}"></div></div>
   <div class="f"><label>Notes</label><textarea id="f_notes" rows="2">${d.notes||''}</textarea></div>
   <div class="ma"><button class="btn ghost" onclick="closeM()">Cancel</button><button class="btn pri" onclick="saveM()">${isEdit?'Save':'Add'}</button></div>`;
  document.getElementById('scrim').classList.add('show');window._edited=isEdit;}
function ln(){if(window._edited)return;document.getElementById('rname').textContent=suggestName(document.getElementById('f_co').value,document.getElementById('f_ro').value);}
function closeM(){document.getElementById('scrim').classList.remove('show');}
async function saveM(){const p={company:document.getElementById('f_co').value.trim(),role:document.getElementById('f_ro').value.trim(),
  loc:document.getElementById('f_loc').value.trim(),wt:document.getElementById('f_wt').value,fit:document.getElementById('f_fit').value.trim(),
  stage:document.getElementById('f_stage').value,url:document.getElementById('f_url').value.trim(),resume:document.getElementById('rname').textContent,
  applied:document.getElementById('f_applied').value,next:document.getElementById('f_next').value,notes:document.getElementById('f_notes').value.trim()};
  if(!p.company||!p.role){toast('Company and role required');return;}
  if(editId!==null){p.id=editId;await api('/api/update','POST',p);Object.assign(ROWS.find(r=>r.id===editId),p);}
  else{await api('/api/add','POST',p);const d=await api('/api/state');ROWS=d.rows;}
  closeM();renderPipe();renderFind();toast('Saved');}
async function del(id){if(!confirm('Delete this application?'))return;await api('/api/delete','POST',{id});ROWS=ROWS.filter(r=>r.id!==id);renderPipe();renderFind();toast('Deleted');}
document.getElementById('scrim').addEventListener('click',e=>{if(e.target.id==='scrim')closeM();});
boot();
</script></body></html>"""

def open_browser(): webbrowser.open(f"http://localhost:{PORT}")
if __name__=="__main__":
    have=os.path.exists(CACHE)
    print("\n  Job Hub running.")
    print(f"  -> http://localhost:{PORT} (browser opens automatically)")
    print(f"  -> Pipeline data: {DATA}")
    if not have: print("  -> No roles cached yet — click 'Refresh roles' in the Find tab (takes a few min).")
    print("  -> Stop: Ctrl+C\n")
    threading.Timer(0.8,open_browser).start()
    socketserver.TCPServer.allow_reuse_address=True
    with socketserver.TCPServer(("127.0.0.1",PORT),H) as httpd:
        try: httpd.serve_forever()
        except KeyboardInterrupt: print("\n  Stopped. Data saved.\n")
