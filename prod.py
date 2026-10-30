#!/usr/bin/env python3
"""prod.py — management helper for the my-practice production stack.

Requirements: Python 3, Docker with the Compose plugin.
"""

import glob
import gzip
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request

VERSION = "v0.10.0"  # updated each release — keeps prod.py and docker-compose.prod.yml in sync

COMPOSE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docker-compose.prod.yml")
COMPOSE = ["docker", "compose", "-f", COMPOSE_FILE]
IMAGE = f"ghcr.io/dholbach/my-practice:{VERSION}"
ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
ENV_DOCS = f"https://github.com/dholbach/my-practice/blob/{VERSION}/.env.example"
RELEASES_API = "https://api.github.com/repos/dholbach/my-practice/releases/latest"
RAW_BASE = f"https://raw.githubusercontent.com/dholbach/my-practice/{VERSION}"

# Without these the stack starts but cannot work: Postgres refuses to initialise
# with a blank password, and Django cannot sign sessions or read encrypted
# clinical notes. Compose only warns about them and carries on, so check first.
REQUIRED_SECRETS = ("DJANGO_SECRET_KEY", "POSTGRES_PASSWORD", "FERNET_KEY")

# The host address docker-compose.prod.yml publishes port 8000 on. Compose
# defaults it to loopback: plain HTTP on every interface sends passwords and
# client data across the network unencrypted, and behind a reverse proxy it lets
# a client skip the proxy and claim HTTPS through X-Forwarded-Proto. Docker's
# port publishing bypasses host firewalls such as ufw, so a firewall is no help.
BIND_ADDRESS_KEY = "MY_PRACTICE_BIND_ADDRESS"


def compose(*args):
    return subprocess.run([*COMPOSE, *args])


def exec_django(*args):
    tty = ["-it"] if sys.stdin.isatty() else ["-i"]
    return subprocess.run([*COMPOSE, "exec", *tty, "django", *args])


def manage(*args):
    return exec_django("python", "manage.py", *args)


def abort(msg):
    print(f"\nError: {msg}", file=sys.stderr)
    sys.exit(1)


def step(msg):
    print(f"\n── {msg}")


# This and _confirm_metered_download are duplicated verbatim in dev.py. prod.py
# ships to self-hosters as a single stdlib-only file, so it cannot import a
# shared module, and the copies must stay identical —
# scripts/check_shared_helpers.py fails if they drift.
def _is_metered_connection():
    """Best-effort NetworkManager check for a metered connection (e.g. mobile hotspot).

    Returns True/False when nmcli gives a definite answer, None when it can't be
    determined (no NetworkManager, no default route, non-Linux host, ...).
    Callers should treat None as "unknown" and not block on it.
    """
    if not shutil.which("nmcli"):
        return None
    try:
        route = subprocess.run(
            ["ip", "route", "show", "default"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        parts = route.stdout.split()
        device = parts[parts.index("dev") + 1] if "dev" in parts else None
        if not device:
            return None
        out = subprocess.run(
            ["nmcli", "-t", "-f", "GENERAL.METERED", "device", "show", device],
            capture_output=True,
            text=True,
            timeout=3,
        )
        value = out.stdout.strip().split(":", 1)[-1]
        return value.startswith("yes")
    except Exception:
        return None


def _confirm_metered_download(action):
    """Ask before a data-heavy operation if the active connection looks metered.

    Returns True if it's fine to proceed (not metered, unknown, or user confirmed).
    """
    if _is_metered_connection() is not True:
        return True
    print(
        f"⚠️  Active network connection is metered (e.g. mobile hotspot). {action} can pull a lot of data."
    )
    if not sys.stdin.isatty():
        print("   Not an interactive terminal — pass --yes to proceed anyway.")
        return False
    return input("   Continue anyway? [y/N] ").strip().lower() == "y"


# ── setup ────────────────────────────────────────────────────────────────────


def _check_docker():
    """Verify Docker and the Compose plugin are available."""
    if subprocess.run(["docker", "info"], capture_output=True).returncode != 0:
        abort(
            "Docker is not running or not installed.\n"
            "  Install Docker Desktop: https://docs.docker.com/get-docker/\n"
            "  Then start it and re-run ./prod.py setup"
        )
    if subprocess.run(["docker", "compose", "version"], capture_output=True).returncode != 0:
        abort(
            "The Docker Compose plugin is missing.\n"
            "  Docker Desktop includes it automatically.\n"
            "  On Linux without Desktop: apt install docker-compose-plugin  (Debian/Ubuntu)\n"
            "                            dnf install docker-compose-plugin  (Fedora/RHEL)"
        )


def _generate_fernet_key():
    """Generate a Fernet key using the already-pulled image (no host deps needed)."""
    result = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            IMAGE,
            "python",
            "-c",
            "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        abort(
            "Could not generate FERNET_KEY using the Docker image.\n"
            "  Make sure the image pulled successfully, then re-run ./prod.py setup\n"
            "  Or generate it manually:\n"
            "    pip install cryptography\n"
            '    python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"\n'
            "  and add it to .env as FERNET_KEY=<value>"
        )
    return result.stdout.strip()


def _read_env():
    """Return existing .env as a dict (empty dict if file doesn't exist)."""
    env = {}
    if not os.path.exists(ENV_FILE):
        return env
    with open(ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    return env


def _write_env(env: dict):
    """Write env dict to .env, preserving existing comments if file exists."""
    existing_lines = []
    existing_keys = set()
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE) as f:
            existing_lines = f.readlines()
        for line in existing_lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                existing_keys.add(stripped.split("=", 1)[0].strip())

    with open(ENV_FILE, "w") as f:
        # Rewrite existing file with updated values
        for line in existing_lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                k = stripped.split("=", 1)[0].strip()
                if k in env:
                    f.write(f"{k}={env[k]}\n")
                else:
                    f.write(line)
            else:
                f.write(line)
        # Append any new keys not already in the file
        for k, v in env.items():
            if k not in existing_keys:
                f.write(f"{k}={v}\n")


def _ensure_gitignore():
    """Add .env to .gitignore next to prod.py (create the file if needed)."""
    gitignore_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".gitignore")
    entry = ".env"
    if os.path.exists(gitignore_path):
        with open(gitignore_path) as f:
            existing = {line.strip() for line in f}
        if entry in existing:
            return False
        with open(gitignore_path, "a") as f:
            f.write(f"\n{entry}\n")
    else:
        with open(gitignore_path, "w") as f:
            f.write(f"{entry}\n")
    return True


