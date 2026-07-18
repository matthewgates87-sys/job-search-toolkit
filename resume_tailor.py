#!/usr/bin/env python3
"""
resume_tailor.py — Bullet formatter with REPLACE or ADD
-------------------------------------------------------
Paste bullets your Resume Tailoring chat wrote. For each, choose to either
REPLACE one of your resume's existing bullets (so the resume stays the same
length and actually gets tailored) or ADD it as a new bullet. Formatting is
always preserved.

Config-driven: reads config.json (run setup.py first).
RUN:  python resume_tailor.py   |   Stop: Ctrl+C
"""
import http.server, socketserver, json, os, re, datetime, webbrowser, threading
import resume_engine as eng

PORT=8757
CONFIG="config.json"

def load_config():
    if not os.path.exists(CONFIG): return None
    return json.load(open(CONFIG,encoding="utf-8"))

def get_roles(cfg):
    resume=cfg.get("resume_file","master.docx")
    if not os.path.exists(resume): return [],resume
    try: return eng.list_bullets(resume),resume
    except Exception: return [],resume

class H(http.server.BaseHTTPRequestHandler):
    def log_message(self,*a): pass
    def _s(self,code,body,ctype="application/json",extra=None):
        self.send_response(code);self.send_header("Content-Type",ctype);self.send_header("Cache-Control","no-store")
        if extra:
            for k,v in extra.items(): self.send_header(k,v)
        self.end_headers()
        self.wfile.write(body if isinstance(body,bytes) else body.encode("utf-8"))
    def do_GET(self):
        if self.path=="/" or self.path.startswith("/?"): self._s(200,PAGE,"text/html");return
        if self.path=="/api/config":
            cfg=load_config()
            if not cfg: self._s(200,json.dumps({"ready":False,"reason":"no_config"}));return
            roles,resume=get_roles(cfg)
            self._s(200,json.dumps({"ready":os.path.exists(resume),"resume":resume,
                "name":cfg.get("name","You"),"roles":roles,
                "reason":"" if os.path.exists(resume) else "no_resume"}));return
        self._s(404,"{}")
    def do_POST(self):
        n=int(self.headers.get("Content-Length",0));body=json.loads(self.rfile.read(n) or "{}")
        if self.path=="/api/export":
            cfg=load_config()
            if not cfg: self._s(400,json.dumps({"error":"No config.json — run setup.py first."}));return
            roles,resume=get_roles(cfg)
            if not os.path.exists(resume): self._s(400,json.dumps({"error":f"Resume '{resume}' not found."}));return
            changes=body.get("changes",[])  # [{mode, text, find?, anchor?}]
            clean=[]
            for c in changes:
                t=(c.get("text") or "").strip()
                if not t: continue
                if c.get("mode")=="replace" and c.get("find"):
                    clean.append({"mode":"replace","find":c["find"],"text":t})
                elif c.get("mode")=="add" and c.get("anchor"):
                    clean.append({"mode":"add","anchor":c["anchor"],"text":t})
            if not clean: self._s(400,json.dumps({"error":"No changes to make."}));return
            name=cfg.get("name","Candidate")
            last=re.sub(r'[^A-Za-z0-9]+','-',name).strip('-').split('-')[-1].title() if name and name!="Your Name" else "Resume"
            title=re.sub(r'[^A-Za-z0-9]+','-',body.get("title","Role")).strip('-')[:30] or "Role"
            out=f"{last}_{title}_{datetime.date.today().isoformat()}.docx"
            try:
                missed=eng.apply_changes(resume,clean,out)
                data=open(out,"rb").read()
                extra={"Content-Disposition":f'attachment; filename="{out}"'}
                if missed: extra["X-Missed"]=str(len(missed))
                self._s(200,data,"application/vnd.openxmlformats-officedocument.wordprocessingml.document",extra)
            except Exception as e:
                self._s(500,json.dumps({"error":str(e)}))
            return
        self._s(404,"{}")

