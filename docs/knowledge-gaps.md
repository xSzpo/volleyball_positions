# Knowledge gaps

Decisions made without the owner, while the owner was not available. Each one
follows the plan (`docs/v2.md`) and the guide as closely as possible. Review
them after deploy; each entry says what to change to reverse it.

### 1. Built-in defaults and the live site with every flag off

- **Issue:** #17
- **Problem:** `docs/v2.md` says unbuilt features default to off, but not what the working v1 features default to, nor what the live site shows while every PostHog flag is off.
- **Decision:** The built-in defaults are on for every v1 feature that works today and off for `learn-animation`, `rules-official` and `after-dig`, so `file://` and the tests behave as v1. On `xszpo.github.io` the PostHog values replace the defaults, so with every flag off the live site shows only the shell and an empty state.
- **Alternatives:** default everything off (tests and `file://` would need `?ff=all`), or let the defaults win until a flag is switched on.
- **Reversible by:** changing the values in `FEATURES` in `src/template.html`, or switching the PostHog flags on.

### 2. Empty-state wording

- **Issue:** #17
- **Problem:** When no tab is on, the page needs something to show instead of a blank area.
- **Decision:** One card below the header: "New version on the way."
- **Alternatives:** a longer text with a link to v1 or a date.
- **Reversible by:** editing `#ffEmpty` in `src/template.html`.

### 3. First visit before PostHog answers

- **Issue:** #17
- **Problem:** On the first visit to the live site there are no stored flag values, so the page must render something before PostHog answers.
- **Decision:** The built-in defaults render first; PostHog's answer replaces them if the user has not touched the page yet, otherwise on the next load. A flag missing from PostHog's answer counts as off. If PostHog is blocked, the defaults stay.
- **Alternatives:** render the shell only until PostHog answers (blank app when PostHog is blocked).
- **Reversible by:** changing `flagsBase` and `flagsFromPosthog()` in `src/template.html`.

### 4. How `?ff=` values combine

- **Issue:** #17
- **Problem:** The plan does not say whether a second `?ff=` replaces or adds to the stored override.
- **Decision:** Values add up, left to right, on top of `ksv51:ffOverride`: `all` turns everything on, `reset` clears, `key`/`-key` set one flag. So `?ff=reset,-drill-tab` means "defaults without Drill". Unknown keys are ignored.
- **Alternatives:** each `?ff=` replaces the stored override.
- **Reversible by:** changing `ffParse()` in `src/template.html`.

### 5. Online guests follow the host's checks

- **Issue:** #17
- **Problem:** In an online room the host's settings decide the neighbour and set call checks; a guest's own flag may differ.
- **Decision:** A guest follows the host (`meta.nb`, `meta.sets`), as in v1, so the room never waits on a guest whose flag is off.
- **Alternatives:** hide the check on the guest's phone and mark the answer done.
- **Reversible by:** the online code in `src/template.html` (`G.online.meta.nb`, `G.online.meta.sets`).

### 6. L route colour in light mode

- **Issue:** #18
- **Problem:** The plan draws light-mode routes in the role fills, but the L fill `#ffc600` is 1.58:1 on the white route halo, below the 3:1 needed for lines.
- **Decision:** The light L route is `#9a7600`, a darker shade of the same yellow (3.7:1 or more on the halo over every court band). The L marker keeps `#ffc600`.
- **Alternatives:** a darker halo under L only, or a dark outline on the L route.
- **Reversible by:** changing `--route-l` in the light `:root` block of `src/template.html` (`theme_test.py` checks the ratio).

### 7. What the header role chip shows

- **Issue:** #18
- **Problem:** The plan puts the role in a header chip but does not say whether the rules mode stays visible once the summary bar is gone.
- **Decision:** The chip shows only the role code (`OH1 ▾`). The rules mode is in its aria-label and in the sheet. The chip stays visible on every tab, Sets included (v1 hid the bar on Sets).
- **Alternatives:** `OH1 · Drill` on the chip, or hide the chip on Sets.
- **Reversible by:** `renderSetupSummary()` in `src/template.html`.

### 8. How the role sheet behaves

- **Issue:** #18
- **Problem:** The plan says the sheet opens on the first visit with one job and closes on a pick, but not how it closes later or whether the rules switch shows the first time.
- **Decision:** A modal bottom sheet. On the first visit it shows only "Pick your role" (no rules switch) and closes on a pick. Later it closes on a pick, Done, Escape or a tap on the backdrop.
- **Alternatives:** keep the sheet open after a pick until Done, or show the rules on the first visit too.
- **Reversible by:** `setSetupOpen()` in `src/template.html`.

### 9. Teammates in Learn, zone numbers and the setter glow

- **Issue:** #18
- **Problem:** v1 dimmed teammates in Learn, printed zone numbers on the court and pulsed a green ring on the setter's spot. The mock-up shows none of this.
- **Decision:** Learn draws teammates at full strength and marks you with the double ring. Zone numbers and the setter ring are gone; a "Zones" toggle is left for a later issue. In Drill and Match feedback the other players are faded to 35%, and with Show on court "Setter" the markers are 90% size.
- **Alternatives:** keep the dimming in Learn, or keep zone numbers until the toggle exists.
- **Reversible by:** the `chip()` calls in the Learn drawing, and `courtBase()`, in `src/template.html`.

### 10. Court size on short phones

- **Issue:** #18
- **Problem:** `docs/v2.md` §2.7 capped the court at `100svh - 330px`, which at 390 × 664 gives a 290 px wide court and markers about 32 px, below the 36 px the same section asks for.
- **Decision:** The height cap has a 381 px floor, so markers stay at 36 px or more; at 390 × 664 the court is 324 × 381 and the page scrolls a little. `docs/v2.md` is updated.
- **Alternatives:** keep the cap and accept smaller markers on short phones.
- **Reversible by:** the `max-width` of `svg.court` in `src/template.html`.

