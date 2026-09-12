#!/usr/bin/env python3
"""prod.py — management helper for the my-practice production stack.

Requirements: Python 3, Docker with the Compose plugin.
"""

import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
import urllib.request

VERSION = "v0.6.0"  # updated each release — keeps prod.py and docker-compose.prod.yml in sync

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


def _is_metered_connection():
    """Best-effort NetworkManager check for a metered connection (e.g. mobile hotspot).

    Returns True/False when nmcli gives a definite answer, None when it can't be
    determined (no NetworkManager, no default route, non-Linux host, ...).
    Callers should treat None as "unknown" and not block on it.
    """
    # Deliberately not identical to dev.py's copy: dev.py routes these through
    # flatpak-spawn for VS Code's sandboxed terminal, a workstation concern that
    # would drag is_vscode()/has_flatpak_spawn() into a file that ships on its
    # own. Unlike _confirm_metered_download below, these two may differ.
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


# Duplicated verbatim in dev.py. prod.py ships to self-hosters as a single
# stdlib-only file, so it cannot import a shared module, and the two copies must
# stay identical — scripts/check_shared_helpers.py fails if they drift.
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
    print("     FERNET_KEY encrypts clinical notes (Art. 9 GDPR data).")
    print("     Losing it means losing access to that encrypted content.")
    print()
    print("  .env controls much more than these three keys (email, calendar,")
    print("  data directory, HTTPS, and more). Review the full reference:")
    print(f"  {ENV_DOCS}")

    # 4. Start the stack
    step("Starting the stack")
    result = compose("up", "-d", "--remove-orphans")
    if result.returncode != 0:
        abort("docker compose up failed.\n  Check the logs for details:\n    ./prod.py logs")

    # 5. Wait for healthy
    if not _wait_for_healthy():
        abort(
            "Django did not become healthy in time.\n"
            "  Check what went wrong:\n"
            "    ./prod.py logs\n"
            "  Common causes: wrong POSTGRES_PASSWORD, missing FERNET_KEY,\n"
            "  or a port conflict on 8000."
        )

    # 6. Create superuser
    step("Creating your login")
    print("  You'll be prompted for a username, email address, and password.")
    print("  This will be your login for the web UI and Django admin.\n")
    result = manage("createsuperuser")
    if result.returncode != 0:
        print(
            "\n  createsuperuser did not complete — you can run it later:\n"
            "    ./prod.py manage createsuperuser"
        )

    # 7. Setup practice
    step("Setting up your practice")
    print("  You'll be prompted for your name, address, and bank details.")
    print("  These appear on invoices — you can edit them later in the admin.\n")
    result = manage("setup_practice")
    if result.returncode != 0:
        print(
            "\n  setup_practice did not complete — you can run it later:\n"
            "    ./prod.py manage setup_practice"
        )

    # 8. Done
    print()
    print("=" * 50)
    print("Setup complete.")
    print()
    print("  Open the app: http://localhost:8000")
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


# ── commands ────────────────────────────────────────────────────────────────


def cmd_start(_args):
    """Start the stack."""
    _require_secrets()
    _require_no_foreign_containers()
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
    """Pull the latest image and restart. Pass --yes to skip the metered-connection prompt."""
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


# ── dispatch ─────────────────────────────────────────────────────────────────

COMMANDS = {
    "setup": (cmd_setup, "First-time setup: secrets, pull, start, create login"),
    "start": (cmd_start, "Start the stack"),
    "stop": (cmd_stop, "Stop the stack"),
    "restart": (cmd_restart, "Restart the Django container"),
    "update": (cmd_update, "Pull the latest image and restart"),
    "logs": (cmd_logs, "Follow Django logs"),
    "status": (cmd_status, "Show container status"),
    "manage": (cmd_manage, "Run a Django management command"),
    "shell": (cmd_shell, "Open an interactive Django shell"),
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
    print("  ./prod.py update                        # pull latest image + restart")
    print("  ./prod.py logs                          # follow Django logs")
    print("  ./prod.py logs --tail 50                # last 50 lines")
    print("  ./prod.py status                        # container health")
    print("  ./prod.py manage createsuperuser        # create a login manually")
    print("  ./prod.py manage setup_practice         # practice setup wizard")
    print("  ./prod.py manage migrate                # apply database migrations")
    print("  ./prod.py shell                         # Django shell")


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