PAGE = r"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Resume Formatter</title>
<style>
:root{--ink:#14202e;--soft:#4a5a6a;--paper:#f7f5f0;--panel:#fff;--line:#dcd8cf;
--go:#1f6f5c;--go-s:#e4f0ec;--warn:#b5632a;--warn-s:#f6e9dd;--accent:#2d4a63;--rep:#3b4d8f;--rep-s:#e7ebf7;
--mono:ui-monospace,'Cascadia Code',Menlo,monospace;--sans:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;
--serif:'Iowan Old Style','Palatino Linotype',Georgia,serif;}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font-family:var(--sans);line-height:1.5}
.wrap{max-width:960px;margin:0 auto;padding:30px 22px 90px}
header{border-bottom:2px solid var(--ink);padding-bottom:14px;margin-bottom:8px;display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:10px}
h1{font-family:var(--serif);font-size:28px;margin:0}h1 span{color:var(--go)}
.who{font-family:var(--mono);font-size:11px;text-transform:uppercase;letter-spacing:.1em;color:var(--soft)}
.lede{color:var(--soft);font-size:14.5px;max-width:700px;margin:14px 0 18px}
.masterbar{border-radius:9px;padding:10px 14px;font-size:13px;margin-bottom:18px;font-family:var(--mono)}
.masterbar.ok{background:var(--go-s);color:#195a4b}.masterbar.no{background:var(--warn-s);color:#7a4318}
.field{margin:12px 0}.field label{display:block;font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:.05em;color:var(--soft);margin-bottom:6px}
.field input{width:100%;padding:11px 13px;border:1px solid var(--line);border-radius:8px;font-size:14px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:15px 16px;margin:13px 0}
.card .hd{display:flex;justify-content:space-between;gap:10px;align-items:flex-start}
.card textarea{width:100%;min-height:52px;border:1px solid var(--line);border-radius:8px;padding:10px 12px;font-family:var(--sans);font-size:14px;line-height:1.5;resize:vertical;background:#fbfaf7}
.card textarea:focus{background:#fff;outline:none;border-color:var(--accent)}
.rm{background:none;border:none;color:var(--soft);font-size:18px;cursor:pointer;padding:4px}
.rm:hover{color:var(--warn)}
.modebar{display:flex;gap:8px;margin:11px 0 8px;flex-wrap:wrap;align-items:center}
.seg{display:inline-flex;border:1px solid var(--line);border-radius:8px;overflow:hidden}
.seg button{border:none;background:#fff;padding:7px 14px;font-size:13px;font-weight:600;cursor:pointer;color:var(--soft)}
.seg button.on{background:var(--rep);color:#fff}
.seg button.on.addmode{background:var(--go)}
select{font-size:13px;padding:8px 10px;border:1px solid var(--line);border-radius:8px;background:#fff;max-width:100%}
.rolepick{font-size:13px}
.replacepick{width:100%;margin-top:4px}
.pickwrap{margin-top:6px}
.pickwrap label{font-size:11px;color:var(--soft);text-transform:uppercase;letter-spacing:.05em;display:block;margin-bottom:4px}
.preview{margin-top:10px;font-size:13px;border-radius:8px;padding:9px 12px;background:#f4f5f8}
.preview .old{color:var(--warn);text-decoration:line-through;opacity:.7}
.preview .new{color:var(--go);font-weight:500}
.preview .arrow{color:var(--soft);margin:0 6px}
.addbtn{background:#fff;border:1px dashed var(--line);color:var(--soft);border-radius:9px;padding:12px;width:100%;font-size:14px;cursor:pointer;margin-top:6px}
.addbtn:hover{border-color:var(--accent);color:var(--accent)}
.foot{position:sticky;bottom:0;background:linear-gradient(transparent,var(--paper) 30%);padding:20px 0 4px;margin-top:22px;display:flex;gap:14px;align-items:center;flex-wrap:wrap}
.count{font-size:13px;color:var(--soft);margin-right:auto}
.btn{border:none;border-radius:8px;font-size:15px;font-weight:600;cursor:pointer;padding:13px 26px}
.btn.export{background:var(--go);color:#fff}.btn.export:disabled{background:#c3ccc8;cursor:not-allowed}
.hint{font-size:12.5px;color:var(--soft);background:#fbfaf7;border-left:3px solid var(--line);padding:10px 14px;border-radius:6px;margin:6px 0 16px}
.toast{position:fixed;bottom:22px;left:50%;transform:translateX(-50%) translateY(20px);opacity:0;background:var(--ink);color:#fff;padding:11px 18px;border-radius:10px;font-size:14px;transition:.25s;z-index:20;pointer-events:none}
.toast.show{opacity:1;transform:translateX(-50%) translateY(0)}
.disc{margin-top:24px;font-size:12px;color:var(--soft);border-top:1px solid var(--line);padding-top:14px}
</style></head><body><div class="wrap">
<header><h1>Resume <span>Formatter</span></h1><div class="who" id="who">replace · add · export</div></header>
<p class="lede">Paste each tailored bullet, then choose whether it <b>replaces</b> one of your existing bullets (keeps your resume the same length and actually tailors it) or gets <b>added</b> as new. Formatting is always preserved.</p>
<div id="masterbar" class="masterbar">checking…</div>
<div class="field"><label>Job title (for the filename)</label><input id="title" placeholder="e.g. Company — Role Title"></div>
<p class="hint">Default is <b>Replace</b> — pick which original bullet each tailored line swaps out. Switch a card to <b>Add</b> only when the bullet is genuinely new and shouldn't replace anything.</p>
<div id="cards"></div>
<button class="addbtn" id="addBtn">+ Add another tailored bullet</button>
<div class="foot">
  <span class="count" id="count">0 changes</span>
  <button class="btn export" id="exportBtn" disabled>Download tailored resume</button>
</div>
<p class="disc">Runs locally — your resume never leaves your computer. Replaced bullets are swapped in place; added bullets go under the chosen role. Always give it a final read before sending.</p>
</div>
<div class="toast" id="toast"></div>
<script>
let ROLES=[],cards=[];
function toast(m){const t=document.getElementById('toast');t.textContent=m;t.classList.add('show');setTimeout(()=>t.classList.remove('show'),2300);}
async function boot(){
  const cfg=await (await fetch('/api/config')).json();
  const bar=document.getElementById('masterbar');
  if(!cfg.ready){bar.className='masterbar no';
    bar.textContent=cfg.reason==='no_config'?'⚠ No config.json. Run  python setup.py  first, then refresh.':'⚠ Resume file not found. Check config.json, then refresh.';return;}
  ROLES=cfg.roles;document.getElementById('who').textContent=(cfg.name||'You')+' · replace · add · export';
  if(!ROLES.length){bar.className='masterbar no';bar.textContent='⚠ No experience sections detected in your resume.';}
  else{const nb=ROLES.reduce((s,r)=>s+r.bullets.length,0);bar.className='masterbar ok';bar.textContent='✓ '+cfg.resume+' — '+ROLES.length+' roles, '+nb+' existing bullets ready to swap.';}
  addCard();
}
function addCard(){cards.push({id:Date.now()+Math.random(),text:"",mode:"replace",roleIndex:0,findIndex:0});paint();}
function removeCard(id){cards=cards.filter(c=>c.id!==id);if(!cards.length)addCard();else paint();}
function bulletOptions(roleIdx,sel){
  const bs=(ROLES[roleIdx]||{bullets:[]}).bullets;
  return bs.map((b,i)=>`<option value="${i}" ${i===sel?'selected':''}>${(b.text.length>70?b.text.slice(0,70)+'…':b.text).replace(/"/g,'&quot;')}</option>`).join('');
}
function roleOptions(sel){return ROLES.map((r,i)=>`<option value="${i}" ${i===sel?'selected':''}>${r.label.length>44?r.label.slice(0,44)+'…':r.label}</option>`).join('');}
function paint(){
  const wrap=document.getElementById('cards');
  wrap.innerHTML=cards.map((c,idx)=>{
    const role=ROLES[c.roleIndex]||{bullets:[]};
    const orig=(role.bullets[c.findIndex]||{}).text||'';
    const isRep=c.mode==='replace';
    return `<div class="card">
      <div class="hd">
        <div style="flex:1"><label style="font-size:11px;color:var(--soft);text-transform:uppercase;letter-spacing:.05em">Tailored bullet ${idx+1}</label>
        <textarea oninput="setText(${c.id},this.value)" placeholder="Paste the tailored bullet here…">${c.text.replace(/</g,'&lt;')}</textarea></div>
        <button class="rm" onclick="removeCard(${c.id})" title="Remove">✕</button>
      </div>
      <div class="modebar">
        <div class="seg">
          <button class="${isRep?'on':''}" onclick="setMode(${c.id},'replace')">Replace</button>
          <button class="${!isRep?'on addmode':''}" onclick="setMode(${c.id},'add')">Add new</button>
        </div>
        <span class="rolepick"><label style="font-size:11px;color:var(--soft)">Role: </label>
          <select onchange="setRole(${c.id},+this.value)">${roleOptions(c.roleIndex)}</select></span>
      </div>
      ${isRep?`<div class="pickwrap"><label>Which existing bullet does this replace?</label>
        <select class="replacepick" onchange="setFind(${c.id},+this.value)">${bulletOptions(c.roleIndex,c.findIndex)}</select>
        ${c.text.trim()?`<div class="preview"><span class="old">${orig.replace(/</g,'&lt;')}</span><span class="arrow">→</span><span class="new">${c.text.replace(/</g,'&lt;')}</span></div>`:''}
      </div>`:`<div class="pickwrap"><div class="preview"><span class="new">+ ${c.text.replace(/</g,'&lt;')||'(new bullet)'}</span> <span style="color:var(--soft)">— added under ${role.label.slice(0,40)}</span></div></div>`}
    </div>`;
  }).join('');
  const n=cards.filter(c=>c.text.trim()).length;
  document.getElementById('count').textContent=n+' change'+(n===1?'':'s');
  document.getElementById('exportBtn').disabled=n===0||!ROLES.length;
}
function setText(id,v){const c=cards.find(x=>x.id===id);if(c)c.text=v;paint();}
function setMode(id,m){const c=cards.find(x=>x.id===id);if(c)c.mode=m;paint();}
function setRole(id,v){const c=cards.find(x=>x.id===id);if(c){c.roleIndex=v;c.findIndex=0;}paint();}
function setFind(id,v){const c=cards.find(x=>x.id===id);if(c)c.findIndex=v;paint();}
document.getElementById('addBtn').onclick=addCard;
document.getElementById('exportBtn').onclick=async()=>{
  const changes=cards.filter(c=>c.text.trim()).map(c=>{
    const role=ROLES[c.roleIndex]||{bullets:[]};
    if(c.mode==='replace'){const orig=(role.bullets[c.findIndex]||{}).text||'';return {mode:'replace',find:orig,text:c.text.trim()};}
    const anchor=(role.bullets[role.bullets.length-1]||{}).text||'';return {mode:'add',anchor,text:c.text.trim()};
  });
  if(!changes.length){toast('Add at least one bullet');return;}
  const title=document.getElementById('title').value.trim()||'Role';
  const r=await fetch('/api/export',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({changes,title})});
  if(!r.ok){const e=await r.json();toast('Export error: '+(e.error||'unknown'));return;}
  const blob=await r.blob();const cd=r.headers.get('Content-Disposition')||'';
  const name=(cd.match(/filename="(.+?)"/)||[])[1]||'tailored_resume.docx';
  const missed=r.headers.get('X-Missed');
  const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=name;document.body.appendChild(a);a.click();
  setTimeout(()=>{URL.revokeObjectURL(a.href);a.remove();},400);
  toast(missed?('Downloaded — '+missed+' change(s) couldn\'t be applied'):'Downloaded '+name+' — read it before sending');
};
boot();
</script></body></html>"""

def open_browser(): webbrowser.open(f"http://localhost:{PORT}")
if __name__=="__main__":
    cfg=load_config()
    print("\n  Resume Formatter running.")
    print(f"  -> http://localhost:{PORT} (browser opens automatically)")
    if not cfg: print("  !! No config.json — run  python setup.py  first.")
    print("  -> Stop: Ctrl+C\n")
    threading.Timer(0.8,open_browser).start()
    socketserver.TCPServer.allow_reuse_address=True
    with socketserver.TCPServer(("127.0.0.1",PORT),H) as httpd:
        try: httpd.serve_forever()
        except KeyboardInterrupt: print("\n  Stopped.\n")
