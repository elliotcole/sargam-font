# Sargam Font Preview

Live preview: https://elliotcole.github.io/sargam-font/

Version 3.0. Hindustani classical sargam notation rendered through four font variants:
- **Lato-Sargam** (Latin output)
- **Mukta-Sargam** (Latin output, Mukta typeface)
- **Mukta-Sargam-Hindi** (Devanagari output)
- **Mukta-Sargam-Punjabi** (Gurmukhi output)

Type Latin sargam (`S R G m M P D N`, lowercase = komal, `X'` = tar, `,X` = mandra,
`X~` = murki, `X~~` = andolan, `(X)` = kan-sur, `[X]` = subscript) and the font
renders it as proper notation — including syllabic रे / ਰੇ for R and नी / ਨੀ for N.

**Why `,X` for mandra.** The common online convention writes lower octave as
`'R`. Sargam uses `,R` instead: the comma sits low, like the dot it becomes,
so `S ,R G` still reads as "low R" without the font. It also removes an
ambiguity: in `'R` / `R'` the apostrophe means both mandra (before) and tar
(after), so `S'R` could be either. And phone keyboards turn `'` into a
curly `’`, while a comma is left alone.

`'X` is still accepted for mandra, so existing notation renders unchanged.
One caveat: with no space, `S'R` reads as tar S then R (the suffix wins);
write `S 'R` or, better, `S,R`.

Source fonts are released under the SIL Open Font License (see OFL.txt).
The sargam mark layer, OpenType lookups, and composite glyphs are added by
scripts in this repo.
