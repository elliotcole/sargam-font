#!/usr/bin/env python3
"""
Build Mukta-Sargam from Mukta (Ek Type, OFL).

Produces a sargam-notation font from Mukta with the same conventions as
Lato-Sargam v2:
  Lowercase r/g/d/n = komal,  uppercase R/G/D/N = shuddha
  Lowercase m       = shuddha Ma,  uppercase M = tivra Ma
  S' = tar octave,  ,S = mandra octave,  'S = mandra (legacy)
  S~ = murki (flipped tilde),  S~~ = andolan (wave after letter)
  /  \\  = meend (long curved diagonals between swaras)
  (srg)  = kan sur (superscript, hugs following swara)
  [srg]  = subscript (placeholder, sub still loose)

Unlike Lato-Sargam v1 (which shipped pre-drawn komal/tivra/octave glyphs
that we just slot-swapped), Mukta is a plain Latin+Devanagari source — so
every sargam glyph is built here as a composite of `letter + mark`. The
ornament-composite generation (Step 3) and chain-context substitution
(Step 8) are the same approach as scripts/build.py.

This script currently focuses on the Roman letters. Devanagari and
Gurmukhi (via Mukta-Mahee) sargam mappings are deferred — see HANDOFF.md.
"""
import io, os, copy, math, re
from pathlib import Path
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._g_l_y_f import Glyph, GlyphComponent
from fontTools.ttLib.tables._g_l_y_f import GlyphCoordinates as _GC
from fontTools.ttLib.tables import ttProgram
from fontTools.ttLib.tables.otTables import Ligature
from fontTools.ttLib.tables import otTables as ot
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.boundsPen import ControlBoundsPen, BoundsPen

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR  = PROJECT_ROOT / 'src' / 'Mukta' / 'Mukta'
OUT_DIR  = PROJECT_ROOT / 'out'

SWARA_LETTERS = ['S', 's', 'R', 'r', 'G', 'g', 'M', 'm', 'P', 'p', 'D', 'd', 'N', 'n']
KOMAL_LETTERS = ['r', 'g', 'd', 'n']
ALIAS         = {'s': 'S', 'p': 'P'}   # lowercase that just mirrors uppercase

# All distance/size constants are in units-per-em-relative font units.
# Mukta is 1000 upem; cap height 630, x-height 468, ascender 1130, descender -532.
TIVRA_BAR_W           = 60     # vertical bar width above M (regular tivra)
TIVRA_BAR_Y_LOW       = 700    # bar bottom edge (just above cap height)
TIVRA_BAR_Y_HIGH      = 920    # bar top edge (regular tivra, plain M)

# When M is also tar (M'), the tivra bar tucks INTO the V-notch of M, with
# its tip poking slightly above cap height — leaving the regular tar-dot
# position above cap free. Imitates Lato v1's pre-drawn tar-tivra glyph.
TIVRA_BAR_W_NOTCHED   = 80     # slightly wider; sits inside the V-notch
TIVRA_BAR_Y_LOW_NOTCHED  = 520 # ~110u below cap (upper V-notch); proportional to Lato's bar
TIVRA_BAR_Y_HIGH_NOTCHED = 760 # ~130u above cap height

KOMAL_BAR_THICK   = 60     # horizontal underline thickness
KOMAL_BAR_Y_LOW   = -180   # bar bottom edge (well below baseline)
KOMAL_BAR_Y_HIGH  = -120   # bar top edge

DOT_RADIUS        = 60     # mandra/tar dot radius (drawn as a 4-curve circle)
TAR_DOT_Y         = 920    # dot center, above cap height (clears tivra bar)
MANDRA_DOT_Y      = -290   # dot center, below baseline (clears komal underline)

# Andolan wave (one shared andolan_wave glyph). Half of Lato's units.
WAVE_WIDTH    = 650
WAVE_AMP      = 100
WAVE_MID_Y    = 350
WAVE_STROKE   = 55
WAVE_HUMPS    = 4
WAVE_GAP      = 30

# Murki swoop (flipped-tilde wave, one shared murki_swoop glyph).
MURKI_WIDTH   = 360
MURKI_AMP     = 90
MURKI_MID_Y   = 400
MURKI_STROKE  = 55
MURKI_HUMPS   = 2
MURKI_GAP     = 20

# Meend slashes (replace `slash` and `backslash` with longer curved strokes).
MEEND_WIDTH   = 850
MEEND_TOP_Y   = 712
MEEND_BOT_Y   = -25
MEEND_STROKE  = 65
MEEND_BULGE   = 65

