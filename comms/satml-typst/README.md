# SaTML 2027 submission

> **SUPERSEDED 2026-08-10** — the team drafts on Overleaf now; the live copy is
> [`../satml-latex/`](../satml-latex/). This Typst version is frozen at the
> outline stage.

Target: [IEEE SaTML 2027](https://satml.org/call-for-papers/), **research paper** track.
Unified attack+defense story: threat model → leak_check measurements → fcvd_ct verification.

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
      submission site) announced **mid-August 2026** — currently on the
      `charged-ieee` Typst template as a stand-in; likely converting to the
      official IEEE LaTeX class at that point.
- [ ] Author order + full names/emails (placeholders in `main.typ`).
- [ ] Double-blind: expect to need an anonymized build; keep repo pointers
      in comments, not prose, until policy is known.
- [ ] Related-work sweep (repo issue #23) feeds `sections/06-related-work.typ`;
      `refs.bib` holds only seed entries.
- [ ] Regenerate the Polygeist status table and coverage numbers from live
      data at draft time — do not hand-copy.

## Build

```sh
typst compile main.typ    # first run downloads the charged-ieee package
typst watch main.typ      # live preview while writing
```
