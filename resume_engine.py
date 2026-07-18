#!/usr/bin/env python3
"""
resume_engine.py — resume utilities that work on ANY .docx resume.
Detects job/experience sections and their last bullet (injection anchor)
using paragraph styles first, with a text-heuristic fallback.
"""
import zipfile, shutil, os, re

def extract_text(docx_path):
    xml=zipfile.ZipFile(docx_path).read('word/document.xml').decode('utf-8','replace')
    # Remove drawing/picture blocks (they contain attributes with '>' that break naive parsing)
    xml=re.sub(r'<w:drawing\b.*?</w:drawing>', ' ', xml, flags=re.S)
    xml=re.sub(r'<w:pict\b.*?</w:pict>', ' ', xml, flags=re.S)
    # Extract text runs: <w:t ...>TEXT</w:t> — [^<] ensures we stop at the next tag, not overreach
    texts=re.findall(r'<w:t\b[^>]*>([^<]*)</w:t>', xml)
    out=' '.join(texts)
    return re.sub(r'\s+',' ',out).replace('&amp;','&').replace('&lt;','<').replace('&gt;','>').strip()

def _paras(xml):
    out=[]
    for m in re.finditer(r'<w:p\b.*?</w:p>', xml, re.S):
        seg=m.group(0)
        txt=' '.join(re.findall(r'<w:t[^>]*>(.*?)</w:t>', seg, re.S)).strip()
        txt=re.sub(r'\s+',' ',txt).replace('&amp;','&')
        style=re.search(r'<w:pStyle w:val="([^"]+)"', seg)
        style=style.group(1) if style else ""
        is_bullet=('<w:numPr' in seg) or ('list' in style.lower())
        out.append(dict(start=m.start(),end=m.end(),text=txt,bullet=is_bullet,style=style))
    return out

SECTION_WORDS=re.compile(r'^(technical skills|skills|education|profile|summary|key competencies|'
                         r'professional experience|experience|work experience|references|'
                         r'certifications|projects|contact|links|awards)$', re.I)
DATE_RE=re.compile(r'(19|20)\d{2}|present|current', re.I)

def detect_roles(docx_path, max_roles=10):
    xml=zipfile.ZipFile(docx_path).read('word/document.xml').decode('utf-8','replace')
    P=_paras(xml)
    n=len(P)

    # Find the heading style used by job titles: the heading level that most
    # often has bullets between it and the next heading of the same level.
    heading_styles={}
    for i,p in enumerate(P):
        st=p['style']
        if st.lower().startswith('heading') and p['text'] and not SECTION_WORDS.match(p['text']):
            if any(P[k]['bullet'] for k in range(i+1,min(i+8,n))):
                heading_styles[st]=heading_styles.get(st,0)+1
    role_style=max(heading_styles,key=heading_styles.get) if heading_styles else None

    # Collect heading positions (job titles) of that style.
    if role_style:
        heads=[i for i,p in enumerate(P) if p['style']==role_style and p['text']
               and not SECTION_WORDS.match(p['text'])]
    else:
        heads=[]

    roles=[]
    for idx,hi in enumerate(heads):
        # bullets belonging to this heading: from here until the next heading of
        # the same style (or end).
        stop=heads[idx+1] if idx+1<len(heads) else n
        last=None
        for k in range(hi+1,stop):
            if P[k]['bullet'] and P[k]['text']:
                last=P[k]['text']
        if last:  # only a real role if it has bullets
            roles.append({"label":P[hi]['text'][:70],"anchor":last})
            if len(roles)>=max_roles: break
    if roles: return roles

    # Fallback: text heuristic for resumes without clean heading styles.
    i=0
    while i<n:
        p=P[i]
        looks_title=(p['text'] and not p['bullet'] and not SECTION_WORDS.match(p['text'])
                     and len(p['text'].split())<=12)
        if looks_title and any(P[k]['bullet'] for k in range(i+1,min(i+5,n))):
            last=None; k=i+1
            while k<n and not (P[k]['text'] and not P[k]['bullet']
                               and len(P[k]['text'].split())<=12 and k>i+1 and P[k-1]['bullet']):
                if P[k]['bullet'] and P[k]['text']: last=P[k]['text']
                k+=1
            if last and last!=p['text']:
                roles.append({"label":p['text'][:70],"anchor":last})
                i=k
                if len(roles)>=max_roles: break
                continue
        i+=1
    return roles

def _is_heading(p, role_style):
    if role_style and p['style']==role_style: return True
    return bool(p['text']) and p['text'].isupper() and len(p['text'].split())<=4

def xml_escape(t): return t.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

def inject(master_path, placements, out_path):
    tmp=out_path+".tmpdir"
    if os.path.exists(tmp): shutil.rmtree(tmp)
    os.makedirs(tmp)
    with zipfile.ZipFile(master_path) as z: z.extractall(tmp)
    doc=os.path.join(tmp,"word","document.xml")
    xml=open(doc,encoding="utf-8").read()
    from collections import OrderedDict
    grouped=OrderedDict()
    for p in placements: grouped.setdefault(p["anchor"],[]).append(p["text"])
    missed=[]
    for anchor,texts in grouped.items():
        target=None
        for m in re.finditer(r'<w:p\b.*?</w:p>', xml, re.S):
            seg=m.group(0)
            t=' '.join(re.findall(r'<w:t[^>]*>(.*?)</w:t>', seg, re.S)).strip()
            t=re.sub(r'\s+',' ',t).replace('&amp;','&')
            if t==anchor: target=m; break
        if not target: missed.append(anchor); continue
        template=target.group(0)
        def mk(t): return re.sub(r"(<w:t[^>]*>).*?(</w:t>)","\\1"+xml_escape(t)+"\\2",template,count=1,flags=re.S)
        injected="".join(mk(t) for t in texts)
        pe=target.end(); xml=xml[:pe]+injected+xml[pe:]
    open(doc,"w",encoding="utf-8").write(xml)
    if os.path.exists(out_path): os.remove(out_path)
    with zipfile.ZipFile(out_path,"w",zipfile.ZIP_DEFLATED) as z:
        for root,_,files in os.walk(tmp):
            for f in files:
                fp=os.path.join(root,f); z.write(fp,os.path.relpath(fp,tmp))
    shutil.rmtree(tmp)
    return missed

