# Publishing this to GitHub

Steps to get this repo onto your GitHub profile.

## 1. Create the repo on GitHub

1. Go to [github.com/new](https://github.com/new)
2. Name it something clear: `job-search-toolkit`
3. Description: *"AI-assisted job search: multi-source discovery, Claude-powered triage, and formatting-preserving resume tailoring."*
4. **Public**
5. Do **not** initialize with a README (you already have one)
6. Create

## 2. Push from your machine

```bash
cd path/to/your/JobSearch-repo

git init
git add -A
git status          # ← IMPORTANT: verify config.json is NOT listed
git commit -m "Job search toolkit: multi-source discovery, AI triage, resume tailoring"
git branch -M main
git remote add origin https://github.com/YOURNAME/job-search-toolkit.git
git push -u origin main
```

## 3. Before you push — safety check

Run this and confirm every line says IGNORED:

```bash
git check-ignore -v config.json master.docx found_roles.json applications.json verdicts.txt
```

If `config.json` is not ignored, **stop** — it contains your API keys.

## 4. Polish the repo page

- **About** (right sidebar): add the description + topics: `python` `job-search` `claude` `ai` `automation` `resume`
- Pin it to your profile: profile → Customize your pins
- Add screenshots to `docs/` and reference them in the README — recruiters skim visuals first

## 5. If you ever commit a key by accident

Rotate it immediately at the provider — deleting the commit is not enough, it stays in history.
