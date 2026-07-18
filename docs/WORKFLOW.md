# Daily Workflow

The full loop, start to finish. Once set up, a cycle takes about 20 minutes of pasting plus however long you spend actually applying.

---

## One-time setup

**1. Files in one folder** — clone the repo, then add:
- `master.docx` — your resume
- Resume variants (optional but recommended): one per role archetype you target

**2. Run setup**
```bash
python setup.py
```

**3. Add API keys** to `config.json` — see the README table for where to get them.

**4. Create two Claude Projects:**
- **"Job Triage"** — paste in `prompts/Job_Triage_Instructions.txt` (everything below the ►►► line)
- **"Resume Tailoring"** — paste in `prompts/Resume_Tailoring_Instructions.txt` (same)

Edit both prompts to contain *your* work history, not the example.

**5. Verify**
```bash
python diagnose.py
```
You want green across your APIs. Dead company slugs are normal — prune them with `python expand_companies.py`.

---

## The loop

### 1 · Pull
```bash
python job_hub.py
```
Hit **↻ Refresh roles**. Several minutes — it queries every API and board, then reads each posting to detect work-type. Roles outside your radius or non-remote-US are discarded at this stage.

`Ctrl+C` when it's done.

### 2 · Export for triage
```bash
python export_jds.py --per-batch 50 --min-fit 50
```
Creates `review_batch_1.txt`, `_2.txt`, etc.

Flags:
- `--per-batch N` — jobs per file. 50 is a good balance; higher risks sloppier verdicts.
- `--min-fit N` — skip roles below N% keyword fit. Crude, but trims the batch count.

### 3 · Triage
For each batch:
1. Open the file, copy everything
2. Paste into a new chat in your **Job Triage** Project
3. Copy the entire reply
4. Append it to `verdicts.txt` (create the file if it doesn't exist)

Claude returns one line per job:
```
f6268c57 | APPLY | Strong AE fit, Glendale hybrid, ROI-led enterprise sale
1e77c057 | SKIP  | Entry-level SDR, far below your level
```

### 4 · Import
```bash
python import_verdicts.py
```
Prints your APPLY / MAYBE / SKIP counts.

### 5 · Work the list
```bash
python job_hub.py
```
Set **Reviewed → APPLY only**. These are the roles that survived judgment.

For each:
1. Click the title → read the actual posting
2. Copy the job description
3. Paste into a new chat in your **Resume Tailoring** Project

It returns: which resume variant to use, any red flags, a verdict, and tailored bullets formatted as:
```
REPLACE (Your Current Role) → "old bullet text"
WITH: "new tailored bullet"
```

### 6 · Tailor
In a second terminal:
```bash
python resume_tailor.py
```
- Paste each bullet
- Choose **Replace** and pick which original it swaps (keeps your resume the same length)
- Enter the job title for the filename
- **Download tailored resume**

### 7 · Apply + track
Back in Job Hub, click **Apply →** on the role:
- Confirms which variant to use
- Copies the filename to save your tailored resume as
- Opens the posting in a new tab
- Logs it to your Pipeline as **Applied**

Submit on the company's site.

### 8 · Manage
**Pipeline** tab → move stages as things progress. Set follow-up dates; overdue ones flag in red.

---

## Maintenance

```bash
python diagnose.py            # are APIs and boards healthy?
python expand_companies.py    # prune dead company slugs
```

To add companies, make a `candidates.txt`:
```
greenhouse,servicetitan
lever,whatnot
ashby,ramp
```
then:
```bash
python expand_companies.py candidates.txt
```
It only adds slugs that actually resolve.

---

## Ports

| Tool | Port |
|---|---|
| `job_hub.py` | 8756 |
| `resume_tailor.py` | 8757 |

They can run simultaneously in separate terminals.

---

## Files the tools create

| File | What |
|---|---|
| `config.json` | Your settings + API keys — **never commit this** |
| `found_roles.json` | Cached roles from the last pull |
| `applications.json` | Your pipeline |
| `verdicts.txt` | Claude's triage replies |
| `review_batch_*.txt` | Export batches |

All are gitignored.