def _wait_for_healthy(timeout=120):
    """Wait for the django container to become healthy."""
    print("  Waiting for Django to be ready", end="", flush=True)
    deadline = time.time() + timeout
    while time.time() < deadline:
        out = subprocess.run(
            [
                "docker",
                "inspect",
                "--format",
                "{{.State.Health.Status}}",
                "my-practice-django",
            ],
            capture_output=True,
            text=True,
        )
        status = out.stdout.strip()
        if status == "healthy":
            print(" ready.")
            return True
        if status == "unhealthy":
            print(" unhealthy.")
            return False
        print(".", end="", flush=True)
        time.sleep(3)
    print(" timed out.")
    return False


def cmd_setup(args):
    """First-time setup: generate secrets, pull image, start, create login.

    Pass --yes to skip the metered-connection prompt before the image pull.
    """
    print("my-practice setup")
    print("=" * 50)

    if "--yes" not in args and not _confirm_metered_download("Pulling the image"):
        abort("Aborted — pass --yes to ./prod.py setup to proceed anyway.")

    # 1. Preflight
    step("Checking Docker")
    _check_docker()
    print("  Docker OK")
    _require_no_foreign_containers()

    if not os.path.exists(COMPOSE_FILE):
        print("  docker-compose.prod.yml not found — downloading...")
        compose_url = f"{RAW_BASE}/docker-compose.prod.yml"
        try:
            with (
                urllib.request.urlopen(compose_url, timeout=10) as r,
                open(COMPOSE_FILE, "wb") as f,
            ):
                f.write(r.read())
            print(f"  Saved to {COMPOSE_FILE}")
        except Exception as e:
            abort(
                f"Could not download docker-compose.prod.yml: {e}\n"
                "  Download it manually:\n"
                "    curl -O https://raw.githubusercontent.com/dholbach/my-practice/main/docker-compose.prod.yml\n"
                "  then re-run ./prod.py setup"
            )

    # 2. Pull image (needed before we can generate the Fernet key inside it)
    step("Pulling image")
    result = subprocess.run(["docker", "pull", IMAGE])
    if result.returncode != 0:
        abort(
            "Could not pull the image from GHCR.\n"
            "  Check your internet connection and try again.\n"
            "  If the problem persists: https://github.com/dholbach/my-practice/issues"
        )

    # 3. Generate secrets (only for keys not already set)
    step("Generating secrets")
    env = _read_env()
    added = []

    if not env.get("DJANGO_SECRET_KEY"):
        env["DJANGO_SECRET_KEY"] = secrets.token_urlsafe(50)
        added.append("DJANGO_SECRET_KEY")

    if not env.get("POSTGRES_PASSWORD"):
        env["POSTGRES_PASSWORD"] = secrets.token_urlsafe(32)
        added.append("POSTGRES_PASSWORD")

    if not env.get("FERNET_KEY"):
        print("  Generating FERNET_KEY (uses the Docker image — takes a moment)...")
        env["FERNET_KEY"] = _generate_fernet_key()
        added.append("FERNET_KEY")

    if added:
        _write_env(env)
        print(f"  Generated and saved to .env: {', '.join(added)}")
    else:
        print("  All required secrets already present in .env — nothing changed.")

    if _ensure_gitignore():
        print("  Created .gitignore — .env will not be accidentally committed to Git.")

    print()
    print("  ⚠  Keep your .env safe — especially FERNET_KEY.")
    print("     FERNET_KEY encrypts clinical and client notes (Art. 9 GDPR data).")
    print("     Losing it means losing access to that encrypted content.")
    print()
    print("  .env controls much more than these three keys (email, calendar,")
    print("  data directory, HTTPS, and more). Review the full reference:")
    print(f"  {ENV_DOCS}")

    # 4. Network exposure (asked once; an existing answer in .env stands)
    url = "http://localhost:8000"
    if BIND_ADDRESS_KEY not in env:
        step("Choosing how the app is reached")
        values, url = _ask_access_mode(env)
        env.update(values)
        _write_env(env)
    _warn_if_proxy_bypassable()

    # 5. Start the stack
    step("Starting the stack")
    result = compose("up", "-d", "--remove-orphans")
    if result.returncode != 0:
        abort("docker compose up failed.\n  Check the logs for details:\n    ./prod.py logs")

    # 6. Wait for healthy
    if not _wait_for_healthy():
        abort(
            "Django did not become healthy in time.\n"
            "  Check what went wrong:\n"
            "    ./prod.py logs\n"
            "  Common causes: wrong POSTGRES_PASSWORD, missing FERNET_KEY,\n"
            "  or a port conflict on 8000."
        )

    # 7. Create superuser
    step("Creating your login")
    print("  You'll be prompted for a username, email address, and password.")
    print("  This will be your login for the web UI and Django admin.\n")
    result = manage("createsuperuser")
    if result.returncode != 0:
        print(
            "\n  createsuperuser did not complete — you can run it later:\n"
            "    ./prod.py manage createsuperuser"
        )

    # 8. Setup practice
    step("Setting up your practice")
    print("  You'll be prompted for your name, address, and bank details.")
    print("  These appear on invoices — you can edit them later in the admin.\n")
    result = manage("setup_practice")
    if result.returncode != 0:
        print(
            "\n  setup_practice did not complete — you can run it later:\n"
            "    ./prod.py manage setup_practice"
        )

    # 9. Done
    print()
    print("=" * 50)
    print("Setup complete.")
    print()
    print(f"  Open the app: {url}")
    print()
    print("  ⚠  Back up your .env file before anything else.")
    print("     It contains FERNET_KEY, which encrypts clinical notes (Art. 9 GDPR data).")
    print("     Losing it means that encrypted content cannot be recovered.")
    print("     Copy .env to a safe location now — USB drive or password manager.")
    print()
    print("  Next steps:")
    print("    ./prod.py logs          — check everything looks healthy")
    print("    ./prod.py update        — upgrade to a new release when one is out")
    print(f"    {ENV_DOCS}")
    print("                            — full .env reference (email, calendar, backups, ...)")
    return subprocess.CompletedProcess(args=[], returncode=0)


