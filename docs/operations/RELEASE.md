# Release Checklist

## 1. Version-bump PR

Version bumps go through a PR like any other change to `main` (branch-protected — no direct commits).

**Version strings — update all three, they must match:**

| File | What to change |
|------|---------------|
| `app/my_practice/version.py` | `VERSION = "vX.Y.Z"` |
| `prod.py` | `VERSION = "vX.Y.Z"` (line ~15) |
| `docker-compose.prod.yml` | `image: ghcr.io/dholbach/my-practice:vX.Y.Z` |

`prod.py` constructs download URLs and the image pull from `VERSION`; `docker-compose.prod.yml` pins what self-hosters actually run.

**Docs pass** (same PR):

- [ ] `docs/CHANGELOG.md` — add a release section with highlights, grouped by Feature/Bug fix/Refactor/i18n/Tests/Deps (see prior entries for the style)
- [ ] `docs/FEATURES.md` — add user-facing additions under the right section
- [ ] `PROJECTS.md` — update Recent Activity, cap at 2 entries

```bash
git checkout -b chore/release-vX.Y.Z
git add app/my_practice/version.py prod.py docker-compose.prod.yml docs/ PROJECTS.md
git commit -m "chore: bump version to vX.Y.Z"
git push -u origin chore/release-vX.Y.Z
gh pr create --title "chore: bump version to vX.Y.Z" --body "..."
```

## 2. Merge, then tag

Once the version-bump PR is merged into `main`:

```bash
git checkout main && git pull --ff-only
git tag vX.Y.Z
git push origin vX.Y.Z
```

Tagging triggers the GitHub Actions image build (`image.yml`), which fires on
`push` to `v*` tags and builds `linux/amd64` + `linux/arm64` images, pushing
both a versioned tag and `:latest`.

## 3. GitHub Release with a real changelog

Required: `./prod.py update` queries the GitHub Releases API
(`/releases/latest`) to detect newer versions — a bare git tag is not enough.

Write actual release notes (pull the highlights straight from the
`docs/CHANGELOG.md` entry for this version) — not just a pointer to the file:

```bash
gh release create vX.Y.Z --title "vX.Y.Z" --notes "$(cat <<'EOF'
## Highlights
- ...
- ...

Full changelog: docs/CHANGELOG.md
EOF
)"
```

## 4. Verify

- [ ] Image appears at `ghcr.io/dholbach/my-practice:vX.Y.Z` (check Actions tab)
- [ ] `./dev.py smoke vX.Y.Z` — boots the released image with a throwaway DB and verifies migrations + login page (runs safely alongside the dev stack)
- [ ] `./prod.py update` on an older install reports the new version
- [ ] `./prod.py setup` on a clean directory pulls the correct versioned image