if __name__=="__main__":
    import sys
    roles=detect_roles(sys.argv[1] if len(sys.argv)>1 else "master.docx")
    print(f"Detected {len(roles)} roles:")
    for r in roles: print(f"  - {r['label']!r}\n      anchor: {r['anchor'][:50]!r}")

def list_bullets(docx_path, max_roles=10):
    """Return roles with their FULL bullet lists, for replace-picking.
    [{label, anchor, bullets:[{text}]}]"""
    xml=zipfile.ZipFile(docx_path).read('word/document.xml').decode('utf-8','replace')
    P=_paras(xml); n=len(P)
    heading_styles={}
    for i,p in enumerate(P):
        st=p['style']
        if st.lower().startswith('heading') and p['text'] and not SECTION_WORDS.match(p['text']):
            if any(P[k]['bullet'] for k in range(i+1,min(i+8,n))):
                heading_styles[st]=heading_styles.get(st,0)+1
    role_style=max(heading_styles,key=heading_styles.get) if heading_styles else None
    heads=[i for i,p in enumerate(P) if role_style and p['style']==role_style and p['text']
           and not SECTION_WORDS.match(p['text'])]
    roles=[]
    for idx,hi in enumerate(heads):
        stop=heads[idx+1] if idx+1<len(heads) else n
        bl=[P[k]['text'] for k in range(hi+1,stop) if P[k]['bullet'] and P[k]['text']]
        if bl:
            roles.append({"label":P[hi]['text'][:70],"anchor":bl[-1],
                          "bullets":[{"text":b} for b in bl]})
            if len(roles)>=max_roles: break
    return roles

def apply_changes(master_path, changes, out_path):
    """changes: list of either
        {"mode":"replace","find":<exact original bullet text>,"text":<new text>}
        {"mode":"add","anchor":<bullet text to add after>,"text":<new text>}
       Replaces or inserts while preserving formatting. Returns list of misses."""
    tmp=out_path+".tmpdir"
    if os.path.exists(tmp): shutil.rmtree(tmp)
    os.makedirs(tmp)
    with zipfile.ZipFile(master_path) as z: z.extractall(tmp)
    doc=os.path.join(tmp,"word","document.xml")
    xml=open(doc,encoding="utf-8").read()
    missed=[]

    def find_para(anchor):
        for m in re.finditer(r'<w:p\b.*?</w:p>', xml, re.S):
            seg=m.group(0)
            t=' '.join(re.findall(r'<w:t[^>]*>(.*?)</w:t>', seg, re.S)).strip()
            t=re.sub(r'\s+',' ',t).replace('&amp;','&')
            if t==anchor: return m
        return None

    # process replaces first (they don't shift as much), then adds
    for c in [c for c in changes if c.get("mode")=="replace"]:
        m=find_para(c["find"])
        if not m: missed.append(c["find"]); continue
        seg=m.group(0)
        # replace the paragraph's text runs with the new text in the FIRST run,
        # blanking any extra runs so formatting of the bullet stays intact
        new_seg=re.sub(r"(<w:t[^>]*>).*?(</w:t>)","\\1"+xml_escape(c["text"])+"\\2",seg,count=1,flags=re.S)
        # blank subsequent <w:t> runs in same paragraph (so old text remnants vanish)
        first=True
        def blanker(mo):
            nonlocal first
            if first: first=False; return mo.group(0)
            return mo.group(1)+mo.group(2)
        new_seg=re.sub(r"(<w:t[^>]*>).*?(</w:t>)",blanker,new_seg,flags=re.S)
        xml=xml[:m.start()]+new_seg+xml[m.end():]

    for c in [c for c in changes if c.get("mode")=="add"]:
        m=find_para(c["anchor"])
        if not m: missed.append(c["anchor"]); continue
        template=m.group(0)
        newp=re.sub(r"(<w:t[^>]*>).*?(</w:t>)","\\1"+xml_escape(c["text"])+"\\2",template,count=1,flags=re.S)
        # blank extra runs in the clone too
        first=True
        def blk(mo):
            nonlocal first
            if first: first=False; return mo.group(0)
            return mo.group(1)+mo.group(2)
        newp=re.sub(r"(<w:t[^>]*>).*?(</w:t>)",blk,newp,flags=re.S)
        xml=xml[:m.end()]+newp+xml[m.end():]

    open(doc,"w",encoding="utf-8").write(xml)
    if os.path.exists(out_path): os.remove(out_path)
    with zipfile.ZipFile(out_path,"w",zipfile.ZIP_DEFLATED) as z:
        for root,_,files in os.walk(tmp):
            for f in files:
                fp=os.path.join(root,f); z.write(fp,os.path.relpath(fp,tmp))
    shutil.rmtree(tmp)
    return missed