# ── preflight ────────────────────────────────────────────────────────────────


def _require_secrets():
    """Abort unless .env carries the secrets the stack cannot run without.

    Compose interpolates a missing variable to an empty string and only prints a
    WARN, so without this the stack comes up mid-broken — Postgres exits because
    POSTGRES_PASSWORD is blank — and the actual cause is four lines above the
    error, phrased as a warning.
    """
    if not os.path.exists(ENV_FILE):
        abort(
            "No .env file here — the stack has no database password or encryption key.\n"
            "  Run the guided setup, which generates them:\n"
            "    ./prod.py setup\n"
            "\n"
            "  Restoring an existing installation? Copy that machine's .env here first.\n"
            "  FERNET_KEY must match the original or encrypted clinical notes cannot be read."
        )
    env = _read_env()
    missing = [key for key in REQUIRED_SECRETS if not env.get(key)]
    if missing:
        abort(
            f".env is missing required secrets: {', '.join(missing)}\n"
            "  Setup fills in whatever is absent and leaves the rest of .env alone:\n"
            "    ./prod.py setup\n"
            "\n"
            "  Do not invent a FERNET_KEY for an installation that already has data —\n"
            "  the original is the only thing that can decrypt existing clinical notes."
        )


def _compose_container_names():
    """Container names claimed by docker-compose.prod.yml.

    Read with a regex rather than a YAML parser: prod.py ships to self-hosters
    as a single stdlib-only file, and this is the one value needed from it.
    """
    if not os.path.exists(COMPOSE_FILE):
        return []
    with open(COMPOSE_FILE) as f:
        return re.findall(r"^\s*container_name:\s*(\S+)", f.read(), re.MULTILINE)


def _inspect_container(ref):
    """(id, name, compose file basename) for a container, or None if absent.

    The compose file is "" for a container Compose did not create. Compared by
    basename so moving the installation directory doesn't read as a foreign stack.
    """
    out = subprocess.run(
        [
            "docker",
            "inspect",
            "--format",
            '{{.Id}}\t{{.Name}}\t{{index .Config.Labels "com.docker.compose.project.config_files"}}',
            ref,
        ],
        capture_output=True,
        text=True,
    )
    if out.returncode != 0:
        return None
    parts = out.stdout.strip().split("\t")
    if len(parts) < 3:
        return None
    container_id, name, files = parts[0], parts[1].lstrip("/"), parts[2]
    if not files or files == "<no value>":
        return container_id, name, ""
    return container_id, name, ", ".join(os.path.basename(path) for path in files.split(","))


def _project_container_ids():
    """Container ids Compose considers part of this project, running or not."""
    out = subprocess.run([*COMPOSE, "ps", "-aq"], capture_output=True, text=True)
    return out.stdout.split() if out.returncode == 0 else []


