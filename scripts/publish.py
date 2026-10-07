#!/usr/bin/env python3
"""
Bundle preview/ + out/ into a self-contained docs/ folder for GitHub Pages.

  docs/
    index.html          (copy of preview/index.html, with ../out/X → fonts/X)
    fonts/              (versioned .woff/.woff2 files referenced by index.html)
    OFL.txt             (combined SIL Open Font License — Lato, Mukta, Mukta Mahee)
    README.md           (one-paragraph context for the GitHub Pages site)

After any build script bumps the cache-buster filenames, re-run this script
to refresh docs/. It's idempotent and only copies the files actually referenced
by the current preview HTML (no stale versions).

To serve on GitHub Pages:
  git init && git add -A && git commit -m "initial commit"
  gh repo create sargam-font --public --source=. --push
  # Then in repo settings → Pages → Source: "Deploy from branch", folder: /docs.
"""
import re, shutil, sys
from pathlib import Path

ROOT    = Path(__file__).resolve().parent.parent
PREVIEW = ROOT / 'preview' / 'index.html'
OUT     = ROOT / 'out'
DOCS    = ROOT / 'docs'

OFL_SOURCES = [
    ('Lato (Łukasz Dziedzic, OFL)',       ROOT / 'src' / 'Lato-Sargam v1'),  # OFL not present here; cite via README
    ('Mukta (Ek Type, OFL)',              ROOT / 'src' / 'Mukta' / 'Mukta' / 'OFL.txt'),
    ('Mukta Mahee (Ek Type, OFL)',        ROOT / 'src' / 'Mukta' / 'Mukta_Mahee' / 'OFL.txt'),
]

README = """# Sargam Font Preview

Live preview: https://<your-github-username>.github.io/sargam-font/

Version 3.0. Hindustani classical sargam notation rendered through four font variants:
- **Lato-Sargam** (Latin output)
- **Mukta-Sargam** (Latin output, Mukta typeface)
- **Mukta-Sargam-Hindi** (Devanagari output)
- **Mukta-Sargam-Punjabi** (Gurmukhi output)

Type Latin sargam (`S R G m M P D N`, lowercase = komal, `X'` = tar, `,X` = mandra,
`X~` = murki, `X~~` = andolan, `(X)` = kan-sur, `[X]` = subscript) and the font
renders it as proper notation — including syllabic रे / ਰੇ for R and नी / ਨੀ for N.

Source fonts are released under the SIL Open Font License (see OFL.txt).
The sargam mark layer, OpenType lookups, and composite glyphs are added by
scripts in this repo.
"""


def main():
    if not PREVIEW.exists():
        sys.exit(f"missing {PREVIEW}")

    DOCS.mkdir(exist_ok=True)
    fonts_dir = DOCS / 'fonts'
    if fonts_dir.exists():
        shutil.rmtree(fonts_dir)
    fonts_dir.mkdir()

    html = PREVIEW.read_text()

    # Collect every ../out/<file>.woffN reference; copy each into docs/fonts/
    # and rewrite the path. This naturally picks up only what's actually
    # referenced — stale versioned files in out/ are ignored.
    referenced = set(re.findall(r"\.\./out/([A-Za-z0-9_.\-]+?\.woff2?)", html))
    if not referenced:
        sys.exit("no ../out/...woff references found in preview HTML")

    missing = []
    for fname in sorted(referenced):
        src = OUT / fname
        if not src.exists():
            missing.append(fname)
            continue
        shutil.copy2(src, fonts_dir / fname)
    if missing:
        sys.exit(f"missing fonts in out/: {missing}")

    new_html = re.sub(r"\.\./out/([A-Za-z0-9_.\-]+?\.woff2?)", r"fonts/\1", html)
    (DOCS / 'index.html').write_text(new_html)

    # Bundle the OFL.txt files we have available, with simple section headers.
    ofl_parts = []
    for label, path in OFL_SOURCES:
        if isinstance(path, Path) and path.is_file():
            ofl_parts.append(f"=== {label} ===\n\n" + path.read_text().strip())
        else:
            ofl_parts.append(f"=== {label} ===\n\n"
                             "Distributed under the SIL Open Font License v1.1. "
                             "Upstream license available from the typeface's source.")
    (DOCS / 'OFL.txt').write_text("\n\n\n".join(ofl_parts) + "\n")

    # Only write README.md if one isn't already there — preserve user edits.
    readme = DOCS / 'README.md'
    if not readme.exists():
        readme.write_text(README)

    total_kb = sum((fonts_dir / f).stat().st_size for f in referenced) // 1024
    print(f"docs/ bundled: {len(referenced)} fonts ({total_kb} KB), 1 HTML, OFL.txt")
    print(f"  → {DOCS}")


if __name__ == '__main__':
    main()