# Kan sur and subscript composites.
SUPER_SCALE   = 0.55
SUPER_DY      = 380
SUB_SCALE     = 0.55
SUB_DY        = -180
KAN_SUR_TRAIL_PULL = 45   # advance reduction on the cluster's last super letter
                          # (a proportional half of Lato's 130 overshoots for
                          # tight-bearing pairs like R+S in Mukta — 45 keeps
                          # all pairs from overlapping while still tightening)


def _make_composite(parts):
    g = Glyph()
    g.numberOfContours = -1
    g.components = []
    for name, dx, dy, scale in parts:
        c = GlyphComponent()
        c.glyphName = name
        c.x = int(round(dx))
        c.y = int(round(dy))
        c.flags = 0
        if scale != 1.0:
            c.transform = ((scale, 0), (0, scale))
        g.components.append(c)
    return g


def _flatten_glyphs(font, names):
    """Replace each named composite with plain contours, transform applied.

    Scaled composites that reference other composites (e.g. r_super → r →
    R → Ra.gm + matra) render differently across rasterizers: Windows
    doesn't scale component offsets the way Apple does when neither
    SCALED_ nor UNSCALED_COMPONENT_OFFSET is set, and its hinting of
    scaled components left kan-sur letters full-height and dropped matras.
    Flat outlines carry no offsets or instructions to disagree about.
    """
    glyf, hmtx = font['glyf'], font['hmtx']
    gs = font.getGlyphSet()
    for name in names:
        rec = DecomposingRecordingPen(gs)
        gs[name].draw(rec)
        pen = TTGlyphPen(None)
        rec.replay(pen)
        g = pen.glyph()
        g.recalcBounds(glyf)
        glyf[name] = g
        hmtx[name] = (hmtx[name][0], g.xMin if g.numberOfContours else 0)


def _make_rect(x_left, y_low, x_right, y_high):
    """Simple rectangle as a 4-point on-curve quad (CW from top-right)."""
    g = Glyph()
    g.numberOfContours = 1
    g.coordinates = _GC([
        (x_right, y_high),
        (x_right, y_low),
        (x_left,  y_low),
        (x_left,  y_high),
    ])
    g.endPtsOfContours = [3]
    g.flags = bytearray([1, 1, 1, 1])
    g.program = ttProgram.Program()
    return g


def _make_circle(cx, cy, radius):
    """4-segment circle approximation (one quadratic Bezier per quadrant)."""
    k = radius * 0.5523  # Bezier handle length for a circle quadrant
    pen = TTGlyphPen(None)
    pen.moveTo((cx + radius, cy))
    pen.qCurveTo((cx + radius, cy + k), (cx + k, cy + radius), (cx, cy + radius))
    pen.qCurveTo((cx - k, cy + radius), (cx - radius, cy + k), (cx - radius, cy))
    pen.qCurveTo((cx - radius, cy - k), (cx - k, cy - radius), (cx, cy - radius))
    pen.qCurveTo((cx + k, cy - radius), (cx + radius, cy - k), (cx + radius, cy))
    pen.closePath()
    return pen.glyph()


def _make_curved_stroke(start, apex, end, stroke_width):
    """Stroked quadratic Bezier from start through apex to end."""
    sx, sy = start;  ax, ay = apex;  ex, ey = end
    dx, dy = ex - sx, ey - sy
    length = math.hypot(dx, dy) or 1
    nx, ny = -dy / length, dx / length
    half = stroke_width / 2
    cx = 2 * ax - 0.5 * (sx + ex)
    cy = 2 * ay - 0.5 * (sy + ey)
    pen = TTGlyphPen(None)
    pen.moveTo((sx + nx * half, sy + ny * half))
    pen.qCurveTo((cx + nx * half, cy + ny * half),
                 (ex + nx * half, ey + ny * half))
    pen.lineTo((ex - nx * half, ey - ny * half))
    pen.qCurveTo((cx - nx * half, cy - ny * half),
                 (sx - nx * half, sy - ny * half))
    pen.closePath()
    return pen.glyph()


def _make_wave(width, amp, mid_y, stroke, humps, first_dir=+1):
    """Stroked sinusoid. first_dir=+1 first hump up (standard tilde),
    first_dir=-1 first hump down (flipped tilde, used for murki)."""
    half = stroke / 2
    half_period = width / humps
    pen = TTGlyphPen(None)
    pen.moveTo((0, mid_y + half))
    for i in range(humps):
        x_start = i * half_period
        x_mid   = x_start + half_period / 2
        x_end   = x_start + half_period
        sign    = first_dir if i % 2 == 0 else -first_dir
        ctrl_y  = mid_y + sign * amp + half
        pen.qCurveTo((x_mid, ctrl_y), (x_end, mid_y + half))
    pen.lineTo((width, mid_y - half))
    for i in range(humps - 1, -1, -1):
        x_start = i * half_period
        x_mid   = x_start + half_period / 2
        x_end   = x_start
        sign    = first_dir if i % 2 == 0 else -first_dir
        ctrl_y  = mid_y + sign * amp - half
        pen.qCurveTo((x_mid, ctrl_y), (x_end, mid_y - half))
    pen.closePath()
    return pen.glyph()