def _require_no_foreign_containers():
    """Abort rather than touch containers this compose file did not create.

    Three ways a container can carry one of our names without being ours, all
    because Docker namespaces less than it looks:

    - The development stack (docker-compose.yml, ./dev.py) uses the same
      container names. Names are global to the daemon, not scoped to a Compose
      project, so whichever stack starts second fails with a raw daemon conflict
      that names the container but not the stack holding it.
    - Both files take their project name from the directory, so Compose matches
      containers by project and service label regardless of name: a
      `docker compose -f docker-compose.prod.yml down` stops and removes the
      *development* containers, silently and without an error. That one is the
      dangerous case, and the reason this check also looks at project membership
      rather than names alone.
    - A container left by an earlier installation in a differently-named
      directory carries our compose file but a project name Compose no longer
      looks under, so `down` cannot reach it and `up` keeps failing on the name.

    Compose reports none of these usefully, so report them here and do nothing.
    """
    ours = os.path.basename(COMPOSE_FILE)
    project_ids = set(_project_container_ids())
    reported = set()
    for ref in [*_compose_container_names(), *project_ids]:
        found = _inspect_container(ref)
        if found is None:
            continue
        container_id, name, owner = found
        if owner == ours and container_id in project_ids:
            continue  # genuinely this stack's own container
        if name in reported:
            continue
        reported.add(name)
        if owner == ours:
            headline = f'The container "{name}" is left over from an earlier run of this stack.'
            why = (
                "  It was created in a different directory, so Compose no longer finds it\n"
                "  from here — but container names are global to Docker, so it still blocks\n"
                "  this one."
            )
            remedy = (
                "  Remove it. The database lives in a Docker volume, not in the container,\n"
                f"  so nothing is lost:\n    docker rm -f {name}"
            )
        elif owner == "docker-compose.yml":
            headline = f'The container "{name}" belongs to the development stack (./dev.py).'
            why = (
                "  Container names are global to Docker, and both compose files in this\n"
                "  directory take the same project name, so the two stacks cannot run\n"
                "  side by side — and a `down` here would remove the development ones."
            )
            remedy = "  Stop it first, then try again:\n    ./dev.py stop"
        elif owner:
            headline = f'The container "{name}" belongs to a stack started from {owner}.'
            why = "  Container names are global to Docker, so both stacks cannot use it."
            remedy = f"  Stop that stack, or remove the container:\n    docker rm -f {name}"
        else:
            headline = f'The container "{name}" was not created by Compose.'
            why = "  Container names are global to Docker, so it blocks this stack's own."
            remedy = f"  Remove it:\n    docker rm -f {name}"
        abort(
            f"{headline}\n"
            f"{why}\n"
            f"{remedy}\n"
            "\n"
            "  Nothing was started or stopped — your data is untouched."
        )


# ── network exposure ─────────────────────────────────────────────────────────


def _is_loopback(address):
    return address.startswith("127.") or address in ("::1", "[::1]", "localhost")


def _ask(prompt, default=""):
    """input() that treats a closed stdin (piped setup) as accepting the default."""
    try:
        return input(prompt).strip() or default
    except EOFError:
        print()
        return default


def _ask_access_mode(env):
    """Ask how the app will be reached; return the .env values that match.

    Returns (values, url) where url is what to open once the stack is up.
    """
    print("  How will you open the app?")
    print("    1) Only on this machine (recommended for a single laptop or desktop)")
    print("    2) Through an HTTPS reverse proxy (nginx, Caddy, ...) on this machine")
    print("    3) Directly from other devices on the network, over plain HTTP")
    choice = ""
    while choice not in ("1", "2", "3"):
        choice = _ask("  Choice [1]: ", "1")

    hosts = [h.strip() for h in env.get("DJANGO_ALLOWED_HOSTS", "").split(",") if h.strip()]
    for host in ("localhost", "127.0.0.1"):
        if host not in hosts:
            hosts.append(host)

    if choice == "1":
        values = {BIND_ADDRESS_KEY: "127.0.0.1", "SECURE_SSL_REDIRECT": "false"}
        url = "http://localhost:8000"
    elif choice == "2":
        domain = ""
        while not domain:
            domain = _ask("  Domain the proxy serves (e.g. practice.example): ")
        hosts.insert(0, domain)
        values = {BIND_ADDRESS_KEY: "127.0.0.1", "SECURE_SSL_REDIRECT": "true"}
        url = f"https://{domain}"
        print("  The proxy must forward to http://127.0.0.1:8000 and set X-Forwarded-Proto —")
        print("  see the nginx example in SECURITY.md.")
    else:
        address = ""
        while not address:
            address = _ask(
                "  This machine's IP address or hostname on the network (e.g. 192.168.1.20): "
            )
        hosts.insert(0, address)
        values = {BIND_ADDRESS_KEY: "0.0.0.0", "SECURE_SSL_REDIRECT": "false"}
        url = f"http://{address}:8000"
        print("  ⚠  Plain HTTP: passwords and client data cross the network unencrypted,")
        print("     readable by anyone on the same network. Use this only on a home network")
        print("     you trust; anywhere else, put an HTTPS reverse proxy in front (option 2).")

    values["DJANGO_ALLOWED_HOSTS"] = ",".join(dict.fromkeys(hosts))
    return values, url


def _ensure_bind_address():
    """Keep an installation set up before v0.8.0 reachable the way it was.

    Until then docker-compose.prod.yml published port 8000 on every interface;
    it now defaults to loopback. An existing .env without the key is pinned to
    the old behaviour, with a comment saying how to narrow it, rather than
    silently cutting off every other device after an update.
    """
    if BIND_ADDRESS_KEY in _read_env():
        return
    with open(ENV_FILE) as f:
        ends_with_newline = f.read().endswith("\n")
    with open(ENV_FILE, "a") as f:
        if not ends_with_newline:
            f.write("\n")
        f.write(
            "\n# Added by prod.py: keeps the app reachable from other devices, as before v0.8.0.\n"
            "# Set to 127.0.0.1 if only this machine (or a reverse proxy on it) needs it.\n"
            f"{BIND_ADDRESS_KEY}=0.0.0.0\n"
        )
    print(f"  Added {BIND_ADDRESS_KEY}=0.0.0.0 to .env — the app stays reachable from")
    print("  other devices as before. If only this machine or a reverse proxy on it")
    print(f"  needs it, change that to {BIND_ADDRESS_KEY}=127.0.0.1 (see SECURITY.md).")


