#!/usr/bin/env python3
"""
Build Lato-Sargam v2 from v1.

v2 conventions:
  Lowercase r/g/d/n = komal,  uppercase R/G/D/N = shuddha
  Lowercase m       = shuddha Ma,  uppercase M = tivra Ma
  S' = tar octave,  ,S = mandra octave
  S~ = murki (letter + tilde-after; placeholder composite, redraw later)
  S~~ = andolan (wavy line drawn AFTER the letter, taking its own space)
  /  \\  = meend (long curved diagonals between swaras)

Reads v1 fonts from ./src, writes v2 fonts to ./out.
"""
import io, os
from pathlib import Path
from fontTools.ttLib import TTFont

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR      = PROJECT_ROOT / 'src'
OUT_DIR      = PROJECT_ROOT / 'out'

# Each potential source font family lives in its own subdirectory under src/.
# Today only the Lato build pipeline is implemented; Baloo and Mukta sit there
# as future targets once the LATO-SPECIFIC steps in modify_font() are
# generalized into composite-based equivalents (see HANDOFF.md).
LATO_V1_DIR  = SRC_DIR / 'Lato-Sargam v1'


def modify_font(input_path: str, output_path: str):
    import copy
    font = TTFont(input_path)
    glyf = font['glyf']
    hmtx = font['hmtx']

    # ── Step 1: Swap glyph outlines  (LATO-SPECIFIC) ──
    # Reuses pre-drawn glyphs that ship inside Lato-Sargam-v1: komal letters
    # are at glyph00303-00306, tivra Ma is glyph00315. For source fonts that
    # don't have these prebuilt, this step has to be replaced with composite-
    # based versions (letter + underline / letter + tivra mark). See HANDOFF.md
    # § "Adapting to other source fonts".
    # Capture v1 source glyphs as independent copies BEFORE reassigning, so
    # later writes to a slot don't mutate earlier reads. (Without deepcopy,
    # `glyf['m'] = glyf['M']` aliases — assigning to glyf['M'] later then
    # corrupts m. This bit us once before; keep the copies explicit.)
    src_M       = copy.deepcopy(glyf['M']);          src_M_mx       = copy.deepcopy(hmtx['M'])
    src_S       = copy.deepcopy(glyf['S']);          src_S_mx       = copy.deepcopy(hmtx['S'])
    src_P       = copy.deepcopy(glyf['P']);          src_P_mx       = copy.deepcopy(hmtx['P'])
    src_g00303  = copy.deepcopy(glyf['glyph00303']); src_g00303_mx  = copy.deepcopy(hmtx['glyph00303'])
    src_g00304  = copy.deepcopy(glyf['glyph00304']); src_g00304_mx  = copy.deepcopy(hmtx['glyph00304'])
    src_g00305  = copy.deepcopy(glyf['glyph00305']); src_g00305_mx  = copy.deepcopy(hmtx['glyph00305'])
    src_g00306  = copy.deepcopy(glyf['glyph00306']); src_g00306_mx  = copy.deepcopy(hmtx['glyph00306'])
    src_g00315  = copy.deepcopy(glyf['glyph00315']); src_g00315_mx  = copy.deepcopy(hmtx['glyph00315'])

    # m ← v1 M (shuddha Ma), M ← glyph00315 (tivra Ma)
    glyf['m'], hmtx['m'] = src_M, src_M_mx
    glyf['M'], hmtx['M'] = src_g00315, src_g00315_mx

    # ── Step 1.1: Relocate M's tivra mark  (LATO-SPECIFIC) ──
    # The original tivra mark on glyph00315 is a thin vertical bar mostly
    # inside the M's V-notch (x≈844-999, y≈1043-1528). At 18px font size,
    # only the slim portion above cap height is visible — sub-pixel and
    # invisible. Relocate the mark to sit fully above the letter so it
    # reads clearly as a tivra marker. Operates on contour 1's 4-point
    # quad assumed by glyph00315's structure.
    from fontTools.ttLib.tables._g_l_y_f import GlyphCoordinates as _GlyphCoords
    def relocate_tivra_mark(glyph_obj, mark_width=210, y_low=1480, y_high=1980):
        coords = list(glyph_obj.coordinates)
        # Letter is contour 0 (everything except the last 4 mark points).
        letter_xs = [p[0] for p in coords[:-4]]
        x_center = (min(letter_xs) + max(letter_xs)) / 2
        half = mark_width / 2
        x_left  = round(x_center - half)
        x_right = round(x_center + half)
        coords[-4:] = [
            (x_right, y_high),  # top-right    (CW winding)
            (x_right, y_low),   # bottom-right
            (x_left,  y_low),   # bottom-left
            (x_left,  y_high),  # top-left
        ]
        glyph_obj.coordinates = _GlyphCoords(coords)
    relocate_tivra_mark(glyf['M'])
    # s ← S, p ← P
    glyf['s'], hmtx['s'] = src_S, src_S_mx
    glyf['p'], hmtx['p'] = src_P, src_P_mx
    # r/g/d/n ← komal glyphs (R_/G_/D_/N_ ligature results in v1)
    glyf['r'], hmtx['r'] = src_g00303, src_g00303_mx
    glyf['g'], hmtx['g'] = src_g00304, src_g00304_mx
    glyf['d'], hmtx['d'] = src_g00305, src_g00305_mx
    glyf['n'], hmtx['n'] = src_g00306, src_g00306_mx
    print("  Glyphs swapped")

    # ── Step 1.2: Widen komal underscores  (LATO-SPECIFIC) ──
    # v1's komal glyphs ship with a narrow underscore (a 4-point quad at
    # y=-246..-118, ~788u wide). At small sizes the bar reads as a barely-
    # visible hyphen — widen it to the ink width of an N so the komal mark
    # is unmistakable. Detection is structural: the underscore is the unique
    # 4-point contour with all y in (-300, 0), distinguishing it from the
    # letter (y > 0), the mandra dot (y < -300), and the tar dot (y > 1700).
    def widen_komal_underscore(glyph, target_width):
        if glyph.numberOfContours <= 0:
            return False
        coords = list(glyph.coordinates)
        end_pts = list(glyph.endPtsOfContours)
        prev = -1
        for end in end_pts:
            seg_count = end - prev
            if seg_count == 4:
                seg = coords[prev+1:end+1]
                ys = [p[1] for p in seg]
                if max(ys) < 0 and min(ys) > -300:
                    # Letter ink center: use only points in the main letter band
                    # (above baseline, below ascender) to avoid mandra/tar dots.
                    other_pts = coords[:prev+1] + coords[end+1:]
                    letter_xs = [p[0] for p in other_pts if 0 < p[1] < 1500]
                    if not letter_xs:
                        letter_xs = [p[0] for p in other_pts]
                    center = (min(letter_xs) + max(letter_xs)) / 2
                    half = target_width / 2
                    x_left  = round(center - half)
                    x_right = round(center + half)
                    y_high  = max(ys)
                    y_low   = min(ys)
                    new_coords = list(coords)
                    new_coords[prev+1:end+1] = [
                        (x_right, y_high),
                        (x_right, y_low),
                        (x_left,  y_low),
                        (x_left,  y_high),
                    ]
                    glyph.coordinates = _GlyphCoords(new_coords)
                    return True
            prev = end
        return False

    from fontTools.pens.boundsPen import ControlBoundsPen as _CBPen
    n_pen = _CBPen(font.getGlyphSet())
    font.getGlyphSet()['N'].draw(n_pen)
    n_x_min, _, n_x_max, _ = n_pen.bounds
    KOMAL_UNDERSCORE_WIDTH = int(round(n_x_max - n_x_min))

    KOMAL_GLYPHS_TO_WIDEN = ['r', 'g', 'd', 'n',
                             'glyph00307', 'glyph00308', 'glyph00309', 'glyph00310',
                             'glyph00311', 'glyph00312', 'glyph00313', 'glyph00314']
    widened = 0
    for name in KOMAL_GLYPHS_TO_WIDEN:
        if name in glyf and widen_komal_underscore(glyf[name], KOMAL_UNDERSCORE_WIDTH):
            widened += 1
    print(f"  Widened komal underscores in {widened} glyphs to {KOMAL_UNDERSCORE_WIDTH}u (= N ink width)")

    # Shared helpers and constants used by Steps 1.5, 1.6, 1.7, etc.
    import math
    from fontTools.ttLib.tables._g_l_y_f import Glyph, GlyphComponent
    from fontTools.pens.boundsPen import ControlBoundsPen
    from fontTools.pens.ttGlyphPen import TTGlyphPen

    SWARA_LETTERS  = ['S', 's', 'R', 'r', 'G', 'g', 'M', 'm', 'P', 'p', 'D', 'd', 'N', 'n']

    def make_composite(parts):
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

    def make_curved_stroke(start, apex, end, stroke_width):
        """Stroked quadratic Bezier with the given thickness, going
        start → apex → end. Used for the meend glyphs (start and end at
        cap-height-ish on the same level, slight bulge) and also for the
        murki ornament (start high, swoop low, end mid)."""
        sx, sy = start;  ax, ay = apex;  ex, ey = end
        dx, dy = ex - sx, ey - sy
        length = math.hypot(dx, dy) or 1
        nx, ny = -dy / length, dx / length   # CCW perpendicular unit
        half = stroke_width / 2
        # Bezier control point such that B(0.5) = apex
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

    # ── Step 1.5: Generate ornament composites (murki, andolan)  (GENERIC) ──
    # Pure composite glyphs that should work on any source font that has the
    # 14 swara letters (S s R r G g M m P p D d N n).
    # Murki = letter followed by a custom directional swoop. The shape mirrors
    #         the typical pitch contour of a murki: high → low → mid (a quick
    #         brush of upper neighbour, dip to lower neighbour, back to main —
    #         "3212" in degree-shorthand). One shared `murki_swoop` glyph
    #         drawn once via make_curved_stroke().
    # Andolan = a horizontal sine-like wavy line drawn AFTER the letter,
    #           taking its own horizontal advance — andolan oscillates over
    #           time, so it claims time-space rather than overlay-space.

    # Andolan wave parameters (one shared 'andolan_wave' glyph)
    WAVE_WIDTH     = 1300
    WAVE_AMP       = 200    # vertical amplitude (peak displacement from centerline)
    WAVE_MID_Y     = 700    # centerline y (around x-height)
    WAVE_STROKE    = 110    # stroke thickness
    WAVE_HUMPS     = 4      # half-periods across WAVE_WIDTH (so 2 full oscillations)
    WAVE_GAP       = 60     # gap between letter and start of wave

    # Murki wave parameters (one shared 'murki_swoop' glyph) — a flipped
    # tilde: same family of shape as a standard ~ but with the first hump
    # going DOWN (valley) and the second going UP (peak), matching the
    # typical murki pitch contour (start, dip to lower neighbour, rebound
    # to upper neighbour, return). Drawn by `make_wave` with first_dir=-1.
    MURKI_WIDTH    = 700
    MURKI_AMP      = 180    # vertical amplitude (peak/valley distance from midline)
    MURKI_MID_Y    = 800    # centerline y — sits a bit above x-height
    MURKI_STROKE   = 110
    MURKI_HUMPS    = 2      # one full wave (one valley + one peak)
    MURKI_GAP      = 40     # gap between letter and start of murki wave

    glyph_set = font.getGlyphSet()

    def make_wave(width, amp, mid_y, stroke, humps, first_dir=+1):
        """Stroked sinusoid: top edge runs left→right with alternating humps,
        bottom edge runs right→left with the same humps offset by stroke width.
        Approximate offset (translate control points by ±half-stroke); good
        enough at typography scales.

        first_dir=+1: first hump rises above the midline (standard tilde).
        first_dir=-1: first hump dips below the midline (flipped tilde — used
        for murki, where the pitch contour starts by descending into the
        lower neighbour before rising)."""
        half = stroke / 2
        half_period = width / humps
        pen = TTGlyphPen(None)
        # Top edge L→R
        pen.moveTo((0, mid_y + half))
        for i in range(humps):
            x_start = i * half_period
            x_mid   = x_start + half_period / 2
            x_end   = x_start + half_period
            sign    = first_dir if i % 2 == 0 else -first_dir
            ctrl_y  = mid_y + sign * amp + half
            pen.qCurveTo((x_mid, ctrl_y), (x_end, mid_y + half))
        # Right end cap (vertical)
        pen.lineTo((width, mid_y - half))
        # Bottom edge R→L (mirrored humps, offset down by half)
        for i in range(humps - 1, -1, -1):
            x_start = i * half_period
            x_mid   = x_start + half_period / 2
            x_end   = x_start
            sign    = first_dir if i % 2 == 0 else -first_dir
            ctrl_y  = mid_y + sign * amp - half
            pen.qCurveTo((x_mid, ctrl_y), (x_end, mid_y - half))
        pen.closePath()
        return pen.glyph()

    # Build the shared andolan wave and murki swoop glyphs
    glyf['andolan_wave'] = make_wave(WAVE_WIDTH, WAVE_AMP, WAVE_MID_Y,
                                     WAVE_STROKE, WAVE_HUMPS)
    hmtx['andolan_wave'] = (WAVE_WIDTH, 0)

    glyf['murki_swoop'] = make_wave(MURKI_WIDTH, MURKI_AMP, MURKI_MID_Y,
                                    MURKI_STROKE, MURKI_HUMPS, first_dir=-1)
    hmtx['murki_swoop'] = (MURKI_WIDTH, 0)

    new_glyph_names = ['andolan_wave', 'murki_swoop']
    for letter in SWARA_LETTERS:
        letter_advance = hmtx[letter][0]

        # Murki: letter + directional swoop AFTER it. The swoop traces the
        # typical murki pitch contour: high → low → mid.
        murki_name = f'{letter}_murki'
        murki_dx = letter_advance + MURKI_GAP
        glyf[murki_name] = make_composite([
            (letter, 0, 0, 1.0),
            ('murki_swoop', murki_dx, 0, 1.0),
        ])
        hmtx[murki_name] = (letter_advance + MURKI_GAP + MURKI_WIDTH, hmtx[letter][1])

        # Andolan: letter + wave AFTER it. Composite advance = letter advance
        # + gap + wave width.
        andolan_name = f'{letter}_andolan'
        wave_dx = letter_advance + WAVE_GAP
        glyf[andolan_name] = make_composite([
            (letter, 0, 0, 1.0),
            ('andolan_wave', wave_dx, 0, 1.0),
        ])
        hmtx[andolan_name] = (letter_advance + WAVE_GAP + WAVE_WIDTH, hmtx[letter][1])
        new_glyph_names.extend([murki_name, andolan_name])

    glyph_order = font.getGlyphOrder()
    for name in new_glyph_names:
        if name not in glyph_order:
            glyph_order.append(name)
    font.setGlyphOrder(glyph_order)
    print(f"  Generated {len(new_glyph_names)} ornament glyphs (1 wave + {len(new_glyph_names)-1} composites)")

    # ── Step 1.6: Redraw meend slashes (/ and \)  (GENERIC) ──
    # Replaces the source font's `slash` and `backslash` outlines with longer,
    # gently curved strokes. Works on any source font that has these glyphs.
    # Default Latin slashes are short and steep. Meend is a glide between
    # swaras — visually a longer, less-steep stroke with a slight inward curve
    # on ascent and outward on descent. Reuses the shared `make_curved_stroke`
    # helper defined at the top of modify_font.
    MEEND_WIDTH    = 1700
    MEEND_TOP_Y    = 1423
    MEEND_BOT_Y    = -50
    MEEND_STROKE   = 130
    MEEND_BULGE    = 130   # apex deviation perpendicular to the straight line
    mid_x = MEEND_WIDTH / 2
    mid_y = (MEEND_TOP_Y + MEEND_BOT_Y) / 2

    # / : ascending — apex shifts right-and-down (curve bulges lower-right,
    # so the stroke leaves the start gently and steepens toward the top)
    glyf['slash'] = make_curved_stroke(
        start=(0, MEEND_BOT_Y),
        apex=(mid_x + MEEND_BULGE * 0.4, mid_y - MEEND_BULGE),
        end=(MEEND_WIDTH, MEEND_TOP_Y),
        stroke_width=MEEND_STROKE)
    hmtx['slash'] = (MEEND_WIDTH, 0)

    # \ : descending — apex shifts right-and-up (curve bulges upper-right,
    # so the stroke departs gently and steepens toward the bottom)
    glyf['backslash'] = make_curved_stroke(
        start=(0, MEEND_TOP_Y),
        apex=(mid_x + MEEND_BULGE * 0.4, mid_y + MEEND_BULGE),
        end=(MEEND_WIDTH, MEEND_BOT_Y),
        stroke_width=MEEND_STROKE)
    hmtx['backslash'] = (MEEND_WIDTH, 0)
    print(f"  Redrew meend / and \\: width={MEEND_WIDTH}, stroke={MEEND_STROKE}, bulge={MEEND_BULGE}")

    # ── Step 1.7: Generate super/sub composites (kan-sur, subscript)  (GENERIC) ──
    # For each kan-sur-eligible glyph (the 14 swaras plus their mandra and tar
    # octave variants), build scaled-and-translated composites:
    #   <glyph>_super → SUPER_SCALE×, raised by SUPER_DY
    #   <glyph>_sub   → SUB_SCALE×,   dropped by SUB_DY
    # The chain context substitution rules added in Step 2.5 swap base glyphs
    # for these when they appear inside parens (kan-sur) or brackets (sub).
    # The R'/G'/D'/N' tar shuddha targets (glyph00276/00277/00280/00281) are
    # the v1 ligature LigGlyphs left untouched by Step 2's remaps, found by
    # probing the v1 GSUB ahead of time.
    SUPER_SCALE = 0.55
    SUPER_DY    = 750     # raises so cap height of super sits above main cap height
    SUB_SCALE   = 0.55
    SUB_DY      = -350    # drops so the bulk of the letter sits below baseline

    KAN_SUR_BASE = list(SWARA_LETTERS)
    MANDRA_GLYPHS = ['glyph00289', 'glyph00290', 'glyph00311', 'glyph00291',
                     'glyph00312', 'glyph00317', 'glyph00292', 'glyph00293',
                     'glyph00294', 'glyph00313', 'glyph00295', 'glyph00314']
    TAR_GLYPHS    = ['glyph00307', 'glyph00308', 'glyph00309', 'glyph00310',
                     'glyph00275', 'glyph00279', 'glyph00316', 'glyph00278',
                     'glyph00276', 'glyph00277', 'glyph00280', 'glyph00281']
    for g in MANDRA_GLYPHS + TAR_GLYPHS:
        if g not in KAN_SUR_BASE and g in glyf:
            KAN_SUR_BASE.append(g)

    # Composites preserve the source glyph's scaled side bearings, so super
    # letters keep natural spacing between each other inside the cluster
    # (kan-sur of three swaras still reads as three swaras, not a single
    # blob). The cluster-to-neighbour tightening is handled at the boundary
    # markers via separate invisible glyphs (see kan_sur_trail_invisible
    # below) — that's a per-edge concern rather than a per-glyph one.
    super_pairs = {}
    sub_pairs   = {}
    for base in KAN_SUR_BASE:
        super_name = f'{base}_super'
        sub_name   = f'{base}_sub'
        glyf[super_name] = make_composite([(base, 0, SUPER_DY, SUPER_SCALE)])
        glyf[sub_name]   = make_composite([(base, 0, SUB_DY,   SUB_SCALE)])
        base_advance = hmtx[base][0]
        hmtx[super_name] = (int(round(base_advance * SUPER_SCALE)), 0)
        hmtx[sub_name]   = (int(round(base_advance * SUB_SCALE)),   0)
        super_pairs[base] = super_name
        sub_pairs[base]   = sub_name

    # Tight variants of each super glyph: same composite outline (so the
    # ink looks identical), but advance reduced by KAN_SUR_TRAIL_PULL.
    # The Step 2.5 close-paren chain context swaps the LAST super letter
    # for its tight variant, so the swara following the cluster gets laid
    # down KAN_SUR_TRAIL_PULL units earlier — the cluster reads as a unit
    # with the swara it leads into. This is done via GSUB rather than GPOS
    # because some browser shapers ignore non-pair-adjustment lookups
    # inside the kern feature.
    KAN_SUR_TRAIL_PULL = 130
    super_tight_pairs = {}    # super_name → super_name_tight (super TRAIL pull)
    base_tight_pairs  = {}    # base_name  → base_name_tight (sub LEAD pull, mirror)
    for base, super_name in super_pairs.items():
        # super_tight: SUPER variant with reduced advance — used as the LAST
        # super of a kan-sur cluster so the FOLLOWING swara is laid down
        # earlier (cluster reads as part of the swara it leads into).
        tight_name = f'{base}_super_tight'
        glyf[tight_name] = make_composite([(base, 0, SUPER_DY, SUPER_SCALE)])
        super_advance = hmtx[super_name][0]
        hmtx[tight_name] = (max(0, super_advance - KAN_SUR_TRAIL_PULL), 0)
        super_tight_pairs[super_name] = tight_name
        # base_tight: full-size base letter with reduced advance — mirror,
        # used as the PRECEDING swara before a sub cluster, so the sub
        # cluster is laid down earlier (cluster reads as part of the swara
        # it follows from). Same pull amount as super, just on the other
        # side of the cluster.
        base_tight_name = f'{base}_tight'
        glyf[base_tight_name] = make_composite([(base, 0, 0, 1.0)])
        base_advance_orig = hmtx[base][0]
        hmtx[base_tight_name] = (max(0, base_advance_orig - KAN_SUR_TRAIL_PULL), 0)
        base_tight_pairs[base] = base_tight_name

    # Single zero-advance invisible glyph for both opening and closing
    # paren/bracket markers.
    invisible = Glyph(); invisible.numberOfContours = 0
    glyf['kan_sur_invisible'] = invisible
    hmtx['kan_sur_invisible'] = (0, 0)

    glyph_order = font.getGlyphOrder()
    for n in [*super_pairs.values(), *sub_pairs.values(),
              *super_tight_pairs.values(), *base_tight_pairs.values(),
              'kan_sur_invisible']:
        if n not in glyph_order:
            glyph_order.append(n)
    font.setGlyphOrder(glyph_order)
    print(f"  Generated {len(super_pairs) + len(sub_pairs) + len(super_tight_pairs)} super/sub composites ({len(super_tight_pairs)} tight variants for trailing-edge pull)")

    # ── Step 2: ALL GSUB ligature changes in one pass  (MIXED) ──
    # Lato-specific blocks remap the v1 font's existing octave ligatures
    # (QUOTE_REMAP, M_REMAP, m_REMAP, TAR_REMAP) to point at the new v2 glyph
    # IDs. Generic blocks add fresh ligatures that should work on any font:
    #   • mandra prefix  ,X   → mandra X
    #   • murki          X~   → X_murki composite
    #   • andolan        X~~  → X_andolan composite
    # When porting to a non-Lato source, drop the *_REMAP blocks and keep
    # only the additions.
    # Remapping tables
    QUOTE_REMAP = {
        ('M',):          'glyph00317',  # 'M → mandra tivra
        ('m',):          'glyph00292',  # 'm → mandra shuddha
        ('s',):          'glyph00289',  # 's → same as 'S
        ('p',):          'glyph00293',  # 'p → same as 'P
        ('r',):          'glyph00311',  # 'r → mandra komal Re
        ('g',):          'glyph00312',  # 'g → mandra komal Ga
        ('d',):          'glyph00313',  # 'd → mandra komal Dha
        ('n',):          'glyph00314',  # 'n → mandra komal Ni
    }
    QUOTE_REMOVE = {('M', 'grave')}

    M_REMAP = {
        ('quotesingle',):             'glyph00316',  # M' → tar tivra
        ('quotesingle', 'grave'):     None,           # M'` → REMOVE
        ('grave', 'quotesingle'):     None,           # M`' → REMOVE
        ('grave',):                   None,           # M`  → REMOVE (M is already tivra)
    }
    m_REMAP = {
        ('quotesingle',):             'glyph00278',  # m' → tar shuddha
    }

    TAR_REMAP = {
        'r': 'glyph00307',  # r' → tar komal Re
        'g': 'glyph00308',  # g' → tar komal Ga
        'd': 'glyph00309',  # d' → tar komal Dha
        'n': 'glyph00310',  # n' → tar komal Ni
        's': 'glyph00275',  # s' → same as S'
        'p': 'glyph00279',  # p' → same as P'
    }

    # Mandra prefix via comma: ,S → mandra S, etc.
    # Triggered by comma+letter ligature; targets are the v1 mandra glyphs.
    MANDRA_COMMA_PREFIX_REMAP = {
        'S': 'glyph00289',  # ,S → mandra S
        's': 'glyph00289',  # ,s → mandra S (same glyph)
        'R': 'glyph00290',  # ,R → mandra shuddha Re
        'r': 'glyph00311',  # ,r → mandra komal Re
        'G': 'glyph00291',  # ,G → mandra shuddha Ga
        'g': 'glyph00312',  # ,g → mandra komal Ga
        'M': 'glyph00317',  # ,M → mandra tivra Ma
        'm': 'glyph00292',  # ,m → mandra shuddha Ma
        'P': 'glyph00293',  # ,P → mandra Pa
        'p': 'glyph00293',  # ,p → mandra Pa (same glyph)
        'D': 'glyph00294',  # ,D → mandra shuddha Dha
        'd': 'glyph00313',  # ,d → mandra komal Dha
        'N': 'glyph00295',  # ,N → mandra shuddha Ni
        'n': 'glyph00314',  # ,n → mandra komal Ni
    }

    for lookup in font['GSUB'].table.LookupList.Lookup:
        if lookup.LookupType != 4:
            continue
        for sub in lookup.SubTable:
            if not hasattr(sub, 'ligatures'):
                continue

            # Process quotesingle (mandra prefix) ligatures
            if 'quotesingle' in sub.ligatures:
                new_ligs = []
                for lig in sub.ligatures['quotesingle']:
                    comp = tuple(lig.Component)
                    if comp in QUOTE_REMOVE:
                        print(f"  Removed: ' + {' + '.join(comp)}")
                        continue
                    if comp in QUOTE_REMAP:
                        old = lig.LigGlyph
                        lig.LigGlyph = QUOTE_REMAP[comp]
                        print(f"  '{comp[0]} → {lig.LigGlyph} (was {old})")
                    new_ligs.append(lig)
                sub.ligatures['quotesingle'] = new_ligs

            # Process M ligatures
            if 'M' in sub.ligatures:
                new_ligs = []
                for lig in sub.ligatures['M']:
                    comp = tuple(lig.Component)
                    if comp in M_REMAP:
                        target = M_REMAP[comp]
                        if target is None:
                            print(f"  Removed: M + {' + '.join(comp)}")
                            continue
                        lig.LigGlyph = target
                        print(f"  M + {' + '.join(comp)} → {target}")
                    new_ligs.append(lig)
                sub.ligatures['M'] = new_ligs

            # Process m ligatures
            if 'm' in sub.ligatures:
                new_ligs = []
                for lig in sub.ligatures['m']:
                    comp = tuple(lig.Component)
                    if comp in m_REMAP:
                        lig.LigGlyph = m_REMAP[comp]
                        print(f"  m + {' + '.join(comp)} → {lig.LigGlyph}")
                    new_ligs.append(lig)
                sub.ligatures['m'] = new_ligs

            # Process tar (suffix ') ligatures for all lowercase swaras
            for letter, target in TAR_REMAP.items():
                if letter in sub.ligatures:
                    for lig in sub.ligatures[letter]:
                        if list(lig.Component) == ['quotesingle']:
                            old = lig.LigGlyph
                            lig.LigGlyph = target
                            print(f"  {letter}' → {target} (was {old})")

            from fontTools.ttLib.tables.otTables import Ligature

            # Add mandra comma-prefix ligatures: ,S → mandra S, etc.
            # First glyph in ligature is the trigger ('comma' here), components
            # follow it. The lookup table groups all comma-triggered ligatures
            # under sub.ligatures['comma'].
            if 'comma' not in sub.ligatures:
                sub.ligatures['comma'] = []
            for letter, target in MANDRA_COMMA_PREFIX_REMAP.items():
                has_letter = any(list(lig.Component) == [letter] for lig in sub.ligatures['comma'])
                if not has_letter:
                    new_lig = Ligature()
                    new_lig.Component = [letter]
                    new_lig.LigGlyph = target
                    new_lig.CompCount = 2
                    sub.ligatures['comma'].append(new_lig)
                    print(f"  Added: ,{letter} → {target}")

            # Add ornament ligatures: X~~ → X_andolan, X~ → X_murki.
            # Insert the longer match (andolan) FIRST so the engine picks it
            # over the shorter murki match when ~ ~ both follow the swara.
            # The X_murki composite is currently a placeholder (letter +
            # tilde-after); the GSUB rule routes typing to it so we can later
            # redraw the composite without touching ligature wiring.
            for letter in SWARA_LETTERS:
                if letter not in sub.ligatures:
                    sub.ligatures[letter] = []
                # Andolan: X + ~ + ~ → X_andolan
                has_andolan = any(list(lig.Component) == ['asciitilde', 'asciitilde']
                                  for lig in sub.ligatures[letter])
                if not has_andolan:
                    lig = Ligature()
                    lig.Component = ['asciitilde', 'asciitilde']
                    lig.LigGlyph = f'{letter}_andolan'
                    lig.CompCount = 3
                    sub.ligatures[letter].insert(0, lig)
                    print(f"  Added: {letter}~~ → {letter}_andolan")
                # Murki: X + ~ → X_murki
                has_murki = any(list(lig.Component) == ['asciitilde']
                                for lig in sub.ligatures[letter])
                if not has_murki:
                    lig = Ligature()
                    lig.Component = ['asciitilde']
                    lig.LigGlyph = f'{letter}_murki'
                    lig.CompCount = 2
                    sub.ligatures[letter].append(lig)
                    print(f"  Added: {letter}~ → {letter}_murki")

    # ── Step 2.5: Chain context substitution — kan-sur and subscript  (GENERIC) ──
    # Adds OpenType GSUB type-6 chain context lookups so that swaras inside
    # `(...)` render as superscript (kan-sur) and inside `[...]` render as
    # subscript. The parens/brackets themselves are substituted with a
    # zero-width invisible glyph so they don't render.
    #
    # Each side (super, sub) is implemented as three lookups applied in order:
    #   OPEN     : '(' or '[' followed by a base glyph
    #              → substitute the marker with invisible AND the base with super/sub
    #   CONTINUE : a super (or sub) glyph followed by a base
    #              → substitute the base with super (or sub). Repeats left-to-right
    #                within its single pass, propagating super-ness across the run.
    #   CLOSE    : a super (or sub) glyph followed by ')' or ']'
    #              → substitute the marker with invisible
    #
    # The chain breaks naturally on any glyph that isn't a base swara/octave
    # variant (e.g., a space) so input outside parens/brackets is unaffected.
    from fontTools.ttLib.tables import otTables as ot

    # Coverage glyphs must be sorted by glyph ID per the OpenType spec.
    # Glyph IDs follow the font's glyph order, so we sort by index in it.
    _glyph_idx = {g: i for i, g in enumerate(font.getGlyphOrder())}

    def make_coverage(glyphs):
        cov = ot.Coverage()
        cov.glyphs = sorted(set(glyphs), key=lambda g: _glyph_idx.get(g, 1 << 30))
        return cov

    def make_single_subst(mapping):
        s = ot.SingleSubst()
        s.mapping = dict(mapping)
        return s

    def make_chain_ctx(backtrack, input_, lookahead, subst_records):
        s = ot.ChainContextSubst()
        s.Format = 3
        s.BacktrackCoverage   = [make_coverage(g) for g in backtrack]
        s.BacktrackGlyphCount = len(backtrack)
        s.InputCoverage       = [make_coverage(g) for g in input_]
        s.InputGlyphCount     = len(input_)
        s.LookAheadCoverage   = [make_coverage(g) for g in lookahead]
        s.LookAheadGlyphCount = len(lookahead)
        s.SubstLookupRecord   = []
        for seq, idx in subst_records:
            rec = ot.SubstLookupRecord()
            rec.SequenceIndex   = seq
            rec.LookupListIndex = idx
            s.SubstLookupRecord.append(rec)
        s.SubstCount = len(s.SubstLookupRecord)
        return s

    def make_lookup(lookup_type, subtables):
        lk = ot.Lookup()
        lk.LookupType = lookup_type
        lk.LookupFlag = 0
        lk.SubTable = list(subtables)
        lk.SubTableCount = len(lk.SubTable)
        return lk

    gsub = font['GSUB'].table
    lookup_list = gsub.LookupList

    def add_lookup(lk):
        idx = len(lookup_list.Lookup)
        lookup_list.Lookup.append(lk)
        lookup_list.LookupCount = len(lookup_list.Lookup)
        return idx

    # Nested helper lookups: substitute base→super, base→sub, and the four
    # marker glyphs ('(' ')' '[' ']') → invisible. These are referenced by
    # SubstLookupRecord from the chain-context lookups below; they're not
    # added to the 'liga' feature directly.
    idx_super              = add_lookup(make_lookup(1, [make_single_subst(super_pairs)]))
    idx_sub                = add_lookup(make_lookup(1, [make_single_subst(sub_pairs)]))
    idx_super_to_tight     = add_lookup(make_lookup(1, [make_single_subst(super_tight_pairs)]))
    idx_base_to_tight      = add_lookup(make_lookup(1, [make_single_subst(base_tight_pairs)]))
    idx_hide_paren_open    = add_lookup(make_lookup(1, [make_single_subst({'parenleft':    'kan_sur_invisible'})]))
    idx_hide_paren_close   = add_lookup(make_lookup(1, [make_single_subst({'parenright':   'kan_sur_invisible'})]))
    idx_hide_bracket_open  = add_lookup(make_lookup(1, [make_single_subst({'bracketleft':  'kan_sur_invisible'})]))
    idx_hide_bracket_close = add_lookup(make_lookup(1, [make_single_subst({'bracketright': 'kan_sur_invisible'})]))

    super_class = list(super_pairs.values())
    sub_class   = list(sub_pairs.values())
    base_class  = list(super_pairs.keys())

    top_level = []
    # Super: open, continue, close
    top_level.append(add_lookup(make_lookup(6, [make_chain_ctx(
        backtrack=[],
        input_=[['parenleft'], base_class],
        lookahead=[],
        subst_records=[(0, idx_hide_paren_open), (1, idx_super)])])))
    top_level.append(add_lookup(make_lookup(6, [make_chain_ctx(
        backtrack=[super_class],
        input_=[base_class],
        lookahead=[],
        subst_records=[(0, idx_super)])])))
    # Close, step 1: substitute the LAST super letter for its tight variant
    # only when ')' is followed by a base swara. This gates the trailing
    # pull so it kicks in for kan-sur-then-swara (e.g., (SR)G) but NOT for
    # kan-sur-then-meend (e.g., (SR)\G) — meend is its own glide and the
    # cluster shouldn't crash into the curve. Spaces, brackets, and other
    # punctuation likewise fall outside base_class so the cluster keeps
    # natural spacing in those contexts. Single-substitution chain context
    # (one SubstLookupRecord) for browser-shaper compatibility.
    top_level.append(add_lookup(make_lookup(6, [make_chain_ctx(
        backtrack=[],
        input_=[super_class, ['parenright']],
        lookahead=[base_class],
        subst_records=[(0, idx_super_to_tight)])])))
    # Close, step 2: hide ')' whenever it's preceded by a super or super_tight
    # glyph. Backtrack class is the union — covers both the tightened case
    # (step 1 fired) and the un-tightened case (cluster followed by meend
    # / space / other non-swara, where step 1's lookahead didn't match).
    super_tight_class = list(super_tight_pairs.values())
    top_level.append(add_lookup(make_lookup(6, [make_chain_ctx(
        backtrack=[super_class + super_tight_class],
        input_=[['parenright']],
        lookahead=[],
        subst_records=[(0, idx_hide_paren_close)])])))
    # Sub LEAD pull (mirror of super trail pull): when a base swara is
    # followed by '[' which is followed by another base swara, substitute
    # the preceding base for its tight variant. Shrinks the swara's advance
    # so the sub cluster sits closer — sub reads as part of the swara it
    # follows from. Must run BEFORE the open-sub lookup, which consumes '['.
    top_level.append(add_lookup(make_lookup(6, [make_chain_ctx(
        backtrack=[],
        input_=[base_class, ['bracketleft']],
        lookahead=[base_class],
        subst_records=[(0, idx_base_to_tight)])])))
    # Sub: open, continue, close
    top_level.append(add_lookup(make_lookup(6, [make_chain_ctx(
        backtrack=[],
        input_=[['bracketleft'], base_class],
        lookahead=[],
        subst_records=[(0, idx_hide_bracket_open), (1, idx_sub)])])))
    top_level.append(add_lookup(make_lookup(6, [make_chain_ctx(
        backtrack=[sub_class],
        input_=[base_class],
        lookahead=[],
        subst_records=[(0, idx_sub)])])))
    top_level.append(add_lookup(make_lookup(6, [make_chain_ctx(
        backtrack=[sub_class],
        input_=[['bracketright']],
        lookahead=[],
        subst_records=[(0, idx_hide_bracket_close)])])))

    # Wire the six chain-context lookups into the 'liga' feature so they
    # apply by default. They're appended to LookupListIndex so they fire
    # AFTER the existing ligature lookups (mandra/tar/ornament) — important
    # because chain-context backtrack/input classes contain the mandra/tar
    # target glyphs that those earlier ligatures produce.
    for feat_record in gsub.FeatureList.FeatureRecord:
        if feat_record.FeatureTag == 'liga':
            existing = feat_record.Feature.LookupListIndex
            for idx in top_level:
                if idx not in existing:
                    existing.append(idx)
            feat_record.Feature.LookupCount = len(existing)
    print(f"  Added kan-sur/sub chain context: {len(super_pairs)} super + {len(sub_pairs)} sub mappings, 6 chain lookups")

    # Save via TTF roundtrip to ensure GSUB binary is regenerated
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
    """Each build copies the canonical out/Lato-Sargam-v2*.woff(2) files to
    versioned names (Lato-Sargam-v2-N.woff2 etc.) and rewrites the preview
    HTML to point at those versioned names. Safari aggressively caches
    file:// resources by URL path and ignores query strings, so making the
    URL path itself unique each build is the only reliable cache miss
    without manual intervention. Old versioned files are deleted; the
    canonical files stay put for deploy.sh."""
    import re, shutil
    preview = PROJECT_ROOT / 'preview' / 'index.html'
    if not preview.exists():
        return
    text = preview.read_text()

    m = re.search(r'Lato-Sargam-v2(?:-Bold)?-(\d+)\.woff', text)
    current = int(m.group(1)) if m else 0
    next_v = (current + 1) if 0 < current < 1_000_000 else 1

    # Sweep old versioned files. Patterns are anchored so the canonical
    # Lato-Sargam-v2.woff(2) and Lato-Sargam-v2-Bold.woff(2) stay untouched.
    for old in OUT_DIR.glob('Lato-Sargam-v2-Bold-[0-9]*.woff*'):
        old.unlink()
    for old in OUT_DIR.glob('Lato-Sargam-v2-[0-9]*.woff*'):
        old.unlink()

    # Copy canonical → versioned
    pairs = [
        ('Lato-Sargam-v2.woff2',      f'Lato-Sargam-v2-{next_v}.woff2'),
        ('Lato-Sargam-v2.woff',       f'Lato-Sargam-v2-{next_v}.woff'),
        ('Lato-Sargam-v2-Bold.woff2', f'Lato-Sargam-v2-Bold-{next_v}.woff2'),
        ('Lato-Sargam-v2-Bold.woff',  f'Lato-Sargam-v2-Bold-{next_v}.woff'),
    ]
    copied = 0
    for canonical, versioned in pairs:
        src = OUT_DIR / canonical
        if src.exists():
            shutil.copy(src, OUT_DIR / versioned)
            copied += 1

    # Rewrite preview HTML font URLs: replace any
    #   Lato-Sargam-v2[-Bold][-N].woff(2)?[?v=...]
    # with the new versioned filename (and drop any leftover ?v= query string).
    pattern = re.compile(r'Lato-Sargam-v2(-Bold)?(?:-\d+)?\.woff(2?)(?:\?v=\d+)?')
    def replace(match):
        bold = match.group(1) or ''
        ext  = match.group(2)
        return f'Lato-Sargam-v2{bold}-{next_v}.woff{ext}'
    new_text = pattern.sub(replace, text)
    if new_text != text:
        preview.write_text(new_text)
        print(f"  Updated preview → versioned filenames (-{next_v}.woff[2]); copied {copied} files")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    pairs = [
        ('Lato-Sargam-v1.woff2',      'Lato-Sargam-v2.woff2'),
        ('Lato-Sargam-v1.woff',       'Lato-Sargam-v2.woff'),
        ('Lato-Sargam-v1-Bold.woff2', 'Lato-Sargam-v2-Bold.woff2'),
        ('Lato-Sargam-v1-Bold.woff',  'Lato-Sargam-v2-Bold.woff'),
    ]
    for src_name, dst_name in pairs:
        src = LATO_V1_DIR / src_name
        dst = OUT_DIR / dst_name
        if not src.exists():
            print(f"  SKIP (missing source): {src}")
            continue
        print(f"\n{src_name} → {dst_name}")
        modify_font(str(src), str(dst))

    bump_preview_cache_buster()

    print("\n=== Lato-Sargam v2 ===")
    print("  M=tivra  m=shuddha  R/G/D/N=shuddha  r/g/d/n=komal  S/s=Sa  P/p=Pa")


if __name__ == '__main__':
    main()