def modify_font(input_path: str, output_path: str):
    font = TTFont(input_path)
    glyf = font['glyf']
    hmtx = font['hmtx']
    glyph_set = font.getGlyphSet()

    def letter_ink_center_x(name):
        bp = ControlBoundsPen(glyph_set)
        glyph_set[name].draw(bp)
        if bp.bounds is None:
            return hmtx[name][0] / 2
        x0, _, x1, _ = bp.bounds
        return (x0 + x1) / 2

    def letter_ink_x_range(name):
        bp = ControlBoundsPen(glyph_set)
        glyph_set[name].draw(bp)
        if bp.bounds is None:
            return 0, hmtx[name][0]
        x0, _, x1, _ = bp.bounds
        return x0, x1

    new_glyphs = []   # list of names added; appended to glyph order at end

    # ── Step 1: Base swara glyphs ─────────────────────────────────────
    # Aliases (s ← S, p ← P): same outline. Use a deepcopy so further
    # mutations to S or P don't leak.
    for alias, src in ALIAS.items():
        glyf[alias] = copy.deepcopy(glyf[src])
        hmtx[alias] = hmtx[src]

    # Shuddha Ma takes the original M outline (lowercase m). Save it BEFORE
    # we replace M with the tivra composite — otherwise both m and M would
    # reference the tivra composite recursively.
    glyf['m'] = copy.deepcopy(glyf['M'])
    hmtx['m'] = hmtx['M']

    # Tivra mark (vertical bar above M). Drawn origin-aligned (xMin=0); the
    # M composite then translates it to sit centered above M's ink. Why
    # origin-aligned: fontTools' GlyphSet draws components after applying an
    # LSB normalization (offset = lsb − xMin). If xMin != lsb, the component
    # gets shifted unexpectedly. Keeping mark glyphs at xMin=0 with lsb=0
    # makes the normalization a no-op and the composite offset is the only
    # thing positioning the mark.
    glyf['tivra_bar'] = _make_rect(
        x_left  = 0,
        y_low   = TIVRA_BAR_Y_LOW,
        x_right = TIVRA_BAR_W,
        y_high  = TIVRA_BAR_Y_HIGH,
    )
    hmtx['tivra_bar'] = (0, 0)
    new_glyphs.append('tivra_bar')

    # Notched tivra bar for the tar variant of M (M_tar): drops INTO the
    # M's V-notch with the tip poking slightly above cap, mirroring Lato
    # v1's pre-drawn tar-tivra glyph. Leaves the regular tar-dot position
    # above cap free for the dot.
    glyf['tivra_bar_notched'] = _make_rect(
        x_left  = 0,
        y_low   = TIVRA_BAR_Y_LOW_NOTCHED,
        x_right = TIVRA_BAR_W_NOTCHED,
        y_high  = TIVRA_BAR_Y_HIGH_NOTCHED,
    )
    hmtx['tivra_bar_notched'] = (0, 0)
    new_glyphs.append('tivra_bar_notched')

    # Tivra M = m (= original M) + tivra_bar centered above. Overwrite M.
    M_x_min, M_x_max = letter_ink_x_range('M')
    M_center = (M_x_min + M_x_max) / 2
    glyf['M'] = _make_composite([
        ('m',         0, 0, 1.0),
        ('tivra_bar', round(M_center - TIVRA_BAR_W / 2), 0, 1.0),
    ])
    hmtx['M'] = hmtx['m']

    # Komal underline (horizontal bar) — shared glyph, drawn once at the
    # width of N's ink (so it reads as a clear underline at small sizes).
    n_x_min, n_x_max = letter_ink_x_range('N')
    komal_bar_width = round(n_x_max - n_x_min)
    glyf['komal_bar'] = _make_rect(
        x_left  = 0,
        y_low   = KOMAL_BAR_Y_LOW,
        x_right = komal_bar_width,
        y_high  = KOMAL_BAR_Y_HIGH,
    )
    hmtx['komal_bar'] = (0, 0)
    new_glyphs.append('komal_bar')

    # Komal letters: composite of uppercase + komal_bar centered beneath.
    # The user picked "uppercase + underline" as the convention.
    upper_for = {'r': 'R', 'g': 'G', 'd': 'D', 'n': 'N'}
    for lo, up in upper_for.items():
        x0, x1 = letter_ink_x_range(up)
        center = (x0 + x1) / 2
        bar_dx = round(center - komal_bar_width / 2)
        glyf[lo] = _make_composite([
            (up,          0,      0, 1.0),
            ('komal_bar', bar_dx, 0, 1.0),
        ])
        hmtx[lo] = hmtx[up]

    # ── Step 2: Octave variants (mandra, tar) ─────────────────────────
    # Shared mandra_dot and tar_dot glyphs, drawn origin-aligned with the
    # circle CENTERED at (DOT_RADIUS, dot_y) — so xMin=0, xMax=2*DOT_RADIUS.
    # See the tivra_bar comment in Step 1 for why origin-alignment matters.
    # Each <X>_mandra / <X>_tar is a composite of the v2 letter + the dot
    # translated so the dot's center sits over the letter's ink center.
    # Because komal r/g/d/n and tivra M are themselves composites, mandra-
    # komal-r naturally inherits the komal underline, and mandra-tivra-M
    # inherits the tivra bar.
    glyf['mandra_dot'] = _make_circle(DOT_RADIUS, MANDRA_DOT_Y, DOT_RADIUS)
    glyf['tar_dot']    = _make_circle(DOT_RADIUS, TAR_DOT_Y,    DOT_RADIUS)
    hmtx['mandra_dot'] = (0, 0)
    hmtx['tar_dot']    = (0, 0)
    new_glyphs += ['mandra_dot', 'tar_dot']

    mandra_pairs = {}   # base letter → mandra glyph name
    tar_pairs    = {}   # base letter → tar glyph name
    notched_bar_dx = round(M_center - TIVRA_BAR_W_NOTCHED / 2)
    for letter in SWARA_LETTERS:
        center = letter_ink_center_x(letter)
        dot_dx = round(center - DOT_RADIUS)   # so dot center lands on letter center
        mandra_name = f'{letter}_mandra'
        tar_name    = f'{letter}_tar'
        glyf[mandra_name] = _make_composite([
            (letter,        0,      0, 1.0),
            ('mandra_dot',  dot_dx, 0, 1.0),
        ])
        hmtx[mandra_name] = hmtx[letter]
        if letter == 'M':
            # Tar of tivra M: regular tivra bar (above cap) collides with
            # the tar dot. Drop the bar into the M's V-notch instead so the
            # dot has clear space above. m + notched bar + tar dot, built
            # from scratch (not wrapping the regular M composite).
            glyf[tar_name] = _make_composite([
                ('m',                  0,              0, 1.0),
                ('tivra_bar_notched',  notched_bar_dx, 0, 1.0),
                ('tar_dot',            dot_dx,         0, 1.0),
            ])
            hmtx[tar_name] = hmtx['m']
        else:
            glyf[tar_name] = _make_composite([
                (letter,    0,      0, 1.0),
                ('tar_dot', dot_dx, 0, 1.0),
            ])
            hmtx[tar_name] = hmtx[letter]
        mandra_pairs[letter] = mandra_name
        tar_pairs[letter]    = tar_name
        new_glyphs += [mandra_name, tar_name]

    # ── Step 3: Ornament composites (murki, andolan) ──────────────────
    glyf['andolan_wave'] = _make_wave(WAVE_WIDTH, WAVE_AMP, WAVE_MID_Y,
                                      WAVE_STROKE, WAVE_HUMPS, first_dir=+1)
    hmtx['andolan_wave'] = (WAVE_WIDTH, 0)
    glyf['murki_swoop']  = _make_wave(MURKI_WIDTH, MURKI_AMP, MURKI_MID_Y,
                                      MURKI_STROKE, MURKI_HUMPS, first_dir=-1)
    hmtx['murki_swoop']  = (MURKI_WIDTH, 0)
    new_glyphs += ['andolan_wave', 'murki_swoop']

    for letter in SWARA_LETTERS:
        adv = hmtx[letter][0]
        glyf[f'{letter}_murki'] = _make_composite([
            (letter,        0, 0, 1.0),
            ('murki_swoop', adv + MURKI_GAP, 0, 1.0),
        ])
        hmtx[f'{letter}_murki'] = (adv + MURKI_GAP + MURKI_WIDTH, 0)
        glyf[f'{letter}_andolan'] = _make_composite([
            (letter,         0, 0, 1.0),
            ('andolan_wave', adv + WAVE_GAP, 0, 1.0),
        ])
        hmtx[f'{letter}_andolan'] = (adv + WAVE_GAP + WAVE_WIDTH, 0)
        new_glyphs += [f'{letter}_murki', f'{letter}_andolan']

    # ── Step 4: Redraw meend slashes ──────────────────────────────────
    mid_x = MEEND_WIDTH / 2
    mid_y = (MEEND_TOP_Y + MEEND_BOT_Y) / 2
    glyf['slash'] = _make_curved_stroke(
        start=(0, MEEND_BOT_Y),
        apex=(mid_x + MEEND_BULGE * 0.4, mid_y - MEEND_BULGE),
        end=(MEEND_WIDTH, MEEND_TOP_Y),
        stroke_width=MEEND_STROKE)
    hmtx['slash'] = (MEEND_WIDTH, 0)
    glyf['backslash'] = _make_curved_stroke(
        start=(0, MEEND_TOP_Y),
        apex=(mid_x + MEEND_BULGE * 0.4, mid_y + MEEND_BULGE),
        end=(MEEND_WIDTH, MEEND_BOT_Y),
        stroke_width=MEEND_STROKE)
    hmtx['backslash'] = (MEEND_WIDTH, 0)

    # ── Step 5: Super/sub composites (kan-sur and subscript) ──────────
    # Eligible base set = 14 swara letters + their mandra and tar variants.
    kan_sur_base = list(SWARA_LETTERS)
    for letter in SWARA_LETTERS:
        kan_sur_base.append(mandra_pairs[letter])
        kan_sur_base.append(tar_pairs[letter])

    super_pairs = {}
    sub_pairs   = {}
    super_tight_pairs = {}
    sub_tight_pairs   = {}   # sub name  → sub_tight name  (for sub TRAIL pull)
    base_tight_pairs  = {}   # base name → base_tight name (for sub LEAD pull)
    for base in kan_sur_base:
        adv = hmtx[base][0]
        glyf[f'{base}_super'] = _make_composite([(base, 0, SUPER_DY, SUPER_SCALE)])
        hmtx[f'{base}_super'] = (int(round(adv * SUPER_SCALE)), 0)
        glyf[f'{base}_sub']   = _make_composite([(base, 0, SUB_DY,   SUB_SCALE)])
        hmtx[f'{base}_sub']   = (int(round(adv * SUB_SCALE)),   0)
        # super_tight: SUPER variant with reduced advance, used as the LAST
        # super of a kan-sur cluster so the cluster ink crowds the FOLLOWING
        # swara — the cluster reads as part of the swara it leads into.
        super_adv = int(round(adv * SUPER_SCALE))
        glyf[f'{base}_super_tight'] = _make_composite([(base, 0, SUPER_DY, SUPER_SCALE)])
        hmtx[f'{base}_super_tight'] = (max(0, super_adv - KAN_SUR_TRAIL_PULL), 0)
        # sub_tight: SUB variant with reduced advance — symmetric to
        # super_tight. Used as the LAST sub of a `[...]` cluster so the
        # FOLLOWING swara is laid down earlier. Subscript reads as part
        # of the swara it leads to.
        sub_adv = int(round(adv * SUB_SCALE))
        glyf[f'{base}_sub_tight'] = _make_composite([(base, 0, SUB_DY, SUB_SCALE)])
        hmtx[f'{base}_sub_tight'] = (max(0, sub_adv - KAN_SUR_TRAIL_PULL), 0)
        # base_tight: full-size base letter with reduced advance, used as the
        # PRECEDING swara before a sub cluster (`S[r]G` → S tight against `[`).
        # Fires only when the bracket sits immediately against a swara.
        glyf[f'{base}_tight'] = _make_composite([(base, 0, 0, 1.0)])
        hmtx[f'{base}_tight'] = (max(0, adv - KAN_SUR_TRAIL_PULL), 0)
        super_pairs[base]       = f'{base}_super'
        sub_pairs[base]         = f'{base}_sub'
        super_tight_pairs[f'{base}_super'] = f'{base}_super_tight'
        sub_tight_pairs[f'{base}_sub']     = f'{base}_sub_tight'
        base_tight_pairs[base]  = f'{base}_tight'
        new_glyphs += [f'{base}_super', f'{base}_sub',
                       f'{base}_super_tight', f'{base}_sub_tight',
                       f'{base}_tight']

    # Zero-width invisible glyph for boundary marker consumption.
    invisible = Glyph(); invisible.numberOfContours = 0
    glyf['kan_sur_invisible'] = invisible
    hmtx['kan_sur_invisible'] = (0, 0)
    new_glyphs.append('kan_sur_invisible')

    # ── Update glyph order so all new glyphs are addressable ──────────
    glyph_order = font.getGlyphOrder()
    for n in new_glyphs:
        if n not in glyph_order:
            glyph_order.append(n)
    font.setGlyphOrder(glyph_order)

    # Flatten the scaled kan-sur / subscript glyphs (see _flatten_glyphs).
    _flatten_glyphs(font, [*super_pairs.values(), *sub_pairs.values(),
                           *super_tight_pairs.values(), *sub_tight_pairs.values()])

    # ── Step 6: Add GSUB ligatures ────────────────────────────────────
    # Find the 'liga' lookup; pick the first lookup type 4 referenced by liga.
    gsub = font['GSUB'].table
    liga_lookup_indices = []
    for fr in gsub.FeatureList.FeatureRecord:
        if fr.FeatureTag == 'liga':
            liga_lookup_indices.extend(fr.Feature.LookupListIndex)
    liga_type4_lookup = None
    for idx in liga_lookup_indices:
        lk = gsub.LookupList.Lookup[idx]
        if lk.LookupType == 4:
            liga_type4_lookup = lk
            break
    if liga_type4_lookup is None:
        # Mukta has 'liga' but no type-4 yet for our use; create one.
        liga_type4_lookup = ot.Lookup()
        liga_type4_lookup.LookupType = 4
        liga_type4_lookup.LookupFlag = 0
        liga_subtable = ot.LigatureSubst()
        liga_subtable.ligatures = {}
        liga_type4_lookup.SubTable = [liga_subtable]
        liga_type4_lookup.SubTableCount = 1
        new_idx = len(gsub.LookupList.Lookup)
        gsub.LookupList.Lookup.append(liga_type4_lookup)
        gsub.LookupList.LookupCount = len(gsub.LookupList.Lookup)
        for fr in gsub.FeatureList.FeatureRecord:
            if fr.FeatureTag == 'liga':
                fr.Feature.LookupListIndex.append(new_idx)
                fr.Feature.LookupCount = len(fr.Feature.LookupListIndex)

    sub = liga_type4_lookup.SubTable[0]
    if not hasattr(sub, 'ligatures') or sub.ligatures is None:
        sub.ligatures = {}

    def add_lig(first, components, target):
        sub.ligatures.setdefault(first, [])
        if any(list(l.Component) == components for l in sub.ligatures[first]):
            return
        new_lig = Ligature()
        new_lig.Component = components
        new_lig.LigGlyph = target
        new_lig.CompCount = 1 + len(components)
        sub.ligatures[first].append(new_lig)

    def add_lig_first(first, components, target):
        """Insert at start (makes longer matches win against shorter ones
        added later, since the ligature engine picks the FIRST matching rule
        in the array)."""
        sub.ligatures.setdefault(first, [])
        if any(list(l.Component) == components for l in sub.ligatures[first]):
            return
        new_lig = Ligature()
        new_lig.Component = components
        new_lig.LigGlyph = target
        new_lig.CompCount = 1 + len(components)
        sub.ligatures[first].insert(0, new_lig)

    # Tar suffix: X' → X_tar
    for letter in SWARA_LETTERS:
        add_lig(letter, ['quotesingle'], tar_pairs[letter])

    # Mandra prefix via comma: ,X → X_mandra
    for letter in SWARA_LETTERS:
        add_lig('comma', [letter], mandra_pairs[letter])

    # Mandra prefix via apostrophe (legacy 'X): ,X equivalent
    for letter in SWARA_LETTERS:
        add_lig('quotesingle', [letter], mandra_pairs[letter])

    # Andolan FIRST (longer match wins), then murki.
    for letter in SWARA_LETTERS:
        add_lig_first(letter, ['asciitilde', 'asciitilde'], f'{letter}_andolan')
        add_lig(letter, ['asciitilde'], f'{letter}_murki')

    # ── Step 7: Chain context for kan-sur and subscript ───────────────
    _glyph_idx = {g: i for i, g in enumerate(font.getGlyphOrder())}

    def _coverage(glyphs):
        cov = ot.Coverage()
        cov.glyphs = sorted(set(glyphs), key=lambda g: _glyph_idx.get(g, 1 << 30))
        return cov

    def _single_subst(mapping):
        s = ot.SingleSubst()
        s.mapping = dict(mapping)
        return s

    def _chain_ctx(backtrack, input_, lookahead, subst_records):
        s = ot.ChainContextSubst()
        s.Format = 3
        s.BacktrackCoverage   = [_coverage(g) for g in backtrack]
        s.BacktrackGlyphCount = len(backtrack)
        s.InputCoverage       = [_coverage(g) for g in input_]
        s.InputGlyphCount     = len(input_)
        s.LookAheadCoverage   = [_coverage(g) for g in lookahead]
        s.LookAheadGlyphCount = len(lookahead)
        s.SubstLookupRecord = []
        for seq, lk_idx in subst_records:
            rec = ot.SubstLookupRecord()
            rec.SequenceIndex   = seq
            rec.LookupListIndex = lk_idx
            s.SubstLookupRecord.append(rec)
        s.SubstCount = len(s.SubstLookupRecord)
        return s

    def _make_lookup(lookup_type, subtables):
        lk = ot.Lookup()
        lk.LookupType = lookup_type
        lk.LookupFlag = 0
        lk.SubTable = list(subtables)
        lk.SubTableCount = len(lk.SubTable)
        return lk

    def _add_lookup(lk):
        idx = len(gsub.LookupList.Lookup)
        gsub.LookupList.Lookup.append(lk)
        gsub.LookupList.LookupCount = len(gsub.LookupList.Lookup)
        return idx

    super_class = list(super_pairs.values())
    sub_class   = list(sub_pairs.values())
    base_class  = list(super_pairs.keys())
    super_tight_class = list(super_tight_pairs.values())
    sub_tight_class   = list(sub_tight_pairs.values())

    idx_super              = _add_lookup(_make_lookup(1, [_single_subst(super_pairs)]))
    idx_sub                = _add_lookup(_make_lookup(1, [_single_subst(sub_pairs)]))
    idx_super_to_tight     = _add_lookup(_make_lookup(1, [_single_subst(super_tight_pairs)]))
    idx_sub_to_tight       = _add_lookup(_make_lookup(1, [_single_subst(sub_tight_pairs)]))
    idx_base_to_tight      = _add_lookup(_make_lookup(1, [_single_subst(base_tight_pairs)]))
    idx_hide_paren_open    = _add_lookup(_make_lookup(1, [_single_subst({'parenleft':    'kan_sur_invisible'})]))
    idx_hide_paren_close   = _add_lookup(_make_lookup(1, [_single_subst({'parenright':   'kan_sur_invisible'})]))
    idx_hide_bracket_open  = _add_lookup(_make_lookup(1, [_single_subst({'bracketleft':  'kan_sur_invisible'})]))
    idx_hide_bracket_close = _add_lookup(_make_lookup(1, [_single_subst({'bracketright': 'kan_sur_invisible'})]))

    top_level = []
    # Super: open, continue, close (gated to swara lookahead), close-hide.
    top_level.append(_add_lookup(_make_lookup(6, [_chain_ctx(
        backtrack=[],
        input_=[['parenleft'], base_class],
        lookahead=[],
        subst_records=[(0, idx_hide_paren_open), (1, idx_super)])])))
    top_level.append(_add_lookup(_make_lookup(6, [_chain_ctx(
        backtrack=[super_class],
        input_=[base_class],
        lookahead=[],
        subst_records=[(0, idx_super)])])))
    top_level.append(_add_lookup(_make_lookup(6, [_chain_ctx(
        backtrack=[],
        input_=[super_class, ['parenright']],
        lookahead=[base_class],
        subst_records=[(0, idx_super_to_tight)])])))
    top_level.append(_add_lookup(_make_lookup(6, [_chain_ctx(
        backtrack=[super_class + super_tight_class],
        input_=[['parenright']],
        lookahead=[],
        subst_records=[(0, idx_hide_paren_close)])])))
    # Sub LEAD pull (mirror of super trail pull): when a base swara is
    # followed by '[' which is followed by another base swara, substitute
    # the base for its tight variant. This shrinks the preceding swara's
    # advance so the sub cluster is laid down closer — sub reads as part of
    # the swara it follows from. Must run BEFORE the open-sub lookup, which
    # consumes the '[' marker.
    top_level.append(_add_lookup(_make_lookup(6, [_chain_ctx(
        backtrack=[],
        input_=[base_class, ['bracketleft']],
        lookahead=[base_class],
        subst_records=[(0, idx_base_to_tight)])])))
    # Sub: open, continue, trail-pull, close.
    top_level.append(_add_lookup(_make_lookup(6, [_chain_ctx(
        backtrack=[],
        input_=[['bracketleft'], base_class],
        lookahead=[],
        subst_records=[(0, idx_hide_bracket_open), (1, idx_sub)])])))
    top_level.append(_add_lookup(_make_lookup(6, [_chain_ctx(
        backtrack=[sub_class],
        input_=[base_class],
        lookahead=[],
        subst_records=[(0, idx_sub)])])))
    # Sub TRAIL pull (mirror of super TRAIL pull): substitute the LAST sub
    # letter for its tight variant only when ']' is followed by a base
    # swara — same meend/space gating super uses. Must run BEFORE close-sub
    # consumes ']'.
    top_level.append(_add_lookup(_make_lookup(6, [_chain_ctx(
        backtrack=[],
        input_=[sub_class, ['bracketright']],
        lookahead=[base_class],
        subst_records=[(0, idx_sub_to_tight)])])))
    # Close: hide ']' whenever preceded by a sub or sub_tight. Backtrack is
    # the union — covers both the tightened case and the un-tightened case
    # (cluster followed by meend / space / other non-swara).
    top_level.append(_add_lookup(_make_lookup(6, [_chain_ctx(
        backtrack=[sub_class + sub_tight_class],
        input_=[['bracketright']],
        lookahead=[],
        subst_records=[(0, idx_hide_bracket_close)])])))

    for fr in gsub.FeatureList.FeatureRecord:
        if fr.FeatureTag == 'liga':
            existing = fr.Feature.LookupListIndex
            for idx in top_level:
                if idx not in existing:
                    existing.append(idx)
            fr.Feature.LookupCount = len(existing)

    # ── Step 8: Save ──────────────────────────────────────────────────
    buf = io.BytesIO()
    font.flavor = None
    font.save(buf)
    buf.seek(0)
    font2 = TTFont(buf)
    if output_path.endswith('.woff2'):
        font2.flavor = 'woff2'
    elif output_path.endswith('.woff'):
        font2.flavor = 'woff'
    font2.save(output_path)
    print(f"  Saved: {output_path}")