def _warn_if_proxy_bypassable():
    """Warn when HTTPS is assumed but port 8000 is open beside the proxy.

    With SECURE_SSL_REDIRECT=true Django trusts X-Forwarded-Proto, which a
    client talking to port 8000 directly can set itself.
    """
    env = _read_env()
    address = env.get(BIND_ADDRESS_KEY, "127.0.0.1")
    if env.get("SECURE_SSL_REDIRECT", "").lower() == "true" and not _is_loopback(address):
        print(f"  ⚠  SECURE_SSL_REDIRECT=true but {BIND_ADDRESS_KEY}={address}: clients can")
        print("     reach port 8000 without going through the proxy and claim HTTPS.")
        print(f"     Set {BIND_ADDRESS_KEY}=127.0.0.1 if the proxy runs on this machine.")


# ── commands ────────────────────────────────────────────────────────────────


def cmd_start(_args):
    """Start the stack."""
    _require_secrets()
    _require_no_foreign_containers()
    _ensure_bind_address()
    _warn_if_proxy_bypassable()
    return compose("up", "-d", "--remove-orphans")


def cmd_stop(_args):
    """Stop the stack."""
    _require_no_foreign_containers()
    return compose("down")


def cmd_restart(_args):
    """Restart the Django container."""
    _require_secrets()
    _require_no_foreign_containers()
    return compose("restart", "django")


def cmd_update(args):
    """Back up, pull the latest image and restart. --yes skips the metered-connection prompt."""
    _require_secrets()
    _require_no_foreign_containers()
    if "--yes" not in args and not _confirm_metered_download("Pulling the latest image"):
        print("Aborted.")
        return subprocess.CompletedProcess(args=[], returncode=1)

    try:
        with urllib.request.urlopen(RELEASES_API, timeout=5) as r:
            latest = json.loads(r.read())["tag_name"]
        print(f"Latest release: {latest}")
        if latest != VERSION:
            new_base = RAW_BASE.replace(VERSION, latest)
            print(f"  This script is {VERSION}. A newer version is available.")
            print("  To update prod.py and docker-compose.prod.yml:")
            print(f"    curl -O {new_base}/prod.py")
            print(f"    curl -O {new_base}/docker-compose.prod.yml")
            print()
    except Exception:
        pass  # offline or rate-limited — just pull whatever is in the registry

    result = compose("pull")
    if result.returncode != 0:
        return result
    # The new container migrates on start and there is no downgrade path, so
    # the last pre-migration state has to exist before `up` — taken from the
    # still-running old containers (pull alone does not restart them).
    if "--skip-backup" not in args:
        print("📦 Backing up before the update (pass --skip-backup to skip)")
        try:
            run_backup(_compose_cmd(args), _backup_dir(), _passphrase_file())
        except BackupError as exc:
            print(f"❌ {exc}", file=sys.stderr)
            print(
                "   Update aborted before anything was restarted. Start the stack"
                " (./prod.py start) and retry, or pass --skip-backup.",
                file=sys.stderr,
            )
            return subprocess.CompletedProcess(args=[], returncode=1)
    _ensure_bind_address()
    _warn_if_proxy_bypassable()
    return compose("up", "-d", "--remove-orphans")


def cmd_logs(args):
    """Follow Django logs (pass extra flags like --tail 50)."""
    flags = list(args) if args else ["-f"]
    return subprocess.run([*COMPOSE, "logs", *flags, "django"])


def cmd_status(_args):
    """Show container status."""
    return compose("ps")


def cmd_manage(args):
    """Run a Django management command (e.g. ./prod.py manage migrate)."""
    if not args:
        print("Usage: ./prod.py manage <command> [args]")
        return subprocess.CompletedProcess(args=[], returncode=1)
    return manage(*args)


def cmd_shell(_args):
    """Open an interactive Django shell."""
    return manage("shell")


# ── backup / restore ─────────────────────────────────────────────────────────
#
# The one implementation of backups: scripts/backup.sh and scripts/restore.sh
# (used by the systemd timer in a git checkout) call these, and a self-hoster
# who only has prod.py gets the same thing as `./prod.py backup`.
#
# Every archive is written to a temporary file, verified, optionally
# encrypted, and only then renamed into place — so a failed run never leaves a
# file that looks like a backup, and never reaches the retention cleanup (which
# would otherwise rotate real backups out in favour of broken ones).

BACKUP_RETENTION_DAYS = 30
DUMP_TRAILER = b"PostgreSQL database dump complete"
BACKUP_GLOBS = (
    "db_backup_*.sql.gz",
    "db_backup_*.sql.gz.gpg",
    "media_backup_*.tar.gz",
    "media_backup_*.tar.gz.gpg",
    "media_backup_*.empty",
)


class BackupError(Exception):
    """A backup or restore step failed; the message names the step."""


