---
name: lit
description: Literature library and reference lookups. (1) Build and update the index of a PDF library in Dropbox that the library web page (jklaeui.github.io/library) reads; (2) add PDFs, appendices and versions; (3) look up papers, citing papers and references on OpenAlex, build BibTeX entries, and check a .bib file. Use for "build/update the library", "index the inbox", "add this paper", "who cites X", "bib entry for X", "check my bibliography".
argument-hint: "[update the library | add <pdf> | find <paper> | cites <paper> | bib <paper> | check <bib>]"
allowed-tools: Bash, Read, WebSearch, WebFetch
---

# lit: PDF library and references

Scripts (run with `python3`):
- `~/.claude/skills/lit/library.py`: the library index (`--help` lists commands).
- `~/.claude/skills/lit/lit.py`: OpenAlex lookups and the reference check.

Settings: `~/.config/lit/config.json`, written by `library.py setup`. Optional free OpenAlex key in `~/.config/openalex/api_key` (create it at openalex.org/settings/api); without a key, OpenAlex allows about 100 requests a day. Responses are cached in `~/.claude/skills/lit/cache/`.

Requirements: Python 3 with `requests`, `beautifulsoup4`, `lxml`; `pdftotext`/`pdfinfo` (poppler: `brew install poppler`). The library folder must be inside the Dropbox folder on this computer, so that the web page sees the same files.

## First time

1. `python3 ~/.claude/skills/lit/library.py setup --folder "<path to the PDF folder inside Dropbox>" [--email you@example.org]`
2. `python3 library.py sync` reads every PDF: DOI on page 1, NBER/arXiv numbers, title, then OpenAlex; abstract and JEL codes from the PDF. Identical copies are listed, never deleted.
3. `python3 library.py verify` flags entries whose title and authors are not in their PDF (wrong matches on short titles).
4. `python3 library.py review -n 20` shows flagged papers with their page-1 text. Identify them (page 1, OpenAlex `lit.py find`, the author's website) and fix them in one call with `apply` (below).
5. `python3 library.py jel` reads printed JEL codes. For papers without codes, choose 2-4 three-character codes from `jel.json` based on title and abstract and set them with `apply` (`"jel": [...]`).
6. Tell the user to reload the web page.

## Update the library (after uploads from the page)

Uploads land in `<library>/_inbox/`. Run `library.py inbox` (identifies, renames, indexes, ticks off the to-download list), then `sync` (files put into the folder directly), `verify`, `review`, `jel` as above. Report what came in.

## Corrections: `apply`

```
python3 library.py apply <<'EOF'
[{"file": "w21655.pdf", "doi": "10.3386/w21655", "lookup": true},
 {"file": "draft.pdf", "title": "...", "authors": ["Family, Given", "Family, Given"], "year": 2026, "venue": "Mimeo", "ok": true},
 {"file": "paper_nber.pdf", "merge_with": "paper_journal.pdf", "label": "NBER WP 2023"},
 {"file": "appendix.pdf", "merge_with": "paper_journal.pdf", "label": "Online appendix"},
 {"file": "paper_journal.pdf", "main": true},
 {"file": "x.pdf", "jel": ["J64", "J65"]},
 {"file": "x.pdf", "notes": "my note"}]
EOF
```

`lookup` refetches from OpenAlex by `doi` or `title`; `ok` clears the review flag; `merge_with` makes a file another version of a paper; `main` makes it the PDF the page opens first; `split` makes a file its own paper; `label` names a version on the page.

Other commands: `add <pdf>...` (move PDFs into the library and index them), `attach <pdf> --to <paper> --label "Online appendix"`, `rename <file>`, `want "Title" --authors .. --venue .. --year ..` / `wanted` (the to-download list on the page), `notes` (import notes from a ReadCube CSV export), `stats`.

Rules: never delete PDFs; move broken or duplicate files to the Trash only after asking. Keep the user's notes; append, never overwrite.

## Lookups

```
python3 lit.py search "monopsony job search"
python3 lit.py find "The Measure of Monopsony" --author Langella
python3 lit.py cites "The Persistence of Local Joblessness" -n 25
python3 lit.py refs 10.1257/aer.20160575
python3 lit.py bib 10.1093/qje/qjab008
python3 lit.py check references.bib --tex main.tex --out report.md
```

For working papers, the authors' websites are usually more current than OpenAlex: store a homepage with `lit.py site-add "Name" URL`, then `lit.py site "Name" "Title"` shows the paper's entry and status there. `check` uses stored sites automatically.
