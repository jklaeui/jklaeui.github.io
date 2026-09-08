# Layout mockup

Static, standalone copy of the site for playing with the layout. **Nothing here is
published** — Jekyll ignores folders starting with `_` that aren't its own.

## How to look at it

Just open the file:

```bash
open _mockup/index.html
```

(or serve it: `python3 -m http.server 8000` from the repo root, then
<http://localhost:8000/_mockup/>)

Assets are referenced with `../` so the real photo, fonts, CV and report load
straight from the repo.

## What's different from the live site

- **Wide header band** (`<header class="hero">`), full nav-bar width: `syndi1.PNG`
  on the left, intro paragraph + "I am on the 2026-2027 job market." + the contact
  block on the right. Not sticky, scrolls away with the page.
- **No sidebar** — content below the header runs at `--content-width` (760px,
  was ~550px).
- **Research split into three subsections** (`h3.subsection`): Job market paper /
  Working papers and advanced projects / Work in progress.

## Knobs

Top of `style.css`, in `:root`:

| variable | does |
|---|---|
| `--page-width` | outer container width (matches nav bar) |
| `--content-width` | width of the text column below the header |
| `--photo-share` | how much of the header the photo takes |
| `--hero-gap` | space between photo and header text |

## Porting back

- `_mockup/style.css` → the `.hero*`, `.main-wrapper`, `.content`, `h3.subsection`
  rules go into `_sass/jekyll-theme-minimal.scss`.
- The header markup replaces the `<aside class="sidebar">` block in
  `_layouts/default.html`; `site.logo` in `_config.yml` becomes `syndi1.PNG`.
- The intro paragraph moves out of `index.md` into the layout.
- `syndi1.PNG` is 1.8 MB — resize/convert before it goes live.
