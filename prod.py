#!/usr/bin/env python3
"""prod.py — management helper for the my-practice production stack.

Requirements: Python 3, Docker with the Compose plugin.
"""

import json
import os
import subprocess
import sys
import urllib.request

COMPOSE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docker-compose.prod.yml")
COMPOSE = ["docker", "compose", "-f", COMPOSE_FILE]


def compose(*args):
    return subprocess.run([*COMPOSE, *args])


def exec_django(*args):
    tty = ["-it"] if sys.stdin.isatty() else ["-i"]
    return subprocess.run([*COMPOSE, "exec", *tty, "django", *args])


def manage(*args):
    return exec_django("python", "manage.py", *args)


# ── commands ────────────────────────────────────────────────────────────────

def cmd_start(_args):
    """Start the stack."""
    return compose("up", "-d", "--remove-orphans")


def cmd_stop(_args):
    """Stop the stack."""
    return compose("down")


def cmd_restart(_args):
    """Restart the Django container."""
    return compose("restart", "django")


def cmd_update(_args):
    """Pull the latest image and restart."""
    try:
        url = "https://api.github.com/repos/dholbach/my-practice/releases/latest"
        with urllib.request.urlopen(url, timeout=5) as r:
            tag = json.loads(r.read())["tag_name"]
            print(f"Latest release: {tag}")
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
    "start":   (cmd_start,  "Start the stack"),
    "stop":    (cmd_stop,   "Stop the stack"),
    "restart": (cmd_restart,"Restart the Django container"),
    "update":  (cmd_update, "Pull the latest image and restart"),
    "logs":    (cmd_logs,   "Follow Django logs"),
    "status":  (cmd_status, "Show container status"),
    "manage":  (cmd_manage, "Run a Django management command"),
    "shell":   (cmd_shell,  "Open an interactive Django shell"),
}


def print_help():
    print("Usage: ./prod.py <command> [args]")
    print()
    print("Commands:")
    for name, (_, desc) in COMMANDS.items():
        print(f"  {name:<10} {desc}")
    print()
    print("Examples:")
    print("  ./prod.py update                        # pull latest image + restart")
    print("  ./prod.py manage createsuperuser        # create the first login")
    print("  ./prod.py manage setup_practice         # practice setup wizard")
    print("  ./prod.py manage migrate                # apply database migrations")
    print("  ./prod.py logs                          # follow Django logs")
    print("  ./prod.py logs --tail 50                # last 50 lines")
    print("  ./prod.py shell                         # Django shell")
    print("  ./prod.py status                        # container health")


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
