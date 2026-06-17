# Getting Started

Two paths depending on how you want to run the app:

| | Image-based | Source-based |
|---|---|---|
| **Best for** | Self-hosters who want stable releases | Developers, contributors, or anyone who wants to run from main |
| **Requirements** | Docker + Compose plugin | Docker + Compose plugin + Git + Python 3 |
| **Upgrades** | `docker compose pull` | `git pull` + `./dev.py restart --force` |

---

## Image-based setup (recommended for self-hosters)

### 1 — Get the compose file

If you don't have the repository cloned, download just the compose file:

```bash
curl -O https://raw.githubusercontent.com/dholbach/my-practice/main/docker-compose.prod.yml
```

Or if you already have a clone: `cd my-practice` — the file is there.

### 2 — Create your `.env`

The three required secrets — the app refuses to start without them:

```bash
cat > .env <<'EOF'
DJANGO_SECRET_KEY=
POSTGRES_PASSWORD=
FERNET_KEY=
EOF
```

Fill them in — generate each value with:

```bash
# DJANGO_SECRET_KEY
python3 -c "import secrets; print(secrets.token_urlsafe(50))"

# POSTGRES_PASSWORD — any strong password
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# FERNET_KEY — must be this exact format
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

> `FERNET_KEY` encrypts clinical notes at rest (Art. 9 GDPR data). Keep a copy somewhere safe — losing it means losing access to encrypted content.

### 3 — Pull and start

```bash
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d --remove-orphans
```

Migrations run automatically on first start. Wait a few seconds for Django to come up.

### 4 — Create a login

```bash
docker compose -f docker-compose.prod.yml exec django python manage.py createsuperuser
```

### 5 — Set up your practice

```bash
docker compose -f docker-compose.prod.yml exec django python manage.py setup_practice
```

This prompts for your name, address, bank details, and tax status, then creates the practice and links it to your account.

### 6 — Open the app

Go to **http://localhost:8000** and log in.

### Useful commands

```bash
# Follow logs
docker compose -f docker-compose.prod.yml logs -f django

# Run any management command
docker compose -f docker-compose.prod.yml exec django python manage.py <command>

# Upgrade to a new release
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
```

---

## Source-based setup (for developers and contributors)

This guide walks you through running the system for the first time — from zero to a
fully-populated demo practice you can click through and explore.

**Requirements**: Docker with the Compose plugin, Git, Python 3 (for `dev.py`).

---

## 1 — Get the code

```bash
git clone https://github.com/dholbach/my-practice.git
cd my-practice
```

---

## 2 — Start the containers

```bash
./dev.py start --build
```

This builds the Django image, starts PostgreSQL, runs all migrations, and serves
the app at **http://localhost:8000**. The `--build` flag ensures a fresh image with
all current dependencies. The command waits until Django is ready before returning,
so the next steps will work immediately.

> No `.env` needed for a demo run — `docker-compose.yml` has safe defaults
> (insecure dev secret key, `changeme123` DB password). Set up a real `.env`
> before using this with actual client data; see `.env.example` for every option.

---

## 3 — Create a login

```bash
./dev.py manage createsuperuser
```

Pick any username, email, and password. This will be your login for the web UI
and the Django admin.

---

## 4 — Load demo data

```bash
./dev.py manage seed_sample_data
```

This creates a fictional practice called **"Anna Schmidt — Heilpraktikerin für Psychotherapie"**
and populates it with 45 clients drawn from Tolkien, Ursula K. Le Guin, and Greek mythology,
plus ~900 sessions, ~340 invoices, recurring expenses, open inquiries, and a todo list.

Your superuser account is automatically assigned to the demo practice — no admin step needed.

Sample output:

```
🌱 Seeding demo data...
  ✓ Created practice: Anna Schmidt
  ✓ Assigned 1 superuser(s) to demo practice
  ✓ Created 45 clients
  ✓ Created 902 sessions
  ✓ Created 338 invoices
  ✓ Created 8 inquiries
  ✓ Created 6 todos
  ✓ Created 93 expenses (0 already existed)