def _setting(name, default=""):
    """A value from the environment, else .env (inline comments stripped)."""
    if os.environ.get(name):
        return os.environ[name]
    value = _read_env().get(name, "")
    return re.sub(r"\s+#.*$", "", value).strip() or default


def _backup_dir():
    base = os.path.dirname(os.path.abspath(__file__))
    data_dir = _setting(
        "MY_PRACTICE_DATA_DIR", os.path.join(os.path.dirname(base), "my-practice-data")
    )
    # A relative value resolves next to the compose file, as Compose does.
    return os.path.join(base, data_dir, "backups")


def _compose_cmd(args):
    """`docker compose -f <file>`, honouring --compose-file (used by scripts/backup.sh)."""
    files = [COMPOSE_FILE]
    if "--compose-file" in args:
        # Colon-separated, like Compose's own COMPOSE_FILE.
        files = [os.path.abspath(f) for f in args[args.index("--compose-file") + 1].split(":")]
    return ["docker", "compose", *(arg for f in files for arg in ("-f", f))]


def _passphrase_file():
    """BACKUP_PASSPHRASE_FILE, checked, or None when archives stay unencrypted."""
    path = _setting("BACKUP_PASSPHRASE_FILE")
    if not path:
        return None
    if not os.path.isfile(path):
        raise BackupError(f"BACKUP_PASSPHRASE_FILE does not exist: {path}")
    if not shutil.which("gpg"):
        raise BackupError("BACKUP_PASSPHRASE_FILE is set but gpg is not installed")
    return path


def _gpg(passphrase_file, *args):
    return [
        "gpg",
        "--batch",
        "--yes",
        "--quiet",
        "--pinentry-mode",
        "loopback",
        "--passphrase-file",
        passphrase_file,
        *args,
    ]


def _stream_to_file(cmd, path, compress=False):
    """Run cmd, writing its stdout to path (gzip-compressed if asked)."""
    with open(path, "wb") as raw:
        sink = gzip.GzipFile(fileobj=raw, mode="wb") if compress else raw
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        for chunk in iter(lambda: proc.stdout.read(1 << 20), b""):
            sink.write(chunk)
        proc.stdout.close()
        if compress:
            sink.close()
        return proc.wait()


def _verify_dump(path):
    """pg_dump writes its trailer only after the whole dump succeeded."""
    tail = b""
    try:
        with gzip.open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                tail = (tail + chunk)[-4096:]
    except (OSError, EOFError) as exc:
        raise BackupError(f"Database backup is not a valid gzip archive ({exc})") from None
    if DUMP_TRAILER not in tail:
        raise BackupError("Database backup is incomplete (pg_dump trailer missing)")


def _verify_media(path, expected):
    try:
        with tarfile.open(path, "r:gz") as tar:
            count = sum(1 for member in tar if not member.isdir())
    except (OSError, EOFError, tarfile.TarError) as exc:
        raise BackupError(f"Media backup is not a readable tar.gz archive ({exc})") from None
    if count != expected:
        raise BackupError(f"Media backup holds {count} files, expected {expected}")


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _encrypt(path, passphrase_file):
    """Encrypt a verified archive with gpg; prove it decrypts back; return the new path."""
    encrypted = path + ".gpg"
    result = subprocess.run(
        _gpg(passphrase_file, "--symmetric", "--cipher-algo", "AES256", "-o", encrypted, path)
    )
    if result.returncode != 0:
        raise BackupError("gpg encryption failed")
    # Hash the decrypted stream instead of writing it to a file: gpg would
    # create that file itself, with whatever mode the umask gives it, and a
    # killed run would leave a plaintext copy next to the encrypted backup.
    proc = subprocess.Popen(
        _gpg(passphrase_file, "--decrypt", "-o", "-", encrypted), stdout=subprocess.PIPE
    )
    digest = hashlib.sha256()
    for chunk in iter(lambda: proc.stdout.read(1 << 20), b""):
        digest.update(chunk)
    proc.stdout.close()
    if proc.wait() != 0 or digest.hexdigest() != _sha256(path):
        raise BackupError("Encrypted backup does not decrypt back to the original")
    os.unlink(path)
    return encrypted


def _prune(backup_dir):
    cutoff = time.time() - BACKUP_RETENTION_DAYS * 86400
    for pattern in BACKUP_GLOBS:
        for path in glob.glob(os.path.join(backup_dir, pattern)):
            if os.path.getmtime(path) < cutoff:
                os.unlink(path)


