# KSV 5-1 rotation trainer

A single-page app for learning your position in the KSV 5-1 system: serving positions, receiving positions, movement after reception and front row sets.

Live site: https://xszpo.github.io/volleyball_positions/

## For developers

Source files live in `src/`; `index.html` is generated. See `CLAUDE.md` for the build, the tests and the project notes.

## Files

- `index.html` – the whole app. Everything is inside this one file, including the two printable PDFs offered by the download buttons.
- `.nojekyll` – tells GitHub Pages to serve the files as they are.
- `downloads/` – the same cheat sheets as separate files, if you want to link or print them directly:
  - `KSV_5-1_rotation_schema.pdf` / `.png`
  - `KSV_front_row_sets.pdf` / `.png`

## Deploy on GitHub Pages

1. Put these files in the root of the repository (branch `main`).
2. Settings → Pages → Source: Deploy from a branch → Branch: `main`, folder `/ (root)` → Save.
3. After 1–2 minutes the site is live at the URL above.

## Notes

- Match mode can be played alone or with 2–6 friends on the same device (random turn order each moment).
- Rules switch at the top: Official (FIVB, the libero may not serve) or Drill (the libero stays on court and also serves).
- Progress (drill stats, best scores, settings) is saved in each player's browser.
- Positions follow the KSV guide "Receiving positions and movements". The serve column is the team's base defence when we serve (the serving team has no overlap rule since FIVB 2025, so only the server moves) and is not covered by the guide.
