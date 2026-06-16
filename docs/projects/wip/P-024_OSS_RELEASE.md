# P-024 — OSS Release

**Status**: TODO  
**Priority**: Medium  
**Created**: March 2026  
**Updated**: June 2026

---

## Goal

Publish the code as a public GitHub repository — for self-hosting therapists/Heilpraktiker
in the DACH region who are comfortable with Python/Docker. Beta quality, no support
promises, no monetisation plan.

Everything beyond the bare publication (first-run wizard, VPS Docker setup, CI, governance)
goes into a separate follow-up project.

---

## What's Already Done

- ✅ `import_session_odt` management command + `odt_to_json.py` removed (June 2026) — incomplete, ODT-format specific, no OSS value; P-029 updated
- ✅ `odfpy` dependency removed from `requirements.txt` (June 2026)
- ✅ GLS bank references neutralised in UI strings, model docstring, and import form help text (June 2026)
- ✅ Replace-me warnings added to `treatment_contract_pdf.html` and `CHECKLIST_ITEMS` (June 2026)
- ✅ Customization audit written — see §7 below (June 2026)
- ✅ `SessionHistory` decision: remove from orphan branch only — private `main` keeps model + data intact; public repo never sees it (June 2026)
- ✅ Personal tasks (P-010/P-011) removed from public TODO.md → moved to `memory/PERSONAL_TODO.md` (June 2026)
- ✅ `REINSTALL_CHECKLIST.md` gitignored — personal installation record, not for public repo (June 2026)
- ✅ Personal doc location pattern documented: `memory/PUBLISH_STEPS.md` + `MY_PRACTICE_DATA_DIR/docs/` for filled-in operational docs (June 2026)
- ✅ `practice.py` model defaults: real IBAN, tax number, name, address, email removed (April 2026)
- ✅ Migration `0005_practice.py`: same defaults cleaned up
- ✅ Working tree: `gitleaks`-equivalent manual scan — no PII in model data, docs, templates
- ✅ `README.md`: no personal stats, tech stack updated
- ✅ Docs structure: `operations/`, `notes/`, `guides/` — no personal operational data in user-facing docs
- ✅ Tests: all 6 failing tests fixed (UserPractice + Session + NOT NULL constraint)

---

## Still To Do

### 1. Final PII Scan ✅ Done (June 2026)

