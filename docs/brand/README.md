# Logo

Source files for the my-practice logo: a mark (two connected points) and the
"my-practice" wordmark lockup. `-light` files are for light backgrounds,
`-dark` files for dark ones.

| File | Used for |
| --- | --- |
| `logo/favicon.svg` | Browser tab icon — copied to `app/static/img/favicon.svg` |
| `logo/favicon-32.png` | PNG fallback icon and the `/favicon.ico` redirect — `app/static/img/favicon-32.png` |
| `logo/app-icon-180.png` | Apple touch icon — `app/static/img/apple-touch-icon.png` |
| `logo/lockup-light.svg`, `logo/lockup-dark.svg` | README header (switches with the GitHub theme) |
| `logo/app-icon.svg`, `logo/app-icon-192.png`, `logo/app-icon-512.png` | App icons, for a web app manifest if one is added |
| `logo/mark-light.svg`, `logo/mark-dark.svg`, `*-512.png` | The mark on its own (slides, social previews) |
| `logo/favicon-16.png` | 16px raster, for places that cannot scale the SVG |

The app serves copies under `app/static/img/` rather than these files, so
static files stay self-contained in the Docker image. Update both when the logo
changes. The SVGs carry their C2PA provenance manifest in `<metadata>`; leave it
in place.
