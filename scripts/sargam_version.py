"""
Single source of the Sargam font family version, shared by all four builds
(Lato-Sargam, Mukta-Sargam, Mukta-Sargam-Hindi, Mukta-Sargam-Punjabi).

Versioning rules:
  major — what you TYPE changes (the input encoding: M = tivra, ,S = mandra…)
  minor — visual design changes (mark shapes, spacing, spelling of swaras)
  patch — fixes that don't change the intended design

Published filenames carry MAJOR.MINOR plus a per-build counter, e.g.
Lato-Sargam-Bold-3.0-24.woff2. The counter exists only to defeat browser
caching of file:// URLs (see bump_preview_cache_buster).
"""
import re
import shutil

VERSION = '3.0.0'

_major, _minor, _patch = (int(x) for x in VERSION.split('.'))
SHORT = f'{_major}.{_minor}'                       # in filenames: "3.0"
FONT_REVISION = f'{_major}.{_minor}{_patch:02d}'   # head/name style: "3.000"


def stamp_version(font):
    """Write VERSION into head.fontRevision and the name table's version
    (ID 5) and unique-ID (ID 3) strings, replacing whatever the source
    font carried (e.g. Lato v1's 'Version 1.104')."""
    font['head'].fontRevision = float(FONT_REVISION)
    name = font['name']
    ps_name = name.getDebugName(6) or name.getDebugName(4) or 'Sargam'
    for rec in name.names:
        if rec.nameID == 5:
            rec.string = f'Version {FONT_REVISION}; Sargam {VERSION}'
        elif rec.nameID == 3:
            rec.string = f'{FONT_REVISION};{ps_name}'


def set_family_name(font, family):
    """Rename a derived font so it doesn't collide with its source (or with
    the other Sargam builds) when installed: family 'Mukta Sargam Hindi',
    full name 'Mukta Sargam Hindi Bold', PostScript 'MuktaSargamHindi-Bold'.
    The style (Regular/Bold) is kept from the source's name ID 2."""
    name = font['name']
    style = name.getDebugName(2) or 'Regular'
    ps = f"{family.replace(' ', '')}-{style.replace(' ', '')}"
    for rec in name.names:
        if rec.nameID == 1:
            rec.string = family
        elif rec.nameID == 4:
            rec.string = f'{family} {style}'
        elif rec.nameID == 6:
            rec.string = ps
    name.names = [r for r in name.names if r.nameID not in (16, 17)]


def bump_preview_cache_buster(preview, out_dir, family):
    """Copy the canonical out/<family>[-Bold].woff(2) files to versioned
    names (<family>[-Bold]-<SHORT>-<N>.woff2 etc.) and rewrite the preview
    HTML to point at them. Safari aggressively caches file:// resources by
    URL path and ignores query strings, so making the URL path itself
    unique each build is the only reliable cache miss without manual
    intervention. Old versioned files are deleted; the canonical files
    stay put for deploy.sh.

    Also migrates older naming (Lato-Sargam-v2-Bold-23, Mukta-Sargam-12)."""
    if not preview.exists():
        return
    text = preview.read_text()

    # <family>[-v2][-Bold][-X.Y][-N].woff(2)[?v=…]. The family is followed
    # by '-Bold', a version, a counter or '.woff', so 'Mukta-Sargam' never
    # matches 'Mukta-Sargam-Hindi-…'.
    pattern = re.compile(re.escape(family) +
                         r'(?:-v2)?(-Bold)?(?:-\d+\.\d+)?(?:-(\d+))?\.woff(2?)(?:\?v=\d+)?')

    counters = [int(m.group(2)) for m in pattern.finditer(text) if m.group(2)]
    current = max(counters, default=0)
    next_n = (current + 1) if 0 < current < 1_000_000 else 1

    for old in out_dir.glob(f'{family}*.woff*'):
        m = pattern.fullmatch(old.name)
        if m and m.group(2):        # versioned copy; canonical has no counter
            old.unlink()

    copied = 0
    for bold in ('', '-Bold'):
        for ext in ('woff2', 'woff'):
            src = out_dir / f'{family}{bold}.{ext}'
            if src.exists():
                shutil.copy(src, out_dir / f'{family}{bold}-{SHORT}-{next_n}.{ext}')
                copied += 1

    def replace(match):
        bold = match.group(1) or ''
        ext  = match.group(3)
        return f'{family}{bold}-{SHORT}-{next_n}.woff{ext}'
    new_text = pattern.sub(replace, text)
    new_text = re.sub(r'<span class="version">v[\d.]+</span>',
                      f'<span class="version">v{SHORT}</span>', new_text)
    if new_text != text:
        preview.write_text(new_text)
    if copied:
        print(f"  Versioned {family} preview filenames -> -{SHORT}-{next_n} ({copied} files)")