def run_backup(compose_cmd, backup_dir, passphrase_file=None):
    """Dump the database and archive media into backup_dir. Returns the final paths."""
    # Owner-only: an unencrypted archive is protected by nothing but this
    # directory, and makedirs alone would take the umask's (usually 0755).
    os.makedirs(backup_dir, mode=0o700, exist_ok=True)
    os.chmod(backup_dir, 0o700)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    user = _setting("POSTGRES_USER", "my_practice")
    db = _setting("POSTGRES_DB", "my_practice")
    temps, finals = [], []

    def temp(prefix):
        # Same directory as the final file, so the rename is atomic; mkstemp
        # creates it 0600, which the final archive keeps.
        fd, path = tempfile.mkstemp(dir=backup_dir, prefix=f".{prefix}_{stamp}.")
        os.close(fd)
        temps.append(path)
        return path

    def publish(tmp, name):
        if passphrase_file:
            tmp = _encrypt(tmp, passphrase_file)
            temps.append(tmp)
            name += ".gpg"
        final = os.path.join(backup_dir, name)
        os.replace(tmp, final)
        finals.append(final)

    try:
        db_tmp = temp("db_backup")
        dump = [
            *compose_cmd,
            "exec",
            "-T",
            "postgres",
            "pg_dump",
            "-U",
            user,
            "-d",
            db,
            "--no-owner",
            "--clean",
            "--if-exists",
        ]
        if _stream_to_file(dump, db_tmp, compress=True) != 0:
            raise BackupError(
                "Database backup failed (pg_dump or docker compose exec exited non-zero)"
            )
        _verify_dump(db_tmp)
        publish(db_tmp, f"db_backup_{stamp}.sql.gz")

        # A failure here (django container down) aborts rather than passing for "no media".
        listing = subprocess.run(
            [*compose_cmd, "exec", "-T", "django", "find", "/app/media", "-type", "f"],
            capture_output=True,
        )
        if listing.returncode != 0:
            raise BackupError("Could not list media files in the django container")
        media_count = len(listing.stdout.splitlines())
        if media_count:
            media_tmp = temp("media_backup")
            tar = [*compose_cmd, "exec", "-T", "django", "tar", "czf", "-", "-C", "/app", "media"]
            if _stream_to_file(tar, media_tmp) != 0:
                raise BackupError("Media backup failed")
            _verify_media(media_tmp, media_count)
            publish(media_tmp, f"media_backup_{stamp}.tar.gz")
        else:
            marker = os.path.join(backup_dir, f"media_backup_{stamp}.empty")
            with open(marker, "w") as f:
                f.write(f"No media files at {time.ctime()}\n")
            finals.append(marker)
    finally:
        for path in temps:
            if os.path.exists(path):
                os.unlink(path)

    # Only reached when every archive above was verified.
    _prune(backup_dir)
    return finals


def cmd_backup(args):
    """Back up the database and media to MY_PRACTICE_DATA_DIR/backups (verified, rotated)."""
    try:
        backup_dir = _backup_dir()
        print(f"📦 Backing up to {backup_dir}")
        finals = run_backup(_compose_cmd(args), backup_dir, _passphrase_file())
    except BackupError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return subprocess.CompletedProcess(args=[], returncode=1)
    for path in finals:
        size = os.path.getsize(path)
        human = f"{size / 1048576:.1f} MB" if size >= 1048576 else f"{size / 1024:.1f} KB"
        print(f"✅ {os.path.basename(path)} ({human})")
    if not _setting("BACKUP_PASSPHRASE_FILE"):
        print(
            "ℹ️  Archives are not encrypted — set BACKUP_PASSPHRASE_FILE in .env to encrypt them with gpg."
        )
    print(f"✨ Backup complete; archives older than {BACKUP_RETENTION_DAYS} days pruned.")
    return subprocess.CompletedProcess(args=[], returncode=0)


def _decrypted(path, passphrase_file, workdir):
    """Path to a plain copy of an archive (decrypting .gpg ones into workdir)."""
    if not path.endswith(".gpg"):
        return path
    if not shutil.which("gpg"):
        raise BackupError("gpg is needed to restore an encrypted backup")
    plain = os.path.join(workdir, os.path.basename(path)[: -len(".gpg")])
    # Without a passphrase file gpg asks for the passphrase interactively.
    cmd = (
        _gpg(passphrase_file, "--decrypt", "-o", plain, path)
        if passphrase_file
        else ["gpg", "--decrypt", "-o", plain, path]
    )
    if subprocess.run(cmd).returncode != 0:
        raise BackupError(f"Could not decrypt {path}")
    return plain


# Unpack into a staging directory inside the media mount (same filesystem, and
# the leading dot keeps it apart from the media itself), and only replace the
# current files once tar has succeeded.
MEDIA_RESTORE_SCRIPT = (
    "set -e; staging=/app/media/.restore; trap 'rm -rf \"$staging\"' EXIT; "
    'rm -rf "$staging"; mkdir "$staging"; tar xzf - -C "$staging"; '
    "find /app/media -mindepth 1 -maxdepth 1 ! -name .restore -exec rm -rf {} +; "
    'if [ -d "$staging/media" ]; then '
    'find "$staging/media" -mindepth 1 -maxdepth 1 -exec mv {} /app/media/ \\; ; fi'
)


def _verify_media_archive(path):
    """A media backup to restore: readable, and nothing but files under media/."""
    try:
        with tarfile.open(path, "r:gz") as tar:
            for member in tar:
                parts = member.name.split("/")
                if (
                    parts[0] != "media"
                    or ".." in parts
                    or parts[1:2] == [".restore"]  # the staging directory
                    or member.name.startswith("/")
                    or not (member.isfile() or member.isdir())
                ):
                    raise BackupError(f"Media backup has an unexpected entry: {member.name}")
    except (OSError, EOFError, tarfile.TarError) as exc:
        raise BackupError(f"Media backup is not a readable tar.gz archive ({exc})") from None


