#!/usr/bin/env python3
"""
Development helper script for the my-practice Django project.
Automatically detects if running in VS Code on Silverblue and prepends flatpak-spawn.
"""

import os
import shutil
import subprocess
import sys

CONTAINER_NAME = "my-practice-django"


def is_vscode():
    """Check if running in VS Code terminal"""
    return os.environ.get("TERM_PROGRAM") == "vscode"


def has_flatpak_spawn():
    """Check if flatpak-spawn is available"""
    try:
        subprocess.run(
            ["flatpak-spawn", "--help"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def needs_flatpak():
    """Determine if we need to use flatpak-spawn"""
    return is_vscode() and has_flatpak_spawn()


def run_host_command(args):
    """Run a command on the host (outside Docker), respecting flatpak sandbox."""
    cmd = []
    if needs_flatpak():
        cmd.extend(["flatpak-spawn", "--host"])
    cmd.extend(args)
    return subprocess.run(cmd)


def run_docker_command(args, interactive=False):
    """Run a docker command, optionally through flatpak-spawn"""
    cmd = []
    if needs_flatpak():
        cmd.extend(["flatpak-spawn", "--host"])

    cmd.extend(["docker", "exec"])

    if interactive:
        cmd.append("-it")

    cmd.append(CONTAINER_NAME)
    cmd.extend(args)

    return subprocess.run(cmd)


def compose_base_cmd():
    """Return compose command, preferring `docker compose` over `docker-compose`."""
    if shutil.which("docker"):
        return ["docker", "compose"]
    return ["docker-compose"]


def cmd_restart(args):
    """Restart the Django container (or do full restart with --force)"""
    # Check if --force flag is present
    if "--force" in args:
        extra_args = [a for a in args if a not in ("--force", "--build")]
        rebuild = "--build" in args
        print(
            "Forcing full restart (compose down/up) to reload environment variables..."
        )
        if rebuild:
            print("Rebuilding image first...")
            cmd_build(extra_args)
        cmd_stop([])
        return cmd_start(extra_args)
    else:
        print(f"Restarting {CONTAINER_NAME}...")
        cmd = []
        if needs_flatpak():
            cmd.extend(["flatpak-spawn", "--host"])
        cmd.extend(["docker", "restart", CONTAINER_NAME])
        return subprocess.run(cmd)


def cmd_test(args):
    """Run Django tests and JavaScript tests

    Speed optimizations:
    - --smart: Only run tests affected by recent file changes (pytest + testmon).
              First run builds a mapping; subsequent runs are very fast.
    - --parallel N: Run tests in N parallel workers (default: auto-detect CPUs)
    - --failfast: Stop on first failure
    - --fast: Shortcut for --parallel --failfast
    - --no-keepdb: Recreate test database (use when schema changed)
    """
    results = []

    # Check for --js-only flag
    if "--js-only" in args:
        args = [a for a in args if a != "--js-only"]
        return cmd_test_js(args)

    # Check for --smart flag: pytest + testmon (only run tests affected by changes)
    if "--smart" in args:
        args = [a for a in args if a != "--smart"]
        print("🎯 Smart mode: only running tests affected by recent changes...")
        print("   (First run builds the mapping — all tests execute once.)")
        pytest_args = ["python", "-m", "pytest", "--testmon", "-q"]
        if args:  # allow passing extra filters, e.g. a test path
            pytest_args.extend(args)
        return run_docker_command(pytest_args)

    # Check for --django-only flag
    django_only = "--django-only" in args
    if django_only:
        args = [a for a in args if a != "--django-only"]

    # Check for --no-keepdb flag (recreate test database)
    use_keepdb = "--no-keepdb" not in args
    if not use_keepdb:
        args = [a for a in args if a != "--no-keepdb"]

    # Check for --fast shortcut (parallel + failfast)
    fast_flags = []
    if "--fast" in args:
        args = [a for a in args if a != "--fast"]
        # Store flags to add later (after positional arguments)
        if not any(a.startswith("--parallel") for a in args):
            fast_flags.append("--parallel")
        if "--failfast" not in args:
            fast_flags.append("--failfast")

    # Note: Using --keepdb to reuse test database between runs
    # This avoids the need for cleanup and speeds up tests

    # Determine if specific Django tests were specified
    has_specific_tests = (
        args and "--all" not in args and any(not arg.startswith("--") for arg in args)
    )

    # Run Django tests
    print("🐍 Running Django tests...")
    test_args = ["python", "manage.py", "test"]
    if use_keepdb:
        test_args.append("--keepdb")
    if args and "--all" not in args:
        test_args.extend(args)
    else:
        test_args.extend(["-v", "2"])
    # Add --fast flags after positional arguments
    test_args.extend(fast_flags)

    django_result = run_docker_command(test_args)
    results.append(("Django", django_result.returncode))

    # Only run JavaScript tests if no specific Django tests were requested and not django-only
    if not has_specific_tests and not django_only:
        print("\n📊 Running JavaScript tests...")
        js_result = cmd_test_js([])
        results.append(("JavaScript", js_result.returncode))

    # Print summary
    print("\n" + "=" * 50)
    print("Test Summary:")
    print("=" * 50)
    for test_type, code in results:
        if code is None:
            status = "⊘ SKIPPED"
        elif code == 0:
            status = "✓ PASSED"
        else:
            status = "✗ FAILED"
        print(f"{test_type:12} {status}")
    print("=" * 50)

    # Return non-zero if any test failed
    failed = any(code != 0 for _, code in results if code is not None)
    return subprocess.CompletedProcess(args=[], returncode=1 if failed else 0)


def cmd_test_js(args):
    """Run JavaScript chart tests"""

    # Check if --browser flag is present
    browser_only = "--browser" in args
    node_only = "--node" in args

    if browser_only:
        print("📊 JavaScript Chart Tests (Browser-based)")
        print("\nThe browser tests run in the browser console.")
        print(
            "They are automatically executed when you visit the analytics page in development mode."
        )
        print("\nTo run the tests:")
        print("  1. Make sure the server is running: ./dev.py start")
        print("  2. Open http://localhost:8000/analytics/ in your browser")
        print("  3. Open the browser console (F12)")
        print("  4. Tests will run automatically and show results in the console")
        print("\nBrowser Test files:")
        print("  - test_chart_config.js (18 tests)")
        print("  - test_chart_tooltip.js (13 tests)")
        print("  - test_chart_builder.js (17 tests)")
        print("  - test_chart_math.js (math & parsing)")
        print("  - test_chart_helpers.js (validation)")
        print("\nTotal: 48+ test functions covering 1,621 lines of chart code")
        print("\nNote: Tests only run when DEBUG=True (development mode)")
        return subprocess.CompletedProcess(args=[], returncode=0)

    results = []

    # Run Node.js-based tests (if not browser-only)
    if not browser_only:
        print("📊 Running Node.js-based Chart Tests...")

        # Run basic tests
        print("\n--- Basic Chart Utils Tests ---")
        js_result = run_docker_command(["node", "/app/static/js/chart_utils.test.js"])
        results.append(("JS Basic", js_result.returncode))

        # Run extended tests
        if not node_only:
            print("\n--- Extended Chart Utils Tests ---")
            js_ext_result = run_docker_command(
                ["node", "/app/static/js/chart_utils.test.extended.js"]
            )
            results.append(("JS Extended", js_ext_result.returncode))

    # Show browser test info (if not node-only)
    if not node_only:
        print("\n" + "=" * 50)
        print("📊 Browser-based Tests (Phase 2b)")
        print("=" * 50)
        print("\nThe new browser tests (Phase 2b infrastructure) run automatically")
        print("when you visit http://localhost:8000/analytics/ with DEBUG=True")
        print("\nBrowser Test Coverage:")
        print("  - ChartConfig system (18 tests)")
        print("  - ChartTooltip classes (13 tests)")
        print("  - ChartBuilder API (17 tests)")
        print("\nTo run browser tests:")
        print("  ./dev.py test-js --browser")

    # Print Node.js test summary
    if results:
        print("\n" + "=" * 50)
        print("Node.js Test Summary:")
        print("=" * 50)
        for test_type, code in results:
            if code == 0:
                status = "✓ PASSED"
            else:
                status = "✗ FAILED"
            print(f"{test_type:12} {status}")
        print("=" * 50)

        # Return non-zero if any test failed
        failed = any(code != 0 for _, code in results)
        return subprocess.CompletedProcess(args=[], returncode=1 if failed else 0)

    return subprocess.CompletedProcess(args=[], returncode=0)


def cmd_manage(args):
    """Run Django management commands"""
    if not args:
        print("Usage: dev.py manage <command>")
        return subprocess.CompletedProcess(args=[], returncode=1)

    # If --odt-file points to a host path that isn't already inside the container,
    # copy it into the container's /tmp/ first and rewrite the argument.
    args = list(args)
    container_tmp_path = None
    for i, arg in enumerate(args):
        if arg == "--odt-file" and i + 1 < len(args):
            host_path = os.path.expanduser(args[i + 1])
            if not host_path.startswith("/app"):
                filename = os.path.basename(host_path)
                container_tmp_path = f"/tmp/{filename}"
                cp_cmd = []
                if needs_flatpak():
                    cp_cmd.extend(["flatpak-spawn", "--host"])
                cp_cmd.extend(["docker", "cp", host_path, f"{CONTAINER_NAME}:{container_tmp_path}"])
                print(f"Copying {host_path} → container:{container_tmp_path}")
                result = subprocess.run(cp_cmd)
                if result.returncode != 0:
                    return result
                args[i + 1] = container_tmp_path
            break

    interactive = args[0] in ("createsuperuser", "shell") if args else False
    result = run_docker_command(["python", "manage.py"] + args, interactive=interactive)

    # Clean up the temporary file from the container.
    if container_tmp_path:
        rm_cmd = []
        if needs_flatpak():
            rm_cmd.extend(["flatpak-spawn", "--host"])
        rm_cmd.extend(["docker", "exec", CONTAINER_NAME, "rm", "-f", container_tmp_path])
        subprocess.run(rm_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    return result


def cmd_python(args):
    """Run Python in the container"""
    if args:
        return run_docker_command(["python"] + args)
    else:
        return run_docker_command(["python"], interactive=True)


def cmd_shell(args):
    """Open Django shell or execute command with -c"""
    # Check for -c flag (execute command)
    if args and args[0] == "-c":
        if len(args) < 2:
            print("Error: -c requires a command to execute")
            print(
                'Example: ./dev.py shell -c "from my_practice.models import Client; print(Client.objects.count())"'
            )
            return subprocess.CompletedProcess(args=[], returncode=1)

        # Join all remaining args as the command
        command = " ".join(args[1:])

        # Execute command via stdin
        cmd = []
        if needs_flatpak():
            cmd.extend(["flatpak-spawn", "--host"])
        cmd.extend(
            ["docker", "exec", "-i", CONTAINER_NAME, "python", "manage.py", "shell"]
        )

        return subprocess.run(cmd, input=command.encode(), capture_output=False)
    else:
        # Interactive shell
        return run_docker_command(["python", "manage.py", "shell"], interactive=True)


def cmd_bash(args):
    """Open bash shell in container"""
    return run_docker_command(["bash"], interactive=True)


def cmd_build(args):
    """Rebuild Docker image(s) via compose build.

    Options:
        --no-cache   Force full rebuild (ignore layer cache)
        <service>    Build only a specific service (default: all)
    """
    print("Building Docker image(s)...")
    cmd = []
    if needs_flatpak():
        cmd.extend(["flatpak-spawn", "--host"])
    cmd.extend(compose_base_cmd())
    cmd.append("build")
    if args:
        cmd.extend(args)
    return subprocess.run(cmd)


def cmd_start(args):
    """Start all containers with compose."""
    print("Starting containers with compose...")
    cmd = []
    if needs_flatpak():
        cmd.extend(["flatpak-spawn", "--host"])
    cmd.extend(compose_base_cmd())
    cmd.extend(["up", "-d"])
    if args:
        cmd.extend(args)
    result = subprocess.run(cmd)
    if result.returncode != 0:
        return result
    # Wait for Django to finish migrating and start serving requests.
    print("Waiting for Django to be ready...", end="", flush=True)
    wait_cmd = []
    if needs_flatpak():
        wait_cmd.extend(["flatpak-spawn", "--host"])
    wait_cmd.extend(["docker", "inspect", "--format", "{{.State.Health.Status}}", CONTAINER_NAME])
    import time
    for _ in range(60):
        out = subprocess.run(wait_cmd, capture_output=True, text=True)
        status = out.stdout.strip()
        if status == "healthy":
            print(" ready.")
            break
        if status == "unhealthy":
            print(" unhealthy — check logs with: ./dev.py logs -f")
            break
        print(".", end="", flush=True)
        time.sleep(2)
    else:
        print(" timed out — check logs with: ./dev.py logs -f")
    return result


def cmd_stop(args):
    """Stop all containers with compose."""
    print("Stopping containers with compose...")
    cmd = []
    if needs_flatpak():
        cmd.extend(["flatpak-spawn", "--host"])
    cmd.extend(compose_base_cmd())
    cmd.extend(["down"])
    if args:
        cmd.extend(args)
    return subprocess.run(cmd)


def cmd_logs(args):
    """Show container logs"""
    cmd = []
    if needs_flatpak():
        cmd.extend(["flatpak-spawn", "--host"])

    # If no args or only flags, use compose logs for all services
    if not args or (args and args[0].startswith("-")):
        cmd.extend(compose_base_cmd())
        cmd.extend(["logs"])
        if "-f" not in args and "--follow" not in args:
            cmd.extend(["--tail", "100"])
        if args:
            cmd.extend(args)
    else:
        # Specific container requested, use docker logs
        cmd.extend(["docker", "logs"])
        if "-f" not in args and "--follow" not in args:
            cmd.extend(["--tail", "100"])
        cmd.extend(args)

    return subprocess.run(cmd)


def cmd_ps(args):
    """Show container status"""
    cmd = []
    if needs_flatpak():
        cmd.extend(["flatpak-spawn", "--host"])
    cmd.extend(compose_base_cmd())
    cmd.extend(["ps"])
    if args:
        cmd.extend(args)
    return subprocess.run(cmd)


def cmd_migrate(args):
    """Run migrations"""
    return run_docker_command(["python", "manage.py", "migrate"] + args)


def cmd_makemigrations(args):
    """Create new migrations"""
    return run_docker_command(["python", "manage.py", "makemigrations"] + args)


def cmd_i18n(args):
    """Extract and compile translation strings.

    Usage:
      ./dev.py i18n                # extract + compile (default)
      ./dev.py i18n makemessages   # extract only
      ./dev.py i18n compilemessages  # compile only
    """
    sub = args[0] if args else None
    if sub in (None, "makemessages"):
        result = run_docker_command(
            ["python", "manage.py", "makemessages", "-l", "de", "-l", "en", "--no-wrap"]
        )
        if result.returncode != 0:
            return result
    if sub in (None, "compilemessages"):
        result = run_docker_command(["python", "manage.py", "compilemessages"])
    return result


def cmd_runserver(args):
    """Start development server (if not already running)"""
    print("Note: Django server should already be running in the container")
    print("Use 'dev.py logs -f' to view server output")
    return subprocess.CompletedProcess(args=[], returncode=0)


def cmd_quality(args):
    """Run code quality checks (ruff format, ruff lint, Tailwind CSS build, tests)

    Options:
        --no-tests: Skip test execution
        --only-format: Run only ruff format + ruff lint
        --only-tests: Run only tests
        --verbose: Show full output (default: minimal)

    Note: vulture and mypy are skipped by default due to many false positives.
          Run them manually if needed:
            docker exec my-practice-django python -m vulture my_practice
            docker exec my-practice-django python -m mypy my_practice
    """
    results = []
    verbose = "--verbose" in args
    run_tests = "--no-tests" not in args
    only_format = "--only-format" in args
    only_tests = "--only-tests" in args

    # Determine which checks to run
    run_format = not only_tests
    run_tests = run_tests and not only_format

    print("🔍 Code Quality Checks")
    print("=" * 50)
    if not verbose:
        print("💡 Use --verbose for full output")
    print()

    # Ruff format check
    if run_format:
        print("1️⃣  Ruff format (code formatter)")
        print("-" * 30)
        cmd = ["python", "-m", "ruff", "format", ".", "--check"]
        if not verbose:
            cmd.append("--quiet")
        fmt_result = run_docker_command(cmd)
        if fmt_result.returncode == 0:
            print("✅ Ruff format OK")
            results.append(("Ruff format", 0))
        else:
            print("❌ Code needs formatting")
            if not verbose:
                print("   Run: ./dev.py format")
            results.append(("Ruff format", 1))
        print()

    # Ruff linter
    if run_format:
        print("2️⃣  Ruff lint")
        print("-" * 30)
        cmd = ["python", "-m", "ruff", "check", "."]
        if not verbose:
            cmd.extend(["--quiet"])
        ruff_result = run_docker_command(cmd)
        results.append(("Ruff lint", ruff_result.returncode))
        if ruff_result.returncode == 0:
            print("✅ Ruff lint passed")
        else:
            print("❌ Ruff found issues")
            if not verbose:
                print("   Run with --verbose to see details")
        print()

    # Tailwind CSS build
    if run_format:
        print("3️⃣  Tailwind CSS build")
        print("-" * 30)
        css_result = run_docker_command(["npm", "run", "build:css"])
        results.append(("Tailwind CSS", css_result.returncode))
        if css_result.returncode == 0:
            print("✅ Tailwind CSS built")
        else:
            print("❌ Tailwind CSS build failed")
        print()

    # Django tests (optional)
    if run_tests:
        print("4️⃣  Django Tests")
        print("-" * 30)

        # Note: Using --keepdb to reuse test database between runs
        cmd = ["python", "manage.py", "test", "my_practice", "--keepdb"]
        if not verbose:
            cmd.append("--verbosity=1")
        test_result = run_docker_command(cmd)
        results.append(("Tests", test_result.returncode))
        print()
    else:
        print("4️⃣  Django Tests")
        print("-" * 30)
        print("⏭️  Skipped (--no-tests flag)")
        print()

    # Summary
    print()
    print("=" * 50)
    print("Quality Check Summary:")
    print("=" * 50)
    for name, code in results:
        status = "✅ PASSED" if code == 0 else "❌ FAILED"
        print(f"{name:<20} {status}")
    print("=" * 50)

    if not results:
        print("⚠️  No checks were run")
        print("   Use --only-format or --only-tests")
        return subprocess.CompletedProcess(args=[], returncode=0)

    # Return overall status
    overall_status = 0 if all(code == 0 for _, code in results) else 1
    if overall_status == 0:
        print("✅ All checks passed")
    else:
        print("❌ Some checks failed")
        if not verbose:
            print("\n💡 Tip: Run with --verbose to see detailed output")
    return subprocess.CompletedProcess(args=[], returncode=overall_status)


def _print_outdated_dev_packages():
    """Print outdated host packages that appear in requirements-dev.txt."""
    import json
    import re

    dev_req = os.path.join(os.path.dirname(__file__), "app", "requirements-dev.txt")
    try:
        with open(dev_req) as f:
            # Extract bare package names, normalise to lowercase with hyphens
            dev_names = set()
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                name = re.split(r"[>=<!;\[]", line)[0].strip().lower().replace("_", "-")
                if name:
                    dev_names.add(name)
    except FileNotFoundError:
        print("  (requirements-dev.txt not found)")
        return

    cmd = []
    if needs_flatpak():
        cmd.extend(["flatpak-spawn", "--host"])
    cmd.extend(["pip3", "list", "--outdated", "--format", "json"])
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0 or not result.stdout.strip():
        print("  (could not run pip3 on host)")
        return

    try:
        packages = json.loads(result.stdout)
    except json.JSONDecodeError:
        print("  (failed to parse pip3 output)")
        return

    relevant = [
        p for p in packages
        if p["name"].lower().replace("_", "-") in dev_names
    ]
    if relevant:
        print(f"  {'Package':<30} {'Version':<16} {'Latest':<16} Type")
        print(f"  {'-'*30} {'-'*16} {'-'*16} ----")
        for p in relevant:
            print(f"  {p['name']:<30} {p['version']:<16} {p['latest_version']:<16} {p['latest_filetype']}")
    else:
        print("  All dev packages up to date")


def cmd_review(args):
    """Periodic codebase health review (monthly/quarterly).

    Runs automated checks and prints the manual checklist.

    Options:
        --full      Quarterly mode: also runs complexity analysis (radon)
        --verbose   Show full tool output instead of summaries
        --no-tests  Skip the test-coverage step (faster, no DB required)
        -h, --help  Show this help message
    """
    if "-h" in args or "--help" in args:
        print("Usage: ./dev.py review [--full] [--verbose] [--no-tests]")
        print()
        print("Options:")
        print("  --full      Quarterly mode: adds radon complexity analysis")
        print("  --verbose   Show full tool output instead of summaries")
        print("  --no-tests  Skip the test-coverage step (faster, no DB required)")
        print("  -h, --help  Show this help message")
        return subprocess.CompletedProcess(args=[], returncode=0)

    full = "--full" in args
    verbose = "--verbose" in args
    no_tests = "--no-tests" in args
    results = []

    mode = "Quarterly" if full else "Monthly"
    print(f"🔬 Codebase Health Review — {mode}")
    print("=" * 55)
    if not verbose:
        print("💡 Use --verbose for full tool output")
    print()

    # --- 1. Dead code (vulture) ---
    print("1️⃣  Dead code (vulture)")
    print("-" * 30)
    vulture_result = run_docker_command(
        ["python", "-m", "vulture", "my_practice", "--min-confidence", "80"]
    )
    results.append(("Dead code (vulture)", vulture_result.returncode))
    if vulture_result.returncode == 0:
        print("✅ No dead code found")
    else:
        print("⚠️  Potential dead code above")
    print()

    # --- 2. Unused imports / variables (ruff F401/F841) ---
    print("2️⃣  Unused imports & variables (ruff)")
    print("-" * 30)
    ruff_cmd = ["python", "-m", "ruff", "check", ".", "--select", "F401,F841"]
    if not verbose:
        ruff_cmd.append("--quiet")
    ruff_result = run_docker_command(ruff_cmd)
    results.append(("Unused symbols (ruff)", ruff_result.returncode))
    if ruff_result.returncode == 0:
        print("✅ No unused imports or variables")
    else:
        print("⚠️  Unused symbols found above")
    print()

    # --- 3. Security: known CVEs (pip-audit + npm audit) ---
    print("3️⃣  Dependency security (pip-audit + npm audit)")
    print("-" * 30)
    # Check if pip-audit is available before running
    check = run_docker_command(["python", "-c", "import pip_audit"])
    if check.returncode != 0:
        print("⏭️  pip-audit not installed — skipping Python CVE check")
        print("   Install: pip install pip-audit")
        results.append(("CVE audit (pip-audit)", None))
    else:
        audit_result = run_docker_command(
            ["python", "-m", "pip_audit", "--progress-spinner", "off"]
        )
        results.append(("CVE audit (pip-audit)", audit_result.returncode))
        if audit_result.returncode == 0:
            print("✅ No known Python CVEs")
        else:
            print("⚠️  Python vulnerabilities found above")

    npm_audit = run_docker_command(["npm", "audit", "--prefix", "/app"])
    results.append(("CVE audit (npm audit)", npm_audit.returncode))
    if npm_audit.returncode == 0:
        print("✅ No known JS CVEs")
    else:
        print("⚠️  JS vulnerabilities found above")
    print()

    # --- 4. Outdated packages ---
    print("4️⃣  Outdated packages (pip list --outdated)")
    print("-" * 30)
    print("App (container / requirements.txt):")
    run_docker_command(["pip", "list", "--outdated", "--format", "columns"])
    print("Dev tools (host / requirements-dev.txt):")
    _print_outdated_dev_packages()
    results.append(("Outdated packages", 0))  # informational only
    print()

    # --- 5. Test coverage ---
    print("5️⃣  Test coverage (coverage report)")
    print("-" * 30)
    if no_tests:
        print("⏭️  Skipped (--no-tests)")
        results.append(("Coverage", None))
    else:
        run_docker_command([
            "python", "-m", "coverage", "run",
            "--source=my_practice",
            "manage.py", "test", "my_practice", "--keepdb", "--verbosity=0",
        ])
        cov_cmd = [
            "python", "-m", "coverage", "report",
            "--skip-covered",
            "--skip-empty",
            "--omit=*/migrations/*,*/tests/*",
        ]
        if not verbose:
            cov_cmd.extend(["--sort=miss"])
        cov_result = run_docker_command(cov_cmd)
        results.append(("Coverage", cov_result.returncode))
    print()

    # --- 6. Complexity (quarterly only) ---
    if full:
        print("6️⃣  Complexity hotspots (radon cc)")
        print("-" * 30)
        check = run_docker_command(["python", "-c", "import radon"])
        if check.returncode != 0:
            print("⏭️  radon not installed in container — skipping complexity check")
            print("   Rebuild the container to install it: ./dev.py build")
            results.append(("Complexity (radon)", None))
        else:
            radon_result = run_docker_command([
                "python", "-m", "radon", "cc", "my_practice",
                "--min", "C",   # C = complex, D/E/F = very complex
                "--show-complexity",
                "--average",
            ])
            results.append(("Complexity (radon)", radon_result.returncode))
        print()

    # --- Summary ---
    print("=" * 55)
    print("Automated Check Summary:")
    print("=" * 55)
    for name, code in results:
        status = "⏭️  Skipped" if code is None else ("✅ OK" if code == 0 else "⚠️  Review")
        print(f"  {name:<30} {status}")
    print()

    # --- Manual checklist ---
    print("=" * 55)
    print(f"Manual Checklist — {mode}:")
    print("=" * 55)
    monthly_items = [
        "git log: repeated fixes in same area? (design smell)",
        "German comments/identifiers in touched files? (P-038)",
        "GH issues: close stale items inactive >2 months",
        "New views bypassing mixins/builders? Consolidate",
    ]
    quarterly_items = [
        "Similar blocks across views/utils? Extract a helper",
        "Django/Python/WeasyPrint/psycopg major versions?",
        "New builder/helper patterns followed by recent code?",
        "PROJECTS.md: stale WIPs → done/cancelled?",
        "docs/architecture/CODE_STRUCTURE.md still accurate?",
        "New language features that simplify existing code?",
    ]
    for item in monthly_items:
        print(f"  [ ] {item}")
    if full:
        print()
        print("  Quarterly extras:")
        for item in quarterly_items:
            print(f"  [ ] {item}")
    print()
    print("See docs/guides/CODEBASE_STANDARDS.md for the full scan checklist and canonical patterns.")

    return subprocess.CompletedProcess(args=[], returncode=0)


def cmd_format(args):
    """Format code with ruff format (Black-compatible formatter only).

    Note: does NOT run ruff check --fix. Auto-fixing lint rules can silently
    introduce syntax regressions (e.g. UP034 stripping parens from
    `except (A, B):` → Python 2 syntax). Use `./dev.py quality` to review
    lint issues and fix them manually.
    """
    print("🎨 Formatting code with ruff...")
    return run_docker_command(["python", "-m", "ruff", "format", "."])


def cmd_calendar_auth(_args):
    """Open the Google Calendar authorization URL in the default browser.

    Use this when the calendar token has expired (invalid_grant error).
    The browser handles the full OAuth2/PKCE flow and saves the new token.
    The app must be running (./dev.py start) before calling this.
    """
    url = "http://localhost:8000/calendar/authorize/"
    print(f"Opening {url} in your browser...")
    print("Complete the Google sign-in to refresh the calendar token.")
    result = run_host_command(["xdg-open", url])
    if result.returncode != 0:
        print(f"xdg-open failed. Open this URL manually in your browser:\n  {url}")
    return result


def cmd_install_hooks(_args):
    """Configure git to use the committed .githooks/ directory.

    Run once after cloning. The pre-commit hook auto-formats staged Python
    files with ruff before each commit (uses host ruff, no Docker needed).
    """
    result = subprocess.run(
        ["git", "config", "core.hooksPath", ".githooks"],
        cwd=os.path.dirname(os.path.abspath(__file__)),
    )
    if result.returncode == 0:
        print("✅ Git hooks installed — .githooks/pre-commit will run on every commit.")
        print("   To skip the hook for one commit: git commit --no-verify")
    return result


def cmd_run(args):
    """Run a Python script in the container with Django environment loaded"""
    if not args:
        print("Error: Please specify a Python script to run")
        print("Example: ./dev.py run check_df.py")
        return subprocess.CompletedProcess(args=[], returncode=1)

    script_path = args[0]

    # Check if script exists
    if not os.path.exists(script_path):
        print(f"Error: Script not found: {script_path}")
        return subprocess.CompletedProcess(args=[], returncode=1)

    # Read script content
    with open(script_path, "r") as f:
        script_content = f.read()

    # Execute via Django shell with script content
    cmd = []
    if needs_flatpak():
        cmd.extend(["flatpak-spawn", "--host"])

    cmd.extend(["docker", "exec", "-i", CONTAINER_NAME, "python", "manage.py", "shell"])

    result = subprocess.run(cmd, input=script_content.encode(), capture_output=False)
    return result


def cmd_exec(args):
    """Execute arbitrary command in container"""
    if not args:
        print("Error: Please specify a command to execute")
        print("Example: ./dev.py exec ls -la")
        return subprocess.CompletedProcess(args=[], returncode=1)

    return run_docker_command(args)


def cmd_sql(args):
    """Execute SQL query in PostgreSQL database"""
    if not args:
        print("Error: Please specify SQL query or file")
        print("Examples:")
        print('  ./dev.py sql "SELECT * FROM my_practice_client LIMIT 5"')
        print("  ./dev.py sql query.sql")
        return subprocess.CompletedProcess(args=[], returncode=1)

    query = args[0]

    # Check if it's a file
    if os.path.exists(query):
        with open(query, "r") as f:
            query = f.read()

    # Execute SQL via psql
    cmd = []
    if needs_flatpak():
        cmd.extend(["flatpak-spawn", "--host"])

    cmd.extend(
        [
            "docker",
            "exec",
            "-i",
            CONTAINER_NAME,
            "psql",
            "-U",
            "my_practice",
            "-d",
            "my_practice",
            "-c",
            query,
        ]
    )

    return subprocess.run(cmd)


def cmd_psql(args):
    """Open interactive PostgreSQL shell"""
    print("Opening PostgreSQL shell...")
    return run_docker_command(
        ["psql", "-U", "my_practice", "-d", "my_practice"], interactive=True
    )


COMMANDS = {
    "build": cmd_build,
    "start": cmd_start,
    "stop": cmd_stop,
    "restart": cmd_restart,
    "test": cmd_test,
    "test-js": cmd_test_js,
    "manage": cmd_manage,
    "python": cmd_python,
    "shell": cmd_shell,
    "bash": cmd_bash,
    "logs": cmd_logs,
    "ps": cmd_ps,
    "migrate": cmd_migrate,
    "makemigrations": cmd_makemigrations,
    "i18n": cmd_i18n,
    "runserver": cmd_runserver,
    "quality": cmd_quality,
    "review": cmd_review,
    "format": cmd_format,
    "calendar-auth": cmd_calendar_auth,
    "install-hooks": cmd_install_hooks,
    "run": cmd_run,
    "exec": cmd_exec,
    "sql": cmd_sql,
    "psql": cmd_psql,
}


def print_help():
    """Print usage information"""
    print("Usage: dev.py <command> [args...]")
    print("\nAvailable commands:")
    print("  start                - Start all containers (compose up -d)")
    print("  stop                 - Stop all containers (compose down)")
    print("  build [--no-cache]   - Rebuild Docker image(s)")
    print(
        "  restart [--force]    - Restart the Django container (--force: full down/up)"
    )
    print("  test [args]          - Run tests (default: Django + JS)")
    print("  test --js-only       - Run only JavaScript tests (Node.js + browser info)")
    print("  test --django-only   - Run only Django tests")
    print("  test-js              - Run JavaScript tests (Node.js-based)")
    print("  test-js --browser    - Show browser test instructions")
    print("  test-js --node       - Run only Node.js tests (skip browser info)")
    print("  manage <cmd> [args]  - Run Django management commands")
    print("  python [args]        - Run Python in the container")
    print('  shell [-c "cmd"]     - Open Django shell or execute command with -c')
    print("  bash                 - Open bash shell in container")
    print("  run <script>         - Run a Python script with Django environment")
    print("  exec <cmd> [args]    - Execute arbitrary command in container")
    print("  sql <query|file>     - Execute SQL query or file")
    print("  psql                 - Open interactive PostgreSQL shell")
    print(
        "  logs [args]          - Show container logs (default: all services, last 100 lines)"
    )
    print("  ps                   - Show container status")
    print("  migrate [args]       - Run migrations")
    print("  makemigrations [args]- Create new migrations")
    print("  i18n [sub]           - Extract/compile translations (makemessages + compilemessages)")
    print("  runserver            - Info about development server")
    print("  quality              - Run code quality checks (ruff format, ruff lint, Tailwind CSS, tests)")
    print("  quality --no-tests   - Run quality checks without tests")
    print("  quality --only-format - Run only formatting checks (ruff format + ruff lint)")
    print("  quality --only-tests - Run only tests")
    print("  quality --verbose    - Show full output from all tools")
    print("  review               - Monthly codebase health check (dead code, CVEs, coverage)")
    print("  review --full        - Quarterly review (adds complexity analysis)")
    print("  review --verbose     - Show full tool output during review")
    print(
        "  format               - Auto-format code with ruff format + ruff check --fix"
    )
    print("  calendar-auth        - Open Google Calendar auth URL in browser (re-authorize expired token)")
    print("  install-hooks        - Configure git to use .githooks/ (run once after clone)")
    print("\nExamples:")
    print("  ./dev.py start                                # Start all containers")
    print("  ./dev.py start --build                        # Rebuild and start")
    print("  ./dev.py build                                # Rebuild image (cached)")
    print("  ./dev.py build --no-cache                     # Full rebuild (no cache)")
    print(
        "  ./dev.py restart --force                      # Full restart (reloads .env)"
    )
    print("  ./dev.py restart --force --build              # Rebuild + full restart")
    print("  ./dev.py stop                                 # Stop all containers")
    print("  ./dev.py stop -v                              # Stop and remove volumes")
    print("  ./dev.py ps                                   # Show container status")
    print("  ./dev.py logs -f                              # Follow all logs")
    print("  ./dev.py logs --tail 50 django                # Last 50 lines of Django")
    print("  ./dev.py test                                 # Run all tests")
    print("  ./dev.py test --django-only                   # Run only Django tests")
    print("  ./dev.py test --js-only                       # Run only JavaScript tests")
    print(
        "  ./dev.py test-js                              # Run Node.js JS tests + browser info"
    )
    print("  ./dev.py test-js --node                       # Run only Node.js tests")
    print(
        "  ./dev.py test-js --browser                    # Show browser test instructions"
    )
    print("  ./dev.py test my_practice.tests.test_imports # Run specific tests")
    print("  ./dev.py manage createsuperuser               # Create superuser")
    print("  ./dev.py shell                                # Open Django shell")
    print(
        "  ./dev.py shell -c \"print('Hello')\"            # Execute command in Django shell"
    )
    print(
        "  ./dev.py run check_df.py                      # Run Python script with Django"
    )
    print(
        "  ./dev.py exec ls -la /app                     # Execute command in container"
    )
    print('  ./dev.py sql "SELECT COUNT(*) FROM ..."       # Execute SQL query')
    print("  ./dev.py psql                                 # Open PostgreSQL shell")
    print("\nNote: Automatically uses flatpak-spawn when running in VS Code")


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ["-h", "--help", "help"]:
        print_help()
        return 0

    command = sys.argv[1]
    args = sys.argv[2:]

    if command not in COMMANDS:
        print(f"Unknown command: {command}")
        print("")
        print_help()
        return 1

    result = COMMANDS[command](args)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
