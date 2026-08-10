# SaTML 2027 submission

Target: [IEEE SaTML 2027](https://satml.org/call-for-papers/), **research paper** track.
Unified attack+defense story: threat model → leak_check measurements → fcvd_ct verification.

LaTeX migration of `../satml-typst/` (the team is drafting on Overleaf). The
Typst version is frozen at the outline stage; this directory is the live one.

## Timeline (all AoE)

| date | event |
|---|---|
| **2026-09-29** | paper submission |
| 2026-11-04 | early reject notification |
| 2026-11-25 → 12-09 | interactive discussion & revision |
| 2026-12-16 | final decision |
| 2027-01-21 | revisions due |
| early May 2027 | conference |

## Status

**Outline stage.** Every section file under `sections/` is bullets only, each
pointing at the repo artifact that backs it. No prose has been drafted.

## Open items

- [ ] Official submission kit (template, page limit, anonymization policy,
      submission site) announced **mid-August 2026** — currently on plain
      `IEEEtran` (conference option) as a stand-in; swap the class/options
      when the kit lands.
- [ ] Author order + full names/emails (placeholders in `main.tex`).
- [ ] Double-blind: expect to need an anonymized build; keep repo pointers
      in comments, not prose, until policy is known.
- [ ] Related-work sweep (repo issue #23) feeds `sections/06-related-work.tex`;
      `refs.bib` holds only seed entries.
- [ ] Regenerate the Polygeist status table and coverage numbers from live
      data at draft time — do not hand-copy.

## Build

### Overleaf

Upload this directory (zip it, or connect the repo via Overleaf's GitHub sync)
and set `main.tex` as the root document. `IEEEtran` and `IEEEtran.bst` are in
Overleaf's TeX Live distribution — no class files need uploading.

### Local

```sh
pdflatex main && bibtex main && pdflatex main && pdflatex main
```