def cmd_restore(args):
    """Restore a database backup (and optionally a media backup) — overwrites current data."""
    files = [
        a
        for i, a in enumerate(args)
        if not a.startswith("--") and (i == 0 or args[i - 1] != "--compose-file")
    ]
    if not files:
        print("Usage: ./prod.py restore <db_backup_file> [media_backup_file]")
        print(f"Backups live in {_backup_dir()}")
        return subprocess.CompletedProcess(args=[], returncode=1)
    db_file, media_file = files[0], (files[1] if len(files) > 1 else None)
    for path in filter(None, (db_file, media_file)):
        if not os.path.isfile(path):
            print(f"❌ Backup file not found: {path}", file=sys.stderr)
            return subprocess.CompletedProcess(args=[], returncode=1)

    print("⚠️  This OVERWRITES the current database" + (" and media" if media_file else "") + ".")
    if "--yes" not in args and input("Type 'yes' to continue: ").strip() != "yes":
        print("Restore cancelled.")
        return subprocess.CompletedProcess(args=[], returncode=0)

    try:
        compose_cmd = _compose_cmd(args)
        passphrase_file = _passphrase_file()
        with tempfile.TemporaryDirectory() as workdir:
            # Check both archives before touching anything, so a bad media file
            # cannot leave a restored database next to the old media.
            plain_db = _decrypted(db_file, passphrase_file, workdir)
            _verify_dump(plain_db)
            plain_media = _decrypted(media_file, passphrase_file, workdir) if media_file else None
            if plain_media:
                _verify_media_archive(plain_media)

            # --single-transaction: an error rolls the whole restore back
            # instead of leaving the --clean drops done and the data half-loaded.
            # ON_ERROR_STOP: psql otherwise logs a failed statement and exits 0.
            psql = subprocess.Popen(
                [
                    *compose_cmd,
                    "exec",
                    "-T",
                    "postgres",
                    "psql",
                    "-U",
                    _setting("POSTGRES_USER", "my_practice"),
                    "-d",
                    _setting("POSTGRES_DB", "my_practice"),
                    "--quiet",
                    "--single-transaction",
                    "-v",
                    "ON_ERROR_STOP=1",
                ],
                stdin=subprocess.PIPE,
            )
            with gzip.open(plain_db, "rb") as dump:
                for chunk in iter(lambda: dump.read(1 << 20), b""):
                    psql.stdin.write(chunk)
            # The dump brings back the sessions that were live when it was
            # taken; sign everyone in afresh instead of reviving them.
            psql.stdin.write(b"\nTRUNCATE django_session;\n")
            psql.stdin.close()
            if psql.wait() != 0:
                raise BackupError("Database restore failed; the database is unchanged")
            print("✅ Database restored")

            if plain_media:
                with open(plain_media, "rb") as archive:
                    result = subprocess.run(
                        [*compose_cmd, "exec", "-T", "django", "sh", "-c", MEDIA_RESTORE_SCRIPT],
                        stdin=archive,
                    )
                if result.returncode != 0:
                    raise BackupError(
                        "Media restore failed; the existing media files are unchanged"
                    )
                print("✅ Media restored")
    except BackupError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return subprocess.CompletedProcess(args=[], returncode=1)
    print("ℹ️  All sessions were signed out. Data erased or anonymised since this backup")
    print("   was taken is back: repeat those GDPR erasures and anonymisations.")
    print("✨ Restore complete. Check the key: ./prod.py manage encryption check")
    return subprocess.CompletedProcess(args=[], returncode=0)


# ── dispatch ─────────────────────────────────────────────────────────────────

COMMANDS = {
    "setup": (cmd_setup, "First-time setup: secrets, pull, start, create login"),
    "start": (cmd_start, "Start the stack"),
    "stop": (cmd_stop, "Stop the stack"),
    "restart": (cmd_restart, "Restart the Django container"),
    "update": (cmd_update, "Back up, pull the latest image and restart"),
    "logs": (cmd_logs, "Follow Django logs"),
    "status": (cmd_status, "Show container status"),
    "manage": (cmd_manage, "Run a Django management command"),
    "shell": (cmd_shell, "Open an interactive Django shell"),
    "backup": (cmd_backup, "Back up database + media (verified, 30-day rotation)"),
    "restore": (cmd_restore, "Restore a backup (overwrites current data)"),
}


def print_help():
    print("Usage: ./prod.py <command> [args]")
    print()
    print("Commands:")
    for name, (_, desc) in COMMANDS.items():
        print(f"  {name:<10} {desc}")
    print()
    print("Examples:")
    print("  ./prod.py setup                         # first-time setup (recommended)")
    print("  ./prod.py update                        # back up, pull latest image + restart")
    print("  ./prod.py logs                          # follow Django logs")
    print("  ./prod.py logs --tail 50                # last 50 lines")
    print("  ./prod.py status                        # container health")
    print("  ./prod.py manage createsuperuser        # create a login manually")
    print("  ./prod.py manage setup_practice         # practice setup wizard")
    print("  ./prod.py manage migrate                # apply database migrations")
    print("  ./prod.py shell                         # Django shell")
    print("  ./prod.py backup                        # back up now (schedule it daily)")
    print("  ./prod.py restore <db.sql.gz> [media]   # restore from a backup")


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print_help()
        return 0

    name = sys.argv[1]
    args = sys.argv[2:]

    if name not in COMMANDS:
        print(f"Unknown command: {name}")
        print()
        print_help()
        return 1

    result = COMMANDS[name][0](args)
    return result.returncode if result else 0


if __name__ == "__main__":
    sys.exit(main())