def bump_preview_cache_buster():
    """Same versioned-filename strategy as scripts/build.py — see there."""
    import shutil
    preview = PROJECT_ROOT / 'preview' / 'index.html'
    if not preview.exists():
        return
    text = preview.read_text()
    m = re.search(r'Mukta-Sargam(?:-Bold)?-(\d+)\.woff', text)
    current = int(m.group(1)) if m else 0
    next_v = (current + 1) if 0 < current < 1_000_000 else 1
    for old in OUT_DIR.glob('Mukta-Sargam-Bold-[0-9]*.woff*'):
        old.unlink()
    for old in OUT_DIR.glob('Mukta-Sargam-[0-9]*.woff*'):
        old.unlink()
    pairs = [
        ('Mukta-Sargam.woff2',      f'Mukta-Sargam-{next_v}.woff2'),
        ('Mukta-Sargam.woff',       f'Mukta-Sargam-{next_v}.woff'),
        ('Mukta-Sargam-Bold.woff2', f'Mukta-Sargam-Bold-{next_v}.woff2'),
        ('Mukta-Sargam-Bold.woff',  f'Mukta-Sargam-Bold-{next_v}.woff'),
    ]
    copied = 0
    for canonical, versioned in pairs:
        src = OUT_DIR / canonical
        if src.exists():
            shutil.copy(src, OUT_DIR / versioned)
            copied += 1
    pattern = re.compile(r'Mukta-Sargam(-Bold)?(?:-\d+)?\.woff(2?)(?:\?v=\d+)?')
    def replace(match):
        bold = match.group(1) or ''
        ext  = match.group(2)
        return f'Mukta-Sargam{bold}-{next_v}.woff{ext}'
    new_text = pattern.sub(replace, text)
    if new_text != text:
        preview.write_text(new_text)
    if copied:
        print(f"  Versioned Mukta preview filenames -> -{next_v} ({copied} files)")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    pairs = [
        ('Mukta-Regular.ttf', 'Mukta-Sargam.woff2'),
        ('Mukta-Regular.ttf', 'Mukta-Sargam.woff'),
        ('Mukta-Bold.ttf',    'Mukta-Sargam-Bold.woff2'),
        ('Mukta-Bold.ttf',    'Mukta-Sargam-Bold.woff'),
    ]
    for src_name, dst_name in pairs:
        src = SRC_DIR / src_name
        dst = OUT_DIR / dst_name
        if not src.exists():
            print(f"  SKIP (missing): {src}")
            continue
        print(f"\n{src_name} → {dst_name}")
        modify_font(str(src), str(dst))

    bump_preview_cache_buster()

    print("\n=== Mukta-Sargam ===")
    print("  M=tivra  m=shuddha  R/G/D/N=shuddha  r/g/d/n=komal  S/s=Sa  P/p=Pa")


if __name__ == '__main__':
    main()