- [x] Run `gitleaks detect --source . --no-git` — 3 hits, all in `.env` (gitignored, won't be in orphan)
- [x] Check invoice-prefix references in docs/comments — found `JL-5` placeholder → fixed to `XX-5`
- [x] Scan `git log --all --oneline` for real names in commit messages — clean, no client names
- [x] Deleted `app/my_practice/management/commands/archive/` (compare_2022/2024/2025 had real client codes)
- [x] Deleted `scripts/archive/` (practice-specific reconciliation scripts, no OSS value)
- [x] **Deleted `docs/archive/`** — all 16 files were stale planning/analysis docs referencing removed code; live patterns are covered by `CODE_STRUCTURE.md` and `CODEBASE_STANDARDS.md`

### 2. Squash Migrations ✅ Done (June 2026)

- [x] Deleted all 87 migration files, regenerated clean `0001_initial.py` from current models
- [x] No personal data in migration defaults (Practice model defaults cleaned April 2026)
- [x] `migrate --fake-initial` on dev DB — consistent, 0 pending migrations, system check clean
- [x] Full test suite passes (945 tests)

### 3. License ✅ Done

- [x] Create `LICENSE` file: AGPL-3.0

### 4. DPIA ✅ Done (June 2026)

- [x] Created `docs/operations/DPIA-template.md` — reusable template with `[PLACEHOLDER]` sections and guidance notes
- [x] `docs/operations/DPIA.md` (personal) added to `.gitignore` and untracked — keep locally, fill from template

### 5. Audit `.env.example` ✅ Done (June 2026)

- [x] All variables documented with inline comments
- [x] No real values — all placeholders (`GENERATE_A_KEY_AND_PUT_IT_HERE`, `CHANGE_THIS_TO_A_STRONG_PASSWORD`, etc.)
- [x] `SECRET_KEY` and `FERNET_KEY` have generation one-liners

### 6. Docs cleanup ✅ Done (June 2026)

- [x] P-010 personal operational doc moved to `memory/` (gitignored); slim done-stub created
- [x] P-011 personal operational doc moved to `memory/` (gitignored); slim done-stub created
- [x] P-009 trimmed to implemented state + open items only
- [x] `docs/guides/EMERGENCY_ACCESS_PLANNING.md` — framework guide for OSS adopters
- [x] `docs/guides/CLINICAL_DATA_SECURITY.md` — encryption model + GDPR obligations guide
- [x] `docs/README.md` — broken links fixed, new guides listed
- [x] Stale German analysis snapshots in `docs/notes/` deleted
- [x] `docs/notes/TYPE_CHECKING_NOTES.md` rewritten in English

### 7. Orphan Commit & GitHub Repo (1h)

The safe approach: no git filter-repo, no history-rewrite risk. Dev history stays private.

```bash
# Cut a clean starting point
git checkout --orphan public
git add -A
git commit -m "Initial public release"

# Create new GitHub repo and push
gh repo create <org>/<name> --public
git push -u origin public:main
```

- [x] Repo name decided: `dholbach/my-practice` (already renamed on GitHub)
- [x] README rewritten: motivation, pre-release disclaimer, status + limitations, screenshot placeholders (June 2026)
- [x] SessionHistory exported to CSV ($MY_PRACTICE_DATA_DIR/documents/) and removed from codebase (June 2026)
- [x] Full content review completed — `git grep` clean, docs gitignored where personal (June 2026)
- [x] Add screenshots to `docs/screenshots/` (5 views with seed data — June 2026)
- [ ] Create repo + push orphan branch (see `memory/PUBLISH_STEPS.md` for step-by-step)
- [ ] Set topics/description on GitHub

### 7. Customization Audit — What OSS Adopters Must Configure

The items below are currently hardcoded for one practice. Each needs a disposition
before the public release: **remove**, **make configurable**, or **document as example
that must be replaced**.

#### ❌ Remove on orphan branch before publish

| Item | Location | Reason |
| ---- | -------- | ------ |
| `import_session_odt` + `odt_to_json.py` | deleted June 2026 (private main too) | Incomplete, ODT-format-specific |
| `SessionHistory` model + admin | `models/session.py`, `admin.py`, `SHOW_SESSION_HISTORY` env flag | Legacy import scaffold; no new install will ever have this data. Private `main` keeps it — remove only from the orphan snapshot and exclude from squashed migration. |

#### 📄 Document as "replace with your own" (content is practice-specific)

| Item | Location | What to do |
| ---- | -------- | ---------- |
| Treatment contract PDF | `templates/my_practice/treatment_contract_pdf.html` | Contains DE-specific legal clauses (§ Heilpraktiker, GebüH, cancellation policy, DSGVO). Framework is reusable; **content must be replaced** by each adopter. Add a prominent comment at the top of the template and a note in the README. |
| Contract email template | `templates/my_practice/send_contract_email.html` | Accompanies the contract — same issue. Less critical since the email body is short and obviously needs to be read before sending. |
| Backup checklist items | `views/operational_views.py` → `CHECKLIST_ITEMS` | NAS, USB, MicroSD rotation steps match one specific LUKS/Yubikey setup. The checklist *engine* (completion tracking, pausing, dashboard widget) is fully reusable. Add a comment block explaining that items must be adapted, and link to the backup guide. |

#### 🔧 Needs generalization or configuration

| Item | Location | Proposed fix |
| ---- | -------- | ------------ |
| GLS Bank CSV format | `utils/bank_import.py` (delimiter `;`, GLS column names), `import_forms.py` help text | Short-term: document that only GLS format is supported, remove "GLS Bank" from UI strings. Long-term: make delimiter + column mapping configurable in `Practice` settings so other banks can be added without code changes. |
| `DURATION_TO_SERVICE_CODE` mapping | `utils/google_calendar.py` | Maps calendar event durations to German therapy service type codes (`therapy_15`, `therapy_60`, etc.). These codes are seeded per-practice via `seed_sample_data` / admin, so the mapping should be user-configurable (e.g. stored on `ServiceType` with a `duration_range_min`/`max` field) rather than hardcoded in Python. |
| `berlin_public_holidays()` | `utils/practice_days.py` | Straightforward to generalize: add a `country`/`state` setting to `Practice` and look up the right holiday set. Or document as Berlin-specific and let adopters override. |
| Session duration assumptions | `seed_sample_data.py`, service type seeding | 50/90-min therapy sessions are the default seed. Fine as example data; document that service types need to be configured via admin for a real install. |

#### ✅ Already configurable — no action needed

| Item | How |
| ---- | --- |
| Practice name, address, IBAN, bank details | `Practice` model fields, set via `setup_practice` wizard |
| Hourly rates per client | `Client.hourly_rate` |
| Email templates (payment reminder, contract cover letter) | Stored in DB via `Practice`; editable in settings UI |
| Logo, signature image | `Practice.logo` / `Practice.signature` file fields |
| Tax settings (USt, Kleinunternehmer) | `Practice.tax_rate` / `is_kleinunternehmer` |

---

## Out of Scope for P-024

Goes into a follow-up project (P-025 or similar):

- First-run wizard / `setup_practice` management command
- `docker-compose.prod.yml` for VPS (Caddy, HTTPS, health-check)
- GitHub Actions CI (ruff + pytest, Docker image build on GHCR)
- `CONTRIBUTING.md`, issue templates, GitHub org, semver release process
- OSS governance (discussions, responsible-disclosure policy)

---

## Open Questions

- **Repo name**: must be decided before step 5
- **CalDAV** as an alternative to Google Calendar — would significantly broaden the target audience (separate TODO)
- **FinTS/HBCI** instead of manual CSV import — a frequent pain point (separate TODO)
- **Update strategy**: how do self-hosting users stay on an up-to-date version? Options include: `git pull` + `./dev.py restart` instructions in README, GitHub release tags with a changelog, a `UPGRADING.md` with per-release migration notes, or an in-app version check. The answer probably goes into the P-025 follow-up (ops/CI), but the user-facing update story should be decided before the initial release so the README sets correct expectations.
