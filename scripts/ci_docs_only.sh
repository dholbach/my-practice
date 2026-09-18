#!/bin/bash
# Decide whether a CI job can skip its expensive steps, and write the answer to
# $GITHUB_OUTPUT as `code=true|false`.
#
# This lives in a script rather than inline in ci.yml because every job needs
# the same answer, and the two inline copies it replaced had to be edited in
# lockstep. It is deliberately NOT a separate `changes` job feeding the others
# via `needs:` — `lint` and `test` are required status checks on main's ruleset
# with no bypass actors, and making them depend on another job means a failure
# upstream leaves them skipped rather than red, which is a far less obvious
# state to debug on a blocked PR.
#
# Pushes to main are never skipped: main must stay fully verified regardless of
# what a PR was allowed to skip.
#
# Environment:
#   EVENT_NAME     github.event_name
#   BASE_SHA       github.event.pull_request.base.sha (pull_request only)
#   HEAD_SHA       github.event.pull_request.head.sha (pull_request only)
#   GITHUB_OUTPUT  set by the runner
set -euo pipefail

if [ "${EVENT_NAME:-}" != "pull_request" ]; then
    echo "Not a pull request — running everything."
    echo "code=true" >>"$GITHUB_OUTPUT"
    exit 0
fi

# A leading `.` is required: a pathspec of only :(exclude) patterns matches
# nothing. Plain `*` spans `/` in a git pathspec, so `*.md` covers Markdown at
# any depth, not just the repo root.
if git diff --quiet "$BASE_SHA" "$HEAD_SHA" \
    -- . ':(exclude)docs/**' ':(exclude)*.md'; then
    echo "Docs-only change — skipping the expensive steps."
    echo "code=false" >>"$GITHUB_OUTPUT"
else
    echo "Code changed — running everything."
    echo "code=true" >>"$GITHUB_OUTPUT"
fi