✅ Seeded: 45 clients, 902 sessions, 338 invoices, 8 inquiries, 6 todos, expenses
```

---

## 5 — Open the app

Go to **http://localhost:8000** and log in with the credentials you just created.

You'll land on the **dashboard** showing the demo practice — revenue chart for the
last 12 months, today's agenda, active client list, and a weekly focus widget.

---

## What to explore

### Dashboard

The dashboard is the daily starting point. It shows:

- **Heute & Diese Woche** — today's agenda (sessions from the calendar) + this week's sessions
- **Revenue chart** — last 12 months, paid vs. sent vs. draft
- **Fokus-Aufgaben** — starred to-do items pinned for the week
- **Steuer-Quartal** — a running tax-quarter overview (Einnahmen-Überschussrechnung)

Switch to **Privacy mode** (toggle in the top bar) to blur client names — useful when
working in a shared space.

### Client list (`/clients/`)

Clients are grouped into three buckets:

- **⚠️ Needs Attention** — clients with system tags like `missing-session-log`,
  `incomplete-intake`, or `no-next-session`
- **✅ Active** — regular clients with recent sessions
- **💤 Inactive** — archived or paused clients

Click any client to see their full record: session history, revenue, clinical
protocol tab, tags, and document uploads.

### Invoices (`/invoices/`)

The invoice list shows all drafts, sent, and paid invoices. Open one to see the
line items (session date, duration, rate). From the detail view you can:

- **Download PDF** — bilingual DE/EN invoice, ready to send
- **Send by email** — if email is configured (see `.env.example`)
- **Mark as paid** — records the payment date

The demo has invoices in all four states (Draft / Sent / Paid / Cancelled),
so you can see what each looks like.

### Batch invoicing (`/invoices/batch/`)

At the end of a billing period, use batch invoicing to create drafts for all
clients with unbilled sessions in one go. Select the month, review the cards
(one per client), and click **Erstellen** — done.

### Analytics (`/analytics/`)

The analytics dashboard has three tabs:

- **Übersicht** — revenue vs. expenses vs. withdrawals, top clients by revenue,
  profit trend
- **Kapazität** — session capacity utilisation, cancellation rate trend, target
  hours vs. actual (holiday-aware, Berlin public holidays)
- **Zeit** — year-over-year revenue comparison, busiest months, session type
  distribution

Use the time-period filter at the top to zoom into a quarter or custom date range.

### Inquiry pipeline (`/inquiries/`)

Tracks potential new clients from first contact through to accepted or declined.
The demo has 8 fictional inquiries at various stages, so the funnel view is
populated.

---

## Reset and re-seed

If you want a fresh start:

```bash
./dev.py manage seed_sample_data --clear
./dev.py manage seed_sample_data
```

`--clear` removes all seeded data (identified by the fictional names — real client
data in other practices is never touched). Re-running without `--clear` is
idempotent: it does nothing if demo data already exists.

---

## Moving to real use

When you're ready to use this for an actual practice:

1. **Copy `.env.example` to `.env`** and fill in:
   - `DJANGO_SECRET_KEY` — generate with the one-liner in the file
   - `FERNET_KEY` — required for encrypted clinical notes (Art. 9 DSGVO data)
   - `POSTGRES_PASSWORD` — use a strong password
   - `MY_PRACTICE_DATA_DIR` — an absolute path outside the repo for backups and media

2. **Restart** to load the new environment:

   ```bash
   ./dev.py restart --force
   ```

3. **Create your practice** with the setup wizard:

   ```bash
   ./dev.py manage setup_practice
   ```

   This prompts for your name, address, bank details, and tax status, then
   creates the practice and links it to your account. Logo, signature, and
   email templates can be added afterwards in the admin.

4. **Clear demo data** once you no longer need it:

   ```bash
   ./dev.py manage seed_sample_data --clear
   ```

5. Set up **backups** before adding real data — see [BACKUP_SETUP.md](BACKUP_SETUP.md).

---

## Stopping and restarting

```bash
./dev.py start          # start containers
./dev.py restart        # restart Django (picks up code changes)
./dev.py restart --force  # full down/up (reloads .env)
./dev.py logs -f        # tail logs
```

Data lives in Docker volumes (`postgres_data`) and the `MY_PRACTICE_DATA_DIR`
directory, so it survives restarts.

---

## Troubleshooting

**`ModuleNotFoundError: No module named 'nh3'` (or any missing package)**

The running container was built from a cached image that predates a dependency
update. Force a rebuild:

```bash
./dev.py start --build
```

**Container starts but app is unreachable at localhost:8000**

Check the logs for startup errors:

```bash
./dev.py logs -f
```

**`WARN: "FOO_VAR" variable is not set`**

Warnings about `EMAIL_HOST_USER`, `FERNET_KEY`, etc. are expected on a demo run
— those features are disabled when the vars are absent. Set them in `.env` only
when you need email sending or encrypted clinical notes.