### 11. Official while `rules-official` is off

- **Issue:** #19
- **Problem:** Official is a restored v1 mode behind `rules-official`, which is off by default. A phone that stored `official` in v1 would otherwise keep using it with no way back.
- **Decision:** While the flag is off, the Official button is not in the DOM and the app plays Simplified, but the stored `ksv51:rulesMode` is left as it is, so the choice comes back when the flag goes on. An online guest still follows the host's `meta.rulesMode`.
- **Alternatives:** overwrite the stored value with `simple`, or show Official before its flag is on.
- **Reversible by:** the `rules-official` check at the top of `applyFeatures()` in `src/template.html`.

### 12. Middle roles across a rules switch

- **Issue:** #19
- **Problem:** Simplified has one middle (`MB`), Official has two (`MB1`, `MB2`). A player who picked a middle needs a role after a switch.
- **Decision:** `roleIn()` maps `MB1` and `MB2` to `MB`, and `MB` to `MB1`. The last picked role stays stored, so `MB2` → Simplified → Official comes back as `MB2`. Same-device players and online roles are mapped the same way.
- **Alternatives:** reopen the role sheet after a switch, or map `MB` to the middle who is front row in R1.
- **Reversible by:** `roleIn()` and `setRules()` in `src/template.html`.

### 13. Rotation step in R3 and R6, and where SUB defends

- **Issue:** #19
- **Problem:** Coach questions 1 and 3 (#16) are open: whether the Rotation step in R3 and R6 shows L or the server in zone 1, and whether the server defends zone 6 or zone 5.
- **Decision:** Built to the plan and the v1 data: the Rotation step shows L in zone 1 in both rule sets (the guide's picture); SUB serves from zone 1 and defends zone 6, the outside hitter keeps zone 5. The Official walk-through table lists the real lineup, so the audit reads L there as the middle it stands for.
- **Alternatives:** show the serving middle or SUB at the Rotation step; SUB in zone 5.
- **Reversible by:** `lineup()` in `src/data.py` for the lineups, `ROWS[..]["serve"]` for the zones; `tests/audit.py` then checks the walk-through tables.

### 14. Drill stats shared between rule sets

- **Issue:** #19
- **Problem:** Drill stats are keyed by role, rotation and phase. `docs/v2.md` §7 says only that Simplified MB stats start empty.
- **Decision:** Keys stay as they are. `MB` is a new role, so its stats start empty; the other roles share their stats between Simplified and Official, which differ only at Our serve in R3 and R6.
- **Alternatives:** add the rules mode to the stats key, so every role starts empty in Simplified.
- **Reversible by:** the stats key in the Drill code of `src/template.html`.

### 15. `match-online` off by default until the live database rules change

- **Issue:** #19
- **Problem:** The live Realtime Database rules reject the role `MB` and `rulesMode` `simple` until the owner runs `terraform apply`. With `match-online` on by default, `file://` and any client without PostHog values would create rooms whose writes are denied.
- **Decision:** The built-in default of `match-online` is off. Re-enable it in #33, after the owner's `terraform apply`.
- **Alternatives:** keep it on and write `official` to rooms until the apply; that would teach the wrong rule set online.
- **Reversible by:** `FEATURES["match-online"]` in `src/template.html` and `DEFAULT_OFF` in `src/tests/flags_test.py`.

### 16. Learn boundaries show your own limits

- **Issue:** #20
- **Problem:** `docs/v2.md` §2.3 asks for T-bars "in the constraining player's role colour", and the mock-up draws them for the setter. It does not say whose limits are drawn when you play another role.
- **Decision:** Learn draws your own limits: one line per overlap partner (the player in your column, and your neighbours in your row), from your marker to the line that partner sets, in their route colour. The caption names the same partners ("Overlap: stay in front of L, right of OP and left of OH1."). When a limit falls inside your marker, no line is drawn and the caption names that partner ("You stand right at the L limit."). The overlap sentence is only in Learn, not in `describe()`, because Drill and Match show `describe()` after the neighbour check and it would give the answer away.
- **Alternatives:** draw every player's limits (busy on a phone), or only the setter's, as in the mock-up.
- **Reversible by:** `partners()`, `overlapText()` and `boundLines()` in `src/template.html`.

### 17. Learn controls before the animation

- **Issue:** #20
- **Problem:** §2.7 puts a sticky controls row under the caption, but its Replay, Pause, Step and speed buttons belong to `learn-animation` (#21). The caption also has no fixed two-line height yet, because the `describe()` texts are longer than 90 characters.
- **Decision:** The sticky row holds only the primary `Next: … ▸`, which steps through the phases and on into the next rotation (R6 wraps to R1). The full `describe()` text stays in the caption; #21 brings the short per-stage captions and the fixed height.
- **Alternatives:** leave the row out until #21; cut `describe()` to two lines now.
- **Reversible by:** `.lctl` and `#lNext` in `src/template.html`.

### 18. SUB texts in Simplified

- **Issue:** #20
- **Problem:** The guide has no SUB. Simplified needs texts for SUB at every step, including the steps where SUB is off court.
- **Decision:** At Our serve in R3 and R6: "You come on for the libero, who may not serve. Serve, then run to zone 6, deep." Off court in R3 and R6: "You come on only for our serve here, because the libero may not serve. When we lose the serve, the libero comes back on for you." In the other rotations: "You play only in R3 (S5) and R6 (S2), to serve when the libero is in zone 1."
- **Alternatives:** leave SUB out of the role texts, since SUB is not in the role picker.
- **Reversible by:** the SUB branches of `describe()` in `src/template.html`.
