# Release Checklist

## Version strings — update all three

| File | What to change |
|------|---------------|
| `app/my_practice/version.py` | `VERSION = "vX.Y.Z"` |
| `prod.py` | `VERSION = "vX.Y.Z"` (line ~15) |
| `docker-compose.prod.yml` | `image: ghcr.io/dholbach/my-practice:vX.Y.Z` |

All three must match. `prod.py` constructs download URLs and the image pull from `VERSION`; `docker-compose.prod.yml` pins what self-hosters actually run.

## Docs pass

- [ ] `docs/CHANGELOG.md` — add release section with highlights
- [ ] `docs/FEATURES.md` — add user-facing additions under the right section
- [ ] `PROJECTS.md` — update Recent Activity, cap at 2 entries

## Git

```bash
# Commit the version bumps
git add app/my_practice/version.py prod.py docker-compose.prod.yml docs/
git commit -m "chore: bump version to vX.Y.Z"

# Tag — this triggers the GitHub Actions image build (image.yml)
git tag vX.Y.Z
git push origin main
git push origin vX.Y.Z
```

The `image.yml` workflow fires on `push` to `v*` tags and builds
`linux/amd64` + `linux/arm64` images, pushing both a versioned tag and `:latest`.

## GitHub Release

Create a release at https://github.com/dholbach/my-practice/releases/new
(or via `gh release create vX.Y.Z`).

This is required: `./prod.py update` queries the GitHub Releases API
(`/releases/latest`) to detect newer versions. A bare git tag is not enough.

```bash
gh release create vX.Y.Z --title "vX.Y.Z" --notes "See docs/CHANGELOG.md"
```

## Verify

- [ ] Image appears at `ghcr.io/dholbach/my-practice:vX.Y.Z` (check Actions tab)
- [ ] `./prod.py update` on an older install reports the new version
- [ ] `./prod.py setup` on a clean directory pulls the correct versioned image
