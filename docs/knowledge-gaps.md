# Knowledge gaps

Decisions made without the owner, while the owner was not available. Each one
follows the plan (`docs/v2.md`) and the guide as closely as possible. Review
them after deploy; each entry says what to change to reverse it.

### 1. Built-in defaults and the live site with every flag off

- **Issue:** #17
- **Problem:** `docs/v2.md` says unbuilt features default to off, but not what the working v1 features default to, nor what the live site shows while every PostHog flag is off.
- **Decision:** The built-in defaults are on for every v1 feature that works today and off for `learn-animation`, `rules-official` and `after-dig`, so `file://` and the tests behave as v1. *Superseded for `learn-animation` by #23 and for `rules-official` by #36.* On `xszpo.github.io` the PostHog values replace the defaults, so with every flag off the live site shows only the shell and an empty state.
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

### 7. What the header role chip shows (replaced by 60)

- **Issue:** #18
- **Problem:** The plan puts the role in a header chip but does not say whether the rules mode stays visible once the summary bar is gone.
- **Decision:** The chip shows only the role code (`OH1 ▾`). The rules mode is in its aria-label and in the sheet. The chip stays visible on every tab, Sets included (v1 hid the bar on Sets).
- **Alternatives:** `OH1 · Drill` on the chip, or hide the chip on Sets.
- **Reversible by:** `renderSetupSummary()` in `src/template.html`.

### 8. How the role sheet behaves (replaced by 60)

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

### 19. Learn animation captions

- **Issue:** #21
- **Problem:** `docs/v2.md` §4.5 asks for one caption per stage that starts with your move, but in most stages you do not move, and the plan does not say what to show then or after the transition ends.
- **Decision:** Each stage caption is "**You (ROLE):** your note" when you move in that stage, else "**Name:** note" for the stage's first mover. At rest the caption shows your last move in the transition, or the last stage when you did not move. The `move` notes in `data.py` are written to their player ("Leave zone 1 for …") and are at most 78 characters, so the prefix still fits in 90. The `describe()` text stays in `#cue` under the caption.
- **Alternatives:** third-person sentences with no prefix ("The setter leaves zone 1 …"); drop `describe()` from Learn.
- **Reversible by:** `stageCaption()` and `captionHtml()` in `src/template.html`, `move` in `src/data.py`.

### 20. Animation stages, passer and hitter

- **Issue:** #21
- **Problem:** The guide shows arrows but not the order of moves, which passer takes the first ball, or who gets the set. The plan gives the order only for Reception → After reception.
- **Decision:** Reception → After reception: setter, then attackers, then cover, with the ball from L to the setting spot and on to the zone 4 attacker at the net. Rotation → Our serve: everyone to base with the server behind the end line, then the serve (the ball crosses the net while the server runs to base). Our serve → Reception: one walk. An exchange (L off, SUB or a middle on) is its own first stage. After reception → next rotation: the rotate stage, then in Simplified R3 and R6 the middle pair reset ("Walk along the net from zone 2 to zone 4: the middle pair resets."). The three stage dots fill up to the stage that is playing. Asked the coach on #16.
- **Alternatives:** a random passer and hitter per rotation; the setter's choice from the set calls.
- **Superseded** by #30 and #31 (#47): nothing animates between screens.
- **Reversible by:** `transition()` in `src/template.html` (removed in #47).

### 21. Where players leave and come on

- **Issue:** #21
- **Problem:** §4.9 says replacements happen "at the sideline by the attack line" but not which sideline.
- **Decision:** The right sideline at the 3 m line, next to zone 1 where the libero and SUB swap. Asked the coach on #16.
- **Alternatives:** the left sideline by the bench.
- **Superseded** by #31 (#47): exchanges no longer animate; the still caption still says "at the sideline".
- **Reversible by:** `EXIT` in `src/template.html` (removed in #47).

### 22. Reduced motion caption height

- **Issue:** #21
- **Problem:** §4.6 says the reduced-motion caption lists all stages "up to three lines", but a three-stage list of 90-character captions needs more at 390 px.
- **Decision:** The caption keeps a two-line minimum height and grows for the list. Nothing moves under it, because the list shows only after Next and stays until the next tap.
- **Alternatives:** show only your own stage.
- **Reversible by:** `.lcap` and `captionHtml()` in `src/template.html`.

### 23. learn-animation on by default, Official captions generic

- **Issue:** #21
- **Problem:** The plan ships the animation "for Simplified first" but `rules-official` is off by default, so only Simplified is reachable without `?ff=`.
- **Decision:** The built-in default of `learn-animation` is on; the PostHog flag stays off. With `rules-official` on, the Official exchanges play with generic captions ("Go off at the sideline: the libero may not serve.") until #22 polishes them. The options fold of §4.4 (Show everyone / Zones) and the Drill and Match motion of §4.7 are not in this issue.
- **Alternatives:** keep the default off until #22.
- **Reversible by:** `FEATURES["learn-animation"]` in `src/template.html`.

### 24. Learn controls on one line, page scrolls to the court

- **Issue:** #21
- **Problem:** §2.7 plans a 48 px sticky row, but with the animation controls, the dots and a two-line `Next: After reception ▸` the row was 79-93 px and covered the caption and court markers at 390 × 750 and 390 × 664. The header, chips, tag, court and caption alone are about 745 px at 390 × 750, so they cannot all fit above any row without scrolling.
- **Decision:** One-line row of 57 px: the stage dots sit on its top border, and while the controls show, Next reads `After reception ▸` (aria-label "Next: After reception"). When a transition starts, the page scrolls just enough that the whole court and the caption sit above the row; the chips and tag scroll up out of view.
- **Alternatives:** the caption above the court or inside the row (the row grows and covers more court); a smaller court cap (below the 381 px floor at 390 × 664).
- **Reversible by:** `.lctl`, `.ldots` and `learnFit()` in `src/template.html`.

### 25. Official Rotation step in R3 and R6 shows the real lineup

- **Issue:** #21
- **Problem:** `ROWS.back` has L in zone 1 in R3 and R6 (the reception picture), so the rotate animation took the serving middle off and walked L into zone 1, then swapped them back at Our serve. §4.9 and the Official walk-through say L leaves, the front-row middle comes on in zone 4, and the zone 1 middle rotates on and serves. Which picture the Rotation step shows is coach question 1.
- **Decision:** In Official, `players(ri, "start")` puts the serving middle in zone 1 with L off in R3 and R6, and `zoneOf()` and the overlap partners follow it. Learn, Drill and Match all use it, so the serving middle answers zone 1 at the Rotation step and the libero answers off court. Simplified is unchanged.
- **Alternatives:** change only the animation (its end state would not match the static court); change `ROWS.back` in `data.py` (also changes the cheat sheet and the Simplified SUB rename).
- **Reversible by:** `middleServes()` in `src/template.html`.

### 26. Whistle timing wording and where it shows

- **Issue:** #44
- **Problem:** The Volleyball Danmark rule from 1 October 2026 moves the overlap check to the referee's whistle, and lets players move from the server's first movement. The plan does not give the on-screen words, and the Rotation step shows our lineup before our own serve, when no overlap rule applies.
- **Decision:** One sentence, "From the server's first movement you may move.", after every overlap text. Rotation: "These limits count at the referee's whistle when they serve." Reception: "These limits count at the whistle, not during the pass." The neighbour check asks "… at the whistle?". The first rule of thumb covers both teams in one entry, so the numbers the Match hints cite ("rule 2", "rule 4") do not shift.
- **Alternatives:** a new rule of thumb for the receiving team; say "service motion" instead of "first movement".
- **Reversible by:** `WHISTLE_MOVE`, `OVERLAP_WHEN`, `THUMB` and `neighbourQ()` in `src/template.html`. The `#checks` fold was deleted in #23.

### 27. Setter release after the serve kept

- **Issue:** #44
- **Problem:** Under the new rule the setter could leave the reception spot from the server's first movement, not only once the serve is hit. The R1 setter caption says "as soon as the serve is hit".
- **Decision:** Keep the caption and all reception and after-reception spots. It is a tactic, not a rule text, and whether KSV wants the earlier release is the coach question on #16.
- **Alternatives:** change the caption to "as soon as the server starts to move".
- **Reversible by:** the R1 `move["ar"]["S"]` note in `src/data.py`.

### 28. No overlap limits for the serving middle at the Rotation step

- **Issue:** #44
- **Problem:** In Official R3 and R6 the Rotation step draws the serving middle in zone 1 (entry #25). The overlap order counts only at the whistle when the other team serves, and by then the libero is in for that middle, so limits drawn against the middle are wrong.
- **Decision:** At the Rotation step in Official R3 and R6 the serving middle gets no limits ("You serve now, so you have no overlap limits. When they serve, the libero is in for you."). Its neighbours get their other limits and none against the zone 1 slot. The libero is off court in that picture, so there is no marker to draw a limit to. This replaces the part of #25 that said the overlap partners follow the serving middle.
- **Alternatives:** name the libero as the zone 1 partner without a line; draw a ghost libero in zone 1.
- **Reversible by:** `partners()` and `serverNow` in `renderLearn()` in `src/template.html`.

### 29. When Our serve and Reception play

- **Issue:** #47
- **Problem:** The owner asked for Our serve and Reception to play once "when the screen opens". The page also re-renders Learn on load, on a tab switch and on a role or rules change, and the page opens on Reception.
- **Decision:** A phase plays once when you move to a new screen in Learn: Next, a phase chip, a rotation chip or an arrow key. Loading the page, switching back to the Learn tab, and a role or rules change show the still picture only; Replay or Play plays it. After the last stage and a 900 ms hold the still picture comes back with a 150 ms fade. **Replaced by entry 50 (#60):** nothing plays on open.
- **Alternatives:** also play on load and on the Learn tab (motion before any tap, and behind the first-visit role sheet); play only on Next and chips.
- **Reversible by:** `learnGo()` in `src/template.html`.

### 30. What the Reception animation shows

- **Issue:** #47
- **Problem:** The owner wants the ball to come to our side, the pass and the second contact until the ball reaches the setter, with the players' moves. The guide has no per-player timing, and who passes differs per serve.
- **Decision:** Two stages. First their serve flies to the libero while the setter runs to the setting spot (the setter's `ar` note, "as soon as the serve is hit"), and everyone else sees their `rec` note. Then the pass flies from the libero to the setter while the attackers move to their `ar` approach spots with their `ar` notes; the libero reads "Pass the serve high to the setter at the net." and the setter "Take the pass at the setting spot: you play the second contact." The cover players do not move: covering comes after the set, which is After reception. The libero is always the passer. This replaces the Reception → After reception stages and the passer of #20.
- **Alternatives:** a passer chosen per rotation (not in the guide); the cover moves too (goes past "until the ball reaches the setter").
- **Reversible by:** `phaseStages()`, `PASS_TEXT` and `SET_TEXT` in `src/template.html`.

### 31. Exchanges and the pair reset move into the still caption

- **Issue:** #47
- **Problem:** With no animation between screens, the libero and substitute exchanges and the Simplified middle pair reset into R3 and R6 no longer show as moves, and Our serve must start and end on its still picture.
- **Decision:** The at-rest caption keeps them: when a screen follows an exchange or a reset, the player involved reads the old walk caption ("Go off at the sideline: the libero may not serve.", "Walk across the back from zone 5 to zone 1: the middle pair resets."), and everyone else reads it with that player's name. Otherwise it is your `move` note for the phase; Rotation has no caption. The rotate step and its caption are gone. This replaces the other stages of #20 and the `EXIT` walk of #21.
- **Alternatives:** put the exchange text in the explanation below the court.
- **Reversible by:** `stillStage()` and `phaseStages()` in `src/template.html`.
- **Changed by entry 50 (#60):** at Reception with the animation on, this caption shows in the play's lead-in; at rest the caption is the base defence line.
- **Changed back by entry 55 (#65):** Reception rests on the reception spots again, with this caption.

### 32. The server stands behind the end line in the Our serve picture

- **Issue:** #47
- **Problem:** Our serve must start and end on its still picture, and that picture had every server, SUB included, on the base spot while the caption and route said they serve from behind the end line first.
- **Decision:** In Learn the Our serve still picture puts the server on the serve spot behind the end line, with the route to the base spot. The animation is the serve (ball over the net), then the run to base. SUB in Simplified R3 and R6 reads "Come on for the libero: you serve from the spot behind the end line." Drill and Match still grade the base spot, and `players()` is unchanged.
- **Alternatives:** keep the server on the base spot and let the animation walk them out to the serve spot first (the picture then shows where they end, not where they start).
- **Reversible by:** `learnSpots()`, `SERVE_HIT` and `SWAP_NOTES.serve` in `src/template.html`.
- **Replaced by entry 50 (#60):** at rest the server stands at base; the play starts on the serve spot (`playStart()`).

### 33. Reception captions read as standing

- **Issue:** #47
- **Problem:** At rest and while their serve is in the air, players stand on their reception spot, but the R1 opposite's `rec` note said "Go to the left sideline …".
- **Decision:** The R1 OP note now reads "Stand at the left sideline on the 3 m line: in R1 the opposite plays left." Every other `rec` note already says Stand, Receive, Hide or Start. These notes show on the Reception still picture, where players stand on their reception spot (since #65; in #60 and #55 only in the play's lead-in), and with reduced motion. The Our serve notes ("Cross to zone 4 …") are kept: the owner likes that content, and the audit ties them to the zone.
- **Alternatives:** show a `rec` note only to a player who moves in that stage (most players would then see the setter's caption).
- **Reversible by:** the R1 `move["rec"]["OP"]` note in `src/data.py`.

### 34. Official exchange captions at the Rotation step

- **Issue:** #22
- **Problem:** §4.9 gives one caption per rotation for R3 and R6 ("The libero leaves; MB2 comes on in zone 4. MB1 is in zone 1 and serves."), but a still caption is written to your role, and the serving middle had no caption at all.
- **Decision:** L reads "Go off at the sideline: MB2 comes on in zone 4 and MB1 serves from zone 1.", the middle who comes on keeps "Come on for the libero and take zone 4.", the serving middle reads "Rotate to zone 1 and serve: the libero may not serve, so you stay on.", and everyone else reads the §4.9 sentence without a name. The Reception exchange captions after the serve rally are kept. Nothing animates, as #47 decided. This replaces the generic Official captions of #23.
- **Alternatives:** the §4.9 sentence for everyone; prefix it with the rotation name.
- **Reversible by:** the `middleServes()` block in `stillStage()` in `src/template.html`.

### 35. Where the libero rule text shows

- **Issue:** #22
- **Problem:** §4.9 says the caption states rule 19.3 (back row only, no serve, block or attack above the net, a completed rally between two replacements). That is about 180 characters; a caption holds 90.
- **Decision:** In Official, the explanation under the court adds the 19.3 text on every screen that follows a libero exchange: Rotation and Reception in R3 and R6. The libero's rules to remember carry it with the finger-set rule, and the libero's After reception text adds "If you set with fingers from the front zone, nobody may attack that ball above the net." Simplified shows none of it: there SUB is a training substitute.
- **Alternatives:** on every Official screen; in the caption as a third line; in Simplified too.
- **Reversible by:** `LIBERO_RULE`, `FINGER_SET` and `@LRULES` in `src/template.html`.

### 36. rules-official on by default

- **Issue:** #22
- **Problem:** #1 kept `rules-official` off by default until Official was finished. #22 finishes it.
- **Decision:** The built-in default of `rules-official` is on, as `learn-animation` in #23; the PostHog flag stays off until the owner checks it on a phone. Simplified stays the default rule set; Official is one tap away in the role sheet. #11 still applies when the flag is off.
- **Alternatives:** keep the default off until the coach answers questions 1 and 5 on #16.
- **Reversible by:** `FEATURES["rules-official"]` in `src/template.html`.

### 37. What the Reception animation shows after the pass

- **Issue:** #49
- **Problem:** The owner wants Reception to play the receive, the set and the spike, with the team moving as it really does. The guide shows the reception shape, the moves to the approach spots, the approach arrows to the net and the back row's moves "after the attacking action" (rule of thumb 03), but not who is set, where the cover stands or when each move starts.
- **Decision:** Four stages, from coaching sources (below) until the coach answers. 1: their serve to the libero, the setter releases (as #30). 2: the pass to the setter, the attackers to their `ar` approach spots (as #30). 3: the set goes to the leftmost front-row attacker (zone 4), the safe club-level first set. That hitter jumps to contact near the net (y 0.08). Every other attacker finishes the approach to hold the block: front row at take-off about 1.5 m off the net (y 0.17), back row behind the 3 m line (y 0.50). A 3-2 cup forms: the setter, the nearest front-row player who is not hitting, and the libero close and low, 2 to 3 m from the hitter; the rest stays deep, 4 to 6 m off, for wipes. 4: the spike; everyone goes to base defence by job (`BASE_DEF`), so a back-row setter defends zone 1. Then the Reception still picture comes back. Each stage has its own caption per player.
- **Sources:** coachingvb.com "Hitter coverage strategy" (3-2 cup) and "Setting the starting rotation in a 5-1" (first set to the outside); Sportplan attack coverage drills (close cover low, 2-3 m); Koach Volleyball pipe guide (back-row take-off behind the 3 m line).
- **Alternatives:** set a different hitter per rotation, or the middle; a 2-3 or 4-1 cover; keep the front row at the net after the spike.
- **Reversible by:** `phaseStages()`, `CUP_FRONT`, `SETTER_STEP`, `DEEP_Y`, `HIT_Y`, `APPROACH_Y`, `BACK_HIT_Y`, `baseSpots()` and `ATTACK_NOTES` in `src/template.html`. Coach question 9 on #16.
- **Updated in #53:** the cup of stage 3 sent the setter up to 0.3 across the court and L on a cross-court sprint. Now the setter follows a step from the set spot (`SETTER_STEP`, within 0.2), the middle approaches for the quick and then drops in low 2 to 3 m from the hitter (`CUP_FRONT`), L covers from the guide's zone 5 spot and the back-row outside hitter stays deep (entries 44 to 46). `CUP` and `DEEP` are gone.

### 38. Where the animation controls sit on the court panel

- **Issue:** #49
- **Problem:** The owner wants Replay, Pause, Step and speed on the court. The strip below the end line holds the "off court" pill on the left and, at Our serve, the server on the serve spot on the right; four 44 px buttons do not fit between them.
- **Decision:** The court panel (`#lPanel`) grows by one bar under the court drawing: the stage dots on the left, the four buttons on the right, on the same gradient. The bar keeps its height on Rotation and After reception (buttons hidden), so the caption does not jump between screens; with reduced motion or `?anim=0` it is gone. The sticky row holds only Next.
- **Alternatives:** overlay the buttons on the strip below the end line (covers the server at Our serve); smaller buttons (under 44 px).
- **Reversible by:** `#lPanel` and `#lAnim` in `src/template.html`.
- **Updated in #55:** Base plays, so the buttons are hidden only on Rotation.

### 39. The Next button on Reception

- **Issue:** #49
- **Problem:** The owner asked to rename the button "Next: After reception ▸" to "After". The other steps still read "Next: Our serve ▸" and so on.
- **Decision:** Only the Reception button changes: it reads "After ▸" (aria-label "Next: After reception"). The others keep "Next: … ▸", now always in full because the animation controls left the row. The phase chip reads "After" and the title tag "After reception", as before. Reception now plays on to the spike and base defence, but the After reception screen still shows the earlier moment at the pass (the attackers on their approach spots); Next goes back in time by one contact there.
- **Alternatives:** "Next: After ▸"; drop "Next:" on every button.
- **Reversible by:** the `lNext` label in `renderLearn()` in `src/template.html`.
- **Updated in #55:** the fourth screen is Base, so the button on Reception reads "Base ▸" (aria-label "Next: Base") and Next no longer goes back in time (entry 51).

### 40. The ball and the movement trails

- **Issue:** #49
- **Problem:** The owner wants a ball that looks like a volleyball, and faded dashed lines to trace where each player came from. Neither has a design in `docs/v2.md`.
- **Decision:** The ball is an inline SVG volleyball (white with a blue and a yellow panel and dark seams, fixed colours in both themes), 0.65 × the marker radius, growing 15% at the top of each flight and turning once; it meets a player at the marker edge, so the label stays readable. Each move leaves a dashed line (1 unit, dash 2/1.6, 60% opacity) in the player's `--route-*` colour, drawn under the markers and growing with the move; the lines stay through the hold, Pause and Step and clear with the still picture, Replay or a screen change. A move shorter than 1% of the court leaves none.
- **Alternatives:** a plain white ball, larger; trails only for your player.
- **Reversible by:** `BALL_SVG`, `BALL_R`, the `.trail` lines in `animPlay()` and `paintAnim()` in `src/template.html`.
- **Updated in #53:** trails that built up over four stages covered the court. Now a trail follows the mover's path (a polyline, so a route round a player shows as one), only the current stage's trails show, and the previous stage's fade out over 400 ms (`TRAIL_FADE_MS`) as the next starts. They still stay through the hold, Pause and Step.

### 41. Rules of thumb for both rule sets

- **Issue:** #23
- **Problem:** The issue asks for Rules of thumb worded for both rule sets (MB, SUB, libero). The five v1 rules read the same in both; none says who plays the middle, and the Match hints cited rules by a fixed number that was one too low.
- **Decision:** A new third rule on the middles, with one wording per rule set: Simplified "MB plays the front middle, L the back middle" (the pair reset into R3 and R6, SUB serves there), Official "The libero replaces the back-row middle" (which middle per rotation, the libero may never serve, the middle serves in R3 and R6 until the side-out, FIVB 19.3). It is marked "your rule" for the middles and the libero. The other five keep their v1 text. Each rule has a key; the hints cite "rule N of the Rules of thumb" from the key; when `learn-guides` is off they give the advice without a rule number. The fold stays closed by default, as in v1.
- **Alternatives:** keep five rules and add the middle text to rule 2; cite rules by title only.
- **Reversible by:** `THUMB`, `thumbRef()` and `@THUMB_MIDDLES_*` in `ruleText()` in `src/template.html`.

### 42. Who passes the serve in Reception

- **Issue:** #53
- **Problem:** The Reception animation sent every serve to L. Guide rule 01 names the receivers (the libero and the two outside hitters) but not who takes the serve in each rotation, and a real serve goes anywhere.
- **Decision:** The passer rotates among the three receivers, so each is shown passing twice: R1 L, R2 OH2, R3 OH1, R4 L, R5 OH1, R6 OH2 (`PASSER`), the same in both rule sets. The serve comes to the receiver named for that rotation, the passer gets "Their serve comes to you", the setter's line and the team line name the passer. A passing front-row attacker gets "Pass high to the setter, then get out to the 3 m line to attack."
- **Alternatives:** always L (v1 of the animation); the receiver in the middle of the shape; a random receiver per play.
- **Reversible by:** `PASSER` in `src/template.html`. Coach question on #16.

### 43. Attackers who do not receive leave at the serve contact

- **Issue:** #53
- **Problem:** The animation held the attackers until the pass, but movement is free from the server's first movement (#44) and the guide's arrows start at the serve.
- **Decision:** Stage 1 moves the setter and every attacker who is not a receiver to their `ar` spots at the serve contact; the receivers move after the pass. Attackers never wait in stage 1. The setter may: in R2 OP starts in front of the set spot, so the setter leaves 1 s after the contact, once OP is out of the way.
- **Alternatives:** release at the pass (#37); release everyone, receivers included, at the contact.
- **Reversible by:** `released` and `noWait` in `buildStages()` in `src/template.html`.

### 44. The setter covers from the set spot

- **Issue:** #53
- **Problem:** The 3-2 cup placed the setter 2 to 3 m from a zone 4 hitter, which in R1 meant a run of about 3 m across the net zone right after setting.
- **Decision:** The setter follows the ball a step towards the hitter and off the net (0.1 left, 0.1 back) and stays within 0.2 of the set spot, from where it covers tips and blocked balls. The caption says "Set X in zone 4, then follow a step or two to cover the tip."
- **Alternatives:** the full cup spot (#37); the setter stays on the set spot.
- **Reversible by:** `SETTER_STEP` in `src/template.html`.
- **Superseded in #72:** the setter now takes its 3-2 cover spot, see [#68](#68-a-real-3-2-cover-round-the-hitter).

### 45. L covers from the guide's zone 5 spot

- **Issue:** #53
- **Problem:** The cup ran L across the court in front of the deep outside hitter. The guide's after-reception picture already has L in zone 5 at about y 0.72, behind the zone 4 attack.
- **Decision:** L does not move in stage 3: it covers from its `ar` spot, reached in stage 2. In R3, R4 and R6 L curves behind the deep outside hitter where the two cross; in R1 OH2 curves behind L, which runs straight; in R2 and R5 nobody crosses. The caption: "Cover X from zone 5: play a ball the block sends back."
- **Alternatives:** L in the close cup (#37).
- **Reversible by:** the L branch of stage 3 in `buildStages()` in `src/template.html`.
- **Superseded in #72:** the L now takes its 3-2 cover spot, see [#68](#68-a-real-3-2-cover-round-the-hitter).

### 46. The deep outside hitter stays deep

- **Issue:** #53
- **Problem:** The back-row outside hitter came forward into the cup and back again, which the guide does not draw.
- **Decision:** The back-row outside hitter goes to y 0.86 or deeper at the set (`DEEP_Y`, the zone 6 base depth) and never comes forward of its reception or after-reception spot before the spike; it covers wipes deep.
- **Alternatives:** the deep cup spot (#37).
- **Reversible by:** `DEEP_Y` in `src/template.html`.
- **Superseded in #72:** the deep outside hitter now takes its 3-2 cover spot, see [#68](#68-a-real-3-2-cover-round-the-hitter).

### 47. Paths, speed and waiting

- **Issue:** #53
- **Problem:** Moves were straight lines of 600 to 900 ms whatever the distance, so long runs went at 10 m/s and markers passed through each other (R1 OP and OH1 at the spike).
- **Decision:** Each move takes 2.5 s per court width (at least 400 ms), eased in and out over a quarter each, so the top speed is about 4.8 m/s (1 unit = 9 m). A planner places the movers one by one, shortest move first, each with the cheapest start delay (0 to 1.3 s) and path that keeps a marker width plus its ring (`GAP`, 0.14) from everyone at every 15 ms. A path is straight or goes round one player met through one waypoint, 1.3 or 1.7 `GAP` to the side; it never turns back and is at most 1.3 times the straight line. Going round in front costs more than any wait (`NET_SIDE_COST`), so players pass behind each other. After the spike, front-row players who switch sides (R1 OP and OH1) pass behind the middle through fixed waypoints (`SWITCH_VIA`), the one going left deeper, so they cross once. Moves under 0.04 left by a `clearOf()` stop are dropped, except in the last stage, which ends exactly on base defence. A stage lasts as long as its longest move. Reception takes 7.5 to 11 s at 1× including the spike and base defence (since #65; in #55 it stopped at the spike, 6.5 to 8 s), and Base 2 to 4.5 s. The only waits: the setter at the contact in R2 (1 s, entry 43), L after the pass in R1 (0.3 s), OH1 at the spike in R1 (0.15 s), and the setter at the set (0.45 to 0.6 s), so it follows the ball.
- **Alternatives:** faster runs (5 to 7 m/s, closer to a real sprint but hard to follow); straight lines with waits only; fixed choreographed routes per rotation.
- **Reversible by:** `MS_PER_UNIT`, `EASE_PART`, `GAP`, `MIN_MOVE`, `DELAYS`, `NET_SIDE_COST`, `SWITCH_VIA`, `detours()` and `planStage()` in `src/template.html`.

### 48. The server runs in at the serve contact

- **Issue:** #53
- **Problem:** Our serve played the serve, then the run to base as a second stage, so the server stood still while the ball flew.
- **Decision:** One stage: the server runs in at the contact while the ball crosses the net (about 2 s). The caption says "Serve from the spot behind the end line, then run in at once." With reduced motion the caption shows that line only, not a list. In R3 and R6 the off-court libero's Our serve caption says to wait at the sideline while the middle (Official) or SUB (Simplified) serves, in both rule sets.
- **Alternatives:** two stages (#30).
- **Reversible by:** the `serve` branch of `buildStages()` and `OFF_SERVE` in `src/template.html`.

### 49. The PDF downloads are removed

- **Issue:** #57
- **Problem:** The owner asked to remove the download option of the PDFs. The printable cheat sheets were v1 pictures in the old colours, and #56 planned a cheat-sheet box to replace them.
- **Decision:** The Downloads card, the `downloads` flag, the `download` event, the embedded PDFs and their generators (`gen_schema.py`, `gen_sets.py`, `pdf.py`, `downloads/`, `cairosvg`) are gone. A stored `ksv51:ffOverride`, `ksv51:flags` or PostHog value for `downloads` is ignored. #56 is closed as superseded. Coach question 8 now asks only about the all-rotations table.
- **Alternatives:** keep the downloads behind the flag, off; regenerate the sheets in the v2 colours (#56).
- **Reversible by:** reverting the #57 PR.

### 50. Play on demand, and the still picture is where the play ends

- **Issue:** #60
- **Problem:** The owner asked that nothing plays on its own, that Play "buzzes" once per open screen, and that every screen opens on "the screen you see when animation is over, not the beginning". Reception plays through the spike to base defence, so its end is not where you stand to receive, and the overlap limits belong to the reception spots at the whistle. After reception (the next screen) is earlier in the rally than that end.
- **Decision:** Taken literally. Our serve opens with the server at base; Reception opens on base defence, with no overlap lines and the caption for base defence. Play starts with a 700 ms lead-in on the start picture: the server on the serve spot, or everyone on their reception spot with the overlap limits drawn and the exchange or `rec` caption. At rest the explanation below the court has no overlap text; the overlap text shows with the lines in the lead-in, also when paused there. With reduced motion or `?anim=0` there is no play to end, so Reception keeps the reception spots and the lines. One 700 ms pulse on Play per open, never looping; a role or rules change is not an open. Drill and Match grading is unchanged.
- **Alternatives:** keep the reception spots as the Reception rest picture (the "end" of getting ready to receive) and stop the play there or snap back; draw the reception spots as ghosts under base defence.
- **Reversible by:** `renderLearn()` (`played`, `drawn`), `restCaption()`, `LEAD_MS`, `playStart()` and `nudgePlay()` in `src/template.html`.
- **Updated in #55:** the play is split at the spike. Reception rests on our spike (attackers on their `ar` spots, the cover formed) with a cue for your job at the spike; the reception text and overlap limits stay in the lead-in. Base plays the spike to base defence and rests there, with the controls and the Play nudge (entry 51).
- **Reversed for Reception in #65:** the owner: "It should show how players are positioned to receive the ball, not how they are positioned after the ball has been received. On serve it makes sense to show positions after the serve, because there are no position faults there. On reception I want to learn how to prepare to receive the serve, and the animation shows what to do after. When the animation is done, it should fade out and show the serve-receive positions again." Reception rests on the reception spots with the overlap limits and the reception cue (entry 55). Our serve and Base still rest where their play ends.
- **Updated in #64:** the owner saw the pulse move the whole layout. The nudge is now colour only (fill and border to `--accent`, icon `--on-accent`); the layout moved because the setup sheet's `.nudge` rule (margin, padding, border) also matched Play, which is now scoped to `#setupNudge`.

### 51. Learn's fourth screen is Base; Drill and Match call the step Attack

- **Issue:** #55
- **Problem:** After reception showed the pass moment (attackers on their approach spots) after a Reception play that ended on base defence, so Next went back in time. The owner asked for a Base screen after our attack. Drill and Match grade the `ar` spots, which are the attack, not base.
- **Decision:** In Learn the `ar` step is Base: the phase chip, the title tag ("R1 (S1) · Base") and Next on Reception ("Base ▸"). Reception plays serve, pass and set and rests on the spike frame; Base plays one stage, the spike to base defence by job (`baseSpots()` on `BASE_DEF`), and rests there. Base draws no routes and no overlap limits; its cue reads "Our attack is over the net: defend." and says when the spot is the same as after our serve. In Drill, Match and the all-rotations table the same step is "Attack" and still grades the `ar` spots. A Drill/Match Defend step is #62.
- **Alternatives:** keep After reception and stop Reception at the pass; add Base as a fifth Learn step and keep After reception.
- **Reversible by:** `PHASES`, `LEARN_NAME`, `FULL`, `STEP_SHORT`, `cutPlay()`, `learnPlayers()`, `baseCue()` in `src/template.html`.
- **Changed in #65:** Reception plays on through the spike to base defence again and rests on the reception spots; Base keeps its screen and replays that last stage (entry 56).

### 52. The front row at base after our attack

- **Issue:** #55
- **Problem:** The guide shows no base spots after our attack. Where the front row waits (at the net, ready to block, or off the net) and whether KSV defends perimeter or rotational is not known.
- **Decision:** The same `BASE_DEF` spots as at Our serve: front row mid-zone at y 0.21, back row deep, by job (OH 4, MB 3, S/OP 2; S/OP 1, L 5, OH 6). The R1 OP/OH1 side switch at base stays (coach question 11). Coach question 12 on #16.
- **Alternatives:** front row at the net (y 0.05 to 0.1) ready to block; a rotational defence with the setter's base elsewhere.
- **Reversible by:** `BASE_DEF` in `src/data.py`, `baseSpots()` and `SWITCH_VIA` in `src/template.html`.

### 53. What the Reception rest cue says

- **Issue:** #55
- **Problem:** With Reception resting on the spike, the reception text and overlap limits describe a picture that is not on the court.
- **Decision:** At rest the cue gives your job at the spike (`SPIKE_CUE`: hit, approach to hold the block, close cover, setter cover, L cover, deep cover), with the hitter named; the reception text and overlap limits show in the lead-in, also when paused there. With reduced motion or `?anim=0` Reception keeps the reception spots, text and limits.
- **Alternatives:** keep the reception text at rest under a spike picture.
- **Reversible by:** `spikeCue()`, `SPIKE_CUE` and `learnCue` in `renderLearn()` in `src/template.html`.
- **Reversed in #65:** Reception rests on the reception spots, so the cue is the reception text with the overlap limits again; `spikeCue()`, `SPIKE_CUE` and `learnCue` are gone. The owner: "On reception I want to learn how to prepare to receive the serve, and the animation shows what to do after." The spike jobs stay in the stage captions.

### 54. Where the ball shows on the still pictures

- **Issue:** #55
- **Problem:** The owner wants the ball on the stills, not on Rotation, and not covering a label. No spot is given.
- **Decision:** The ball rests where the play leaves it: over the net on their side at Our serve (`SERVE_BALL`) and Base (`SPIKE_BALL`), at the hitter's hand at Reception (at the marker edge). With no animation Reception shows it at their serve (`THEIR_SERVE`). In a lead-in the ball waits where the first stage starts: with our server, at their serve, or at the hitter's hand. The tests check it stays a marker radius from every marker.
- **Alternatives:** the ball only at Reception; the ball in the passer's hands at Reception.
- **Reversible by:** `restBall()`, `ballSvg()` and `paintAnim()` in `src/template.html`.
- **Changed in #65:** Reception shows no ball at rest, with or without the animation: the still is the whistle picture. In its play the ball starts at their serve and ends over the net on their side (`SPIKE_BALL`).

### 55. Reception rests on the reception spots and fades back after the play

- **Issue:** #65
- **Problem:** The owner wants Reception to show how to stand to receive, play what happens after, and come back to the reception picture. #60 and #55 rested it on the spike and put the reception spots in a 700 ms lead-in.
- **Decision:** At rest Reception shows the `rec` spots with your overlap limit lines, the reception cue with the overlap text and no ball, in every rotation, both rule sets and with or without the animation. Play has no lead-in: the still is already the whistle picture, so the serve starts at once and the lines go. It plays four stages: serve, pass, set, then the spike over the net with everyone to base defence. When Play runs to the end, the markers, trails and ball fade out over 400 ms and the markers and lines fade back in. Pause keeps its frame. Step stops at the end of each stage and stays on the last one; Play or Replay runs on from there. During the fade-back, Play and Step start the play again.
- **Alternatives:** keep the 700 ms lead-in on the reception spots; snap back without a fade; let Step on the last stage fade back.
- **Reversible by:** `phaseStages()` (`fadeBack`, the `0` lead), `fadeBack()`, `animStep()` and the `played` check in `renderLearn()` in `src/template.html`.

### 56. Base replays the last Reception stage

- **Issue:** #65
- **Problem:** Reception now plays on to base defence, so Base's play (the spike to base defence) repeats Reception's last stage.
- **Decision:** Keep Base as it is: its own screen after Reception, resting on base defence with the ball over the net and the "Our attack is over the net: defend." cue. Its play starts on the spike picture after a 700 ms lead-in and plays the same last stage. The repeat is short (2 to 4.5 s) and lets you look at base defence on its own; Drill and Match still grade the `ar` spots as Attack.
- **Alternatives:** drop Base's play and keep only its still picture; remove the Base screen from Learn.
- **Reversible by:** `cutPlay()` and `learnPlayers()` in `src/template.html`.

### 57. Our serve is a static screen

- **Issue:** #69
- **Problem:** The Our serve play showed only the server walking from behind the end line to base. The owner: "Remove animation from 'our serve' - they add no value."
- **Decision:** Our serve is static like Rotation: no Play, Replay, Step, speed or stage dots (the bar keeps its height, invisible), no Play nudge, nothing plays. The still picture is unchanged: everyone on the base spot, the server at base with the route from the serve spot, the ball over the net (`SERVE_BALL`), and the same still caption (exchanges, `OFF_SERVE`, `LIBERO_RULE`). Drill and Match still grade the serve spots.
- **Alternatives:** keep the play but drop the nudge; play the serve with the whole team moving to base.
- **Reversible by:** `animPhase()`, `phaseStages()` and `buildReception()` in `src/template.html` (the serve stage and `SERVE_HIT` are in git history before #69).

### 58. The middle's quick approach runs during the pass

- **Issue:** #70
- **Problem:** In the Reception play the middle stood at the 3 m line (its `ar` spot, y 0.44) when the pass reached the setter and ran its approach during the set. The owner: for a quick the middle takes off as the setter touches the ball, and standing in the centre at the 3 m line blocks the back-row hitter's run-up.
- **Decision:** Stage 1 is unchanged (the middle leaves the net for its `ar` spot at the serve contact). In stage 2 the middle runs straight from there to take-off at `APPROACH_Y` (0.17), 0.15 left of the set spot, and the pass reaches the setter as the middle arrives (the ball is synced to the middle's run). In stage 3 the middle fakes the quick and only drops back to cover beside the hitter (`CUP_FRONT`, now y 0.20 so the move never goes towards the net). Captions: "Run in for the quick in front of the setter as the pass comes." and "Fake the quick, then drop in low to cover <hitter>." Drill and Match still grade the `ar` spot.
- **Alternatives:** run the approach straight from the reception spot during the serve, never stopping at the 3 m line; keep the cover at y 0.15 with a small step towards the net.
- **Reversible by:** `buildReception()` (`takeOff`, the stage 2 `sync`), `CUP_FRONT` and `ATTACK_NOTES.quick`/`cupFront` in `src/template.html`.

### 59. The Reception ball never waits; long runs carry on

- **Issue:** #71
- **Problem:** A Reception stage lasted as long as its slowest mover plus a 900 ms hold, so the passer held the serve about 1.2 s (R1) and the setter held the pass about 2.4 s (R3, R6: L's cross-court run). L also went round the standing passer along the end line (y 0.91-0.94) in R3, R4 and R6.
- **Decision:** A stage lasts as long as its ball flies, plus 150 ms for the next contact: their serve 1 s, the pass at least 1 s (longer only until the setter reaches the set spot, R1 about 1.05 s), the set until the hitter arrives. The middle starts its quick approach so it reaches take-off as the pass lands (#70 kept). A run longer than its stage carries on into the next stages; the player's next move starts when it ends, and the planner avoids it. The 900 ms hold comes only after the last stage, when the ball is over the net. A detour stays in front of y 0.85 unless the run starts or ends deeper, so L crosses in front of the passer and stays in front of y 0.85. A trail shows through its stage and while its run carries on. Reception now takes about 5 to 7 s at 1×. The caption shows only your own line and changes when you get a new one; each line stays at least 2.5 s of play (5 s at 0.5×), a line due earlier waits, and lines still waiting at the end are dropped. After the play fades back, the reception cue stays and a numbered "Then:" list gives your four stage lines.
- **Alternatives:** keep a hold between stages with the ball frozen in the air; have the passer (deep OH) move first and L go behind; slow every flight to fit the longest run; slow the play to the caption pace instead of pacing the captions.
- **Reversible by:** `buildReception()` (`CONTACT_MS`, `PASS_MS`, the carry), `planStage()` (`carry`, `arrive`), `DEEP_LIMIT` in `detours()`, the trail fade in `paintAnim()`, and `CAPTION_MS`, `captionPlan()` and `restList` in `src/template.html`.

### 60. Role and rules as a dropdown list under the header button

- **Issue:** #76
- **Problem:** The owner: "rules and position selection should be to select from the top corner and should be more visible, should be as a unrolled list not as a pop up." The role chip showed only the role code and opened a modal bottom sheet with a backdrop.
- **Decision:** Read "top corner" as the header's top-right button and "unrolled list" as a dropdown anchored under it, with no backdrop and no inert page. The button has the accent fill and reads the role name and the rules mode on one line ("Outside 1 · Simplified ▾"). The list shows the roles one per line with a colour swatch and a tick on yours, then the Rules switch with a one-line note (the long Simplified and Official explanations are shortened; the full wording stays in Rules of thumb). A role or rules pick closes the list at once, as do a tap outside (which then does nothing else, so it cannot answer on a court), Escape, a second tap and Tab past the list; the Done button is gone. The title now wraps to two lines on a 390 px phone, so the header is about 18 px taller.
- **Replaces:** 7 (the chip shows only the role code) and 8 (the modal bottom sheet).
- **Alternatives:** keep the sheet and only make the chip bigger; list the rules first; keep the list open after a rules pick; shrink the title to keep one header line.
- **Reversible by:** the `#setup` markup in the header, `.rolechip`, `.menu` and `.role` CSS, and `renderSetupSummary()`/`setSetupOpen()` in `src/template.html`.

### 61. The Attack step shows the reception spots and the pass

- **Issue:** #81
- **Problem:** The owner: the Attack step ("Where do you go after the pass?") asks for a move from A to B, but the court did not show A. Teammates showed only as Show on court allowed, on their `ar` spots (the answers). Later addition: "also show where is the ball".
- **Decision:** Before the answer, Drill and Match (solo, same device, online) draw everyone on their reception spot (place A) whatever Show on court is set to: teammates faded, you ringed with a "from" label, nobody on an `ar` spot. The picture is the moment of the pass: the ball is held by the passer, at `HELD` from their marker towards the set spot, with a dashed pass line to the setter's `ar` spot. The passer is the Learn Reception passer (`PASSER`, entry 42). The question names the passer ("OH1 passes to the setter. Where do you go?", or "You pass to the setter. Where do you go?"). A tap draws a thin line from A. Because A is part of the question, the Attack step scores ×1 for Show on court in every mode, a solo peek at it does not count as a peek, and the breakdown shows no multiplier. Show on court still applies to the other steps. The in-play picker stays visible at the Attack step. The help ring still hints at B.
- **Alternatives:** keep Show on court for the teammates and show only your own A; hide the in-play picker at the Attack step; show the ball at the setter (the moment of the set).
- **Reversible by:** `fromLayer()`, `arQuestion()`, the `ar` branch in `gVisMult()` and the peek count in `gAnswer()` in `src/template.html`. The peek is gone since #132.

### 62. "4" is the middle's low quick; "Po" and "Til" removed

- **Issue:** #82
- **Problem:** The guide's Front row sets page draws "4" landing just in front of the setter with a steep, high arc, and also draws "Po" and "Til". The app inferred "4" as a high set and marked "4" and "Po" "(not confirmed)". A web search (Danish and English) found no source for "Po" or "Til".
- **Decision:** Owner input, 2026-09-30: "4" is the middle's short, low quick in front of the setter, close to the net (x 0.56, peak 0.16). The owner does not know "Po" or "Til", and no Danish source names them, so both are removed from `SETS`, the Sets tab, the quiz and the set call check. Re-add them from the guide if the coach explains them (#16, question 7). `UNCONFIRMED_SETS` is empty; the mechanism stays for a future unconfirmed set. Stored data holds no set names; an online answer naming a removed set is dropped by `onClean()`.
- **Alternatives:** keep "Po" and "Til" from the guide drawing, marked "(not confirmed)"; keep "4" as the guide draws it.
- **Reversible by:** adding the rows back to `SETS` in `src/data.py` (with a name in `UNCONFIRMED_SETS` to keep it out of match questions).

### 63. Back-row sets A, B and C

- **Issue:** #82
- **Problem:** The owner named three back-row sets that the guide does not show: A to zone 1, B to zone 6 (the pipe) and C to zone 5. The Sets net diagram is a front view, so it cannot show depth.
- **Decision:** A new `back` family (`--set-back`, teal `#0f766e` light and `#4fd1c5` dark, at least 4.5 on `--panel`, checked by `theme_test.py`). Seen from our side, C lands at x 0.17, B at 0.50 and A at 0.83, each with a peak of about 0.62-0.66 (a medium-high ball). They are drawn dashed with a hollow landing dot, and their chips have a dashed border; the text says they land behind the 3 m line.
- **Alternatives:** draw them below the net as if closer to the viewer; a second, top-down diagram for back sets.
- **Reversible by:** the `back` rows in `SETS` in `src/data.py`, and `FAMCOL`, `FAMNAME`, `.setchip.back` and the dashed path in `netSvg()` in `src/template.html`.

### 64. Set call check lanes

- **Issue:** #82
- **Problem:** With "Po" and "Til" gone the middle lane had only Shoot and "4", and back-row attackers were asked any set.
- **Decision:** `setQ()` keeps asking from each set's family and landing: zone 4 is asked 1, 0 or 2; the middle Shoot or 4; zone 2 7 or 6. A back-row attacker (`ar` kind `back`) is asked the back set of the third it attacks from (zone 1 → A, zone 6 → B, zone 5 → C), with the prompt "The setter sets this ball for you." In the current data only OP attacks from the back row (zone 1, R4-R6), so only A is asked there; B and C are in the setter's and the other players' questions and the quiz. There are always four options: the asked set, one from its family, and two others from the ten sets.
- **Alternatives:** ask back-row attackers all three back sets; ask the middle 4 only.
- **Reversible by:** `setLane()`, `third()` and `setQ()` in `src/template.html`.

### 65. Light mode by default

- **Issue:** #84
- **Problem:** The owner: make day (light) mode the default. With nothing stored, the app followed the system scheme, so a phone in dark mode opened dark.
- **Decision:** With no stored `ksv51:theme` the app opens light, whatever the system says. The `prefers-color-scheme: dark` CSS block is removed, so the first paint is light with no flash; the dark tokens stay under `[data-theme="dark"]`. The header button still switches, and a stored choice still wins. A change of the system scheme no longer repaints the button.
- **Alternatives:** set `data-theme="light"` at start-up and keep the media block (the block would never apply and would duplicate the dark tokens).
- **Reversible by:** the dark `@media (prefers-color-scheme: dark)` block in the `<style>` block and `paintThemeButton()` in `src/template.html`.

### 66. Step back from Base's still, and where a paused frame's caption shows

- **Issue:** #79
- **Problem:** The issue says Step back is disabled on the start picture. Reception's still is its start picture, but Base's still is where its play ends (base defence), so the issue does not say what Step back does there. Paused frames also showed their caption at the fade-in opacity of the moment they stopped, so a new line that starts at a stage end was invisible.
- **Decision:** On Base's still Step back is enabled and goes to the end of the stage before the last; Base has one stage, so that is the lead-in start (the spike picture), where it is disabled. A paused frame (Pause, Step, Step back) shows its caption at full opacity, and it stays there when Step or Play goes on. To fit the sixth button at 44 × 44 in the 324 px court panel of a 390 × 664 screen, the bar's gap is 4 px (was 6) and the dots' gap 6 px (was 8).
- **Alternatives:** disable Step back on Base's still too; smaller buttons; the dots on their own line.
- **Reversible by:** `backTarget()` and `animPause()` in `src/template.html`, and the `.lanim` and `.ldots` gaps.

### 67. Where the H in rotation names is explained

- **Issue:** #78
- **Problem:** The owner asked for `R2 (H6)` instead of `R2 (S6)`, and the issue asks the app to explain the label wherever it explains it. The app had no text that explained the `S`.
- **Decision:** A new last entry in Rules of thumb (key `names`, for every role): "H in R2 (H6) is the setter", saying H is Danish hæver, the number is the setter's zone, and to find the setter first. It goes last so the numbers the Match hints cite do not change. No first-visit text is added.
- **Alternatives:** a line in the first-visit header subtitle; a tooltip on the Learn title tag; the entry first in the list.
- **Reversible by:** the `names` entry in `THUMB` in `src/template.html`.

### 68. A real 3-2 cover round the hitter

- **Issue:** #72
- **Problem:** The cover at the spike was not a cup: only the middle stood within about 2 m of the zone 4 hitter; the setter was 4 to 5 m away (#44), L 6 to 7 m (#45) and the deep outside hitter 7.7 m off the net (#46). The guide draws the after-reception spots, not the cover at the spike.
- **Decision:** A 3-2 cover. During the set the setter, the middle and L stand about 3 m (0.34) from the hitter, behind and inside it, in an arc, each at least a marker width (0.14) inside the hitter's lane: the setter nearest the net (hitter + 0.33 across, + 0.07 back), the middle (+ 0.26, + 0.21), L (+ 0.15, + 0.31). Two deep covers stand behind the gaps: the back-row outside hitter at (0.44, 0.56), and the attacker who neither hits nor fakes the quick at (0.62, 0.44): in R1 to R3 the front-row right-side attacker comes in from the sideline, in R4 to R6 the back-row opposite does not approach. L, the deep OH and the back-row opposite run straight on to their cover during the pass, so L does not stop at the guide's zone 5 spot. The set flies until the close cover stands, at most 1.1 s (0.85 to 0.9 s in every rotation), and lands as the hitter's planned run ends; a late cover covers from where it is. The setter sets from the set spot, so the setter's cover is up to 3 m from it. Captions: the setter "then follow in to cover X close on the right", the middle "cover X close, between the setter and L", L "Cover X close behind", the deep covers "Cover deep …". The coach question stays #16 Q9/Q10.
- **Alternatives:** L goes to the guide's zone 5 spot first and turns to the cover (an L-shaped run, and the set waits up to 1.6 s for it); the right-side attacker keeps its approach, a 3-1 cover; the deep outside hitter in the close cover instead of L where L passes from the right.
- **Reversible by:** `COVER`, `DEEP_COVER`, `SET_MAX_MS`, the pass stage's `onCover` and the set ball's `cover` list in `buildReception()` in `src/template.html`.
- **Amended in #119:** the back-row opposite waits for the pass before its run, see [#111](#111-the-back-row-opposite-waits-for-the-pass-then-runs-straight-to-cover); the close cover sits round the outside-in hit point, see [#114](#114-the-zone-4-hitter-approaches-outside-in).

### 69. Attack is graded where Learn has everyone as the pass lands

- **Issue:** #92
- **Problem:** The Attack step asks where you are as the pass reaches the setter. The data `ar` spots are where each player ends up after the pass (the front middle's is on the 3 m line, where the guide's approach starts). Learn's Reception play has some players elsewhere when the pass lands: the front middle at its take-off by the net (the owner says the middle goes to the middle of the front row), and, since the 3-2 cover (#68), L, the deep outside hitter and in R4 to R6 the back-row opposite on or towards their cover, 0.1 to 0.4 from their `ar` spots (in R4 L is the passer).
- **Decision:** Drill and Match grade every player at their position in the Learn Reception play at the moment the pass lands (stage 2 start plus the pass flight), one source for all roles. The feedback draws the run from the reception spot to that position; for the front middle, the run to the 3 m line, then the dashed approach to the take-off. `ROWS[].ar` is unchanged. The graded spots of the covers follow any change to the cover runs.
- **Alternatives:** grade the `ar` spots and move only the middle (disagrees with Learn for L); move the spots in the data (it would no longer match the guide's drawing); ask about the moment the setter sets.
- **Reversible by:** `answerSpots()` in `src/template.html`.
- **Amended in #119:** L, the deep outside hitter and the back-row opposite are graded on their cover spot, see [#112](#112-the-covers-are-graded-on-their-cover-spot).

### 70. The ball after an Attack answer is at the setter

- **Issue:** #92
- **Problem:** The Attack feedback had no ball. The graded moment has it at the setter, and a ball next to the set spot can cover a marker.
- **Decision:** After the answer (solo feedback, Drill and the multiplayer reveal) the ball is at `HELD` from the set spot. It goes on the passer's side first; if that covers a marker, then towards the right sideline, then behind. Before the answer the #81 picture stays: everyone on the reception spots and the ball at the passer.
- **Alternatives:** keep the ball at the passer after the answer; draw the ball on the setter's marker.
- **Reversible by:** `momentBall()` and `setterBall()` in `src/template.html`.

### 71. Our serve asks the server where they go

- **Issue:** #92, #102
- **Problem:** The server was asked "Where do you stand?" but is graded on their base spot after the serve.
- **Decision:** The server is asked "You serve. Where do you go after it?"; everyone else "We serve. Where do you stand?". #92 also drew the ball over the net at Our serve in Drill and Match, as on Learn's still; the owner removed it (#102: "remove ball from the net when we serve in the match - it doesn't make sense"). Drill and Match draw no ball at Our serve, before or after the answer or on the reveal. Learn's Our serve still keeps its ball.
- **Alternatives:** grade the server on the serve spot behind the end line.
- **Reversible by:** `serveQuestion()` in `src/template.html`.

### 72. Your answer after scoring is an accent dot

- **Issue:** #92
- **Problem:** After scoring, your tap was a small dark dot. On the Attack court it sat on the play's lines and read as part of the play.
- **Decision:** Solo Match and Drill draw your tap as the accent dot used for "your spot" before the answer (`tapMark()`, class `yourtap`), joined to the right spot by the thin dotted line as before. Same-device and online keep the small dark dot until the reveal, which marks each player's tap with their colour and initial.
- **Alternatives:** a label "you" on the tap.
- **Reversible by:** `tapMark()` in `src/template.html`.

### 73. Receive limits wait for the neighbour check

- **Issue:** #92
- **Problem:** The owner: "when you show answer in drill and match for recieve show the position limits compared to other players as you do it in learn section". The neighbour check comes after the Receive answer and asks for one of those limits, so lines drawn at once would give it away.
- **Decision:** After a Receive answer Drill and Match draw your limits as Learn does (`boundLines()` from your right spot) and add the overlap sentence to the feedback. With the neighbour check on, both wait until the check is answered; the check's own note already has the whistle rule, so the sentence then leaves it out. A Next press that skips the check shows no limits. An off-court player gets neither.
- **Alternatives:** draw the limits at once and drop the neighbour check at Receive; draw them at once and keep the check.
- **Reversible by:** `limitsLayer()`, `limitsHtml()` and `dShowLimits()` in `src/template.html`.

### 74. Which limits the multiplayer reveal draws

- **Issue:** #92
- **Problem:** The same-device and online reveal shows everyone's answers on one court. Each role's limits are two or three lines, so several roles' limits would cross each other.
- **Decision:** Online, each phone draws the limits of its own role. Same device draws them only when every player has the same role. The reveal's text list adds each on-court role's overlap sentence.
- **Alternatives:** draw every role's limits; none on the reveal.
- **Reversible by:** the `limitsLayer()` call in `mpReveal()` in `src/template.html`.

### 75. What goes with the Learn rules to remember box

- **Issue:** #91
- **Problem:** The owner asked to remove the "rules to remember" box from Learn. Its lists (`RULES`) and six `ruleText()` keys were used only there, including the libero's Official rules (`@LRULES`, see entry 35).
- **Decision:** The box, `RULES` and the keys only it read (`@MB1SERVE`, `@MB2SERVE`, `@LSLOT`, `@LSERVE`, `@LRULES`, `@OHSERVE`) are deleted; nothing replaces them. The libero rule (19.3) still shows in the hint on the Official R3 and R6 Rotation and Reception screens, and the finger-set rule in L's Base hint and Attack text in Drill and Match. Rules of thumb and the all-rotations table stay.
- **Alternatives:** move the lists into a fold like Rules of thumb; keep only the libero's list.
- **Reversible by:** the `#sheet` card and `RULES` in `src/template.html` before #91.

### 76. The title volleyball and a title that already wraps

- **Issue:** #91
- **Problem:** The task asks for the header on one line at 390 px. At 390 px the title "Where do I stand?" already wraps onto two lines beside the role button ("Outside 1 · Simplified ▾") and the theme button.
- **Decision:** "One line" is read as one header row: title, role button and theme button side by side, with no sideways scroll. The ball goes after "stand?", 0.7 em (the cap height of Barlow Condensed), decorative (`aria-hidden`), and adds no line to the title. The title keeps its two lines at 390 px.
- **Alternatives:** a smaller title so it fits one line; the ball before the title.
- **Reversible by:** `#titleBall` and `.titleball` in `src/template.html`.

### 77. Where the Learn hint goes below Next

- **Issue:** #91
- **Problem:** The owner asked to move the hint below the blue Next button. The hint also carries the Official libero rule and the finger-set rule.
- **Decision:** The hint (`#cue`) stays in the Learn card, right after the sticky Next row, with the libero and finger-set rules in it. Next sticks to the bottom only while its own place is below the screen, so it never covers the hint.
- **Alternatives:** the hint as its own card under the Learn card; the libero rules kept above Next.
- **Reversible by:** the order of `#lCtl` and `#cue` in `src/template.html`.

### 78. Base is a still screen

- **Issue:** #94
- **Problem:** The owner found the Base animation confusing: it replayed Reception's spike stage after a lead-in, so the same move played on two screens.
- **Decision:** The owner's call: only Reception animates. Base shows its still picture (base defence, the ball over the net, "Our attack is over the net: defend.") with the controls hidden, no Play nudge, and nothing plays. Reception's play still runs on to base defence and fades back. The Base-only code (`cutPlay()`, the lead-in `LEAD_MS`, `leadCaption()`, `ksvLearn.lead()`) is deleted.
- **Alternatives:** keep the Base play without its lead-in; play the whole rally at Base.
- **Reversible by:** `animPhase()` and `phaseStages()` in `src/template.html` before #94.

### 79. The Attack texts of the covers

- **Issue:** #92
- **Problem:** Since #89, Drill and Match grade L, the deep outside hitter and a back-row opposite on or towards their 3-2 cover spots as the pass lands. Their Attack texts still sent them elsewhere: "Cover left back (zone 5)", "Drop back to cover", and for the back-row opposite in R4 and R5 "Go straight to zone 1", though the setter sets zone 4 and the opposite covers deep.
- **Decision:** The hint, the feedback and the `move.ar` caption use the cover jobs of the Learn play (`ATTACK_NOTES`): L covers the hitter close behind, the deep OH covers deep behind the close cover, the back-row opposite comes in to cover deep, right of the middle. The Rules of thumb entry "The opposite moves directly to position 1" becomes "The back-row opposite covers deep". `audit.py` now wants "cover" in a back-row attacker's caption. The zone the player defends after the attack stays in the caption.
- **Alternatives:** keep the back-row attack to zone 1 and send the set there in R4 to R6; grade the covers on their `ar` spots again.
- **Reversible by:** `covers` in `buildReception()`, the `cover` branches of `describe()` and `gHint()`, and the `ar` captions in `src/data.py`.

### 82. A Drill steps change replaces the open question

- **Issue:** #98
- **Problem:** The issue says a change of the Drill steps applies from the next question, but not what happens to a question already on screen from a step you just switched off.
- **Decision:** An unanswered question from a step you switch off is replaced at once by one from the picked steps; an answered one keeps its feedback, and Next brings a picked step. A question from a step still picked stays. In Review weak spots, the items from switched-off steps are dropped from the rest of the review.
- **Alternatives:** always keep the open question until it is answered; start a new question on every change.
- **Reversible by:** the `#dSteps` click handler in `src/template.html`.

### 85. How Rotate grades each placed marker

- **Issue:** #99
- **Problem:** The issue asks for exact / close / off per marker, with right meaning every marker exact or close. At Rotate a "close" tap is in the next zone, which is a different rotation spot, so close would score a wrong zone as right.
- **Decision:** Rotate has no close grade. A marker is right when the tap is in its right zone, as the one-tap Rotate question graded it, and wrong otherwise. The question is right only when every marker is right, and counts as one item in stats and Review weak spots.
- **Alternatives:** close within 0.24 of the spot counted as right; exact only within 0.14 of the spot, as the other steps.
- **Reversible by:** `rotGrade()` in `src/template.html`.

### 86. Rotate when you are off court

- **Issue:** #99
- **Problem:** At Rotate some roles are off court: a back-row middle when the libero is in for them, and in Official R3 and R6 the libero. They have no overlap partners.
- **Decision:** They place the setter, then press "I'm off court" (or tap the off court pill) for themselves; the button toggles until your partners are asked (#88), so a second press puts you back to place. There are no partners to place. Marking yourself off when you are on court grades you off.
- **Alternatives:** skip the question for off-court roles; ask the setter only.
- **Reversible by:** `rotStart()` and the `#offBtn` handler in `src/template.html`.

### 87. Mixed names and the weak spots list

- **Issue:** #99
- **Problem:** Mixed is not defined further, and the "Needs practice" list named rotations as "R4 (H4)", which gives away the setter's zone while the Rotate question names only R.
- **Decision:** Mixed picks H or R at random for each question. The weak spots list names a Rotation item by R alone.
- **Alternatives:** alternate H and R; drop Rotation items from the list.
- **Reversible by:** `rotStart()` and `updateScore()` in `src/template.html`.

### 88. Your own marker is locked once your partners are asked

- **Issue:** #99
- **Problem:** Your partners' limits depend on where you stand. If you could still move your own marker while placing them, you could fit yourself to them afterwards.
- **Decision:** Once you have placed yourself (or pressed "I'm off court") and the partner steps begin, a tap on your marker does nothing and "I'm off court" no longer toggles. The setter placed before you can still be moved, and so can a partner. With no partners to place (you are off court, or the serving middle in Official R3/R6), your marker stays movable until Continue.
- **Alternatives:** keep every marker movable until Continue; lock every marker once placed.
- **Reversible by:** `rotLocked()` in `src/template.html`.

### 90. Family colours in the Name the set quiz and the set call check

- **Issue:** #100
- **Problem:** The Name the set quiz and the Match set call check drew the path in its family colour (back sets dashed) and coloured the answer buttons by family, which gave the answer away.
- **Decision:** Before the answer, the path and every button are drawn in `--ink`, solid, for every set. After the answer, the path and buttons show their family colours as feedback (in same-device and online Match, only on the solo feedback path; "Saved." stays neutral). The explore view is unchanged.
- **Alternatives:** keep everything neutral after the answer too; use `--muted` instead of `--ink`.
- **Reversible by:** `newSetQ()`, `answerSet()`, `setHtml()` and `setMark()` in `src/template.html` before #100.

### 91. Where the middle opens for the quick

- **Issue:** #104
- **Problem:** The front middle's `ar` spot sat on the 3 m line (y 0.44), so Learn's Reception play and the Drill and Match Attack route sent the middle back to the 3 m line before the quick. The owner: the middle's approach starts in the middle of the front zone; a back-row outside hitter told them that standing on the 3 m line blocks the back-row spike.
- **Decision:** The owner's call. The front middle's `ar` spot is `QUICK_START_Y` 0.26 in `src/data.py` (x unchanged), in front of the 3 m line and just behind the middle of the front zone, so the approach to take-off (`APPROACH_Y` 0.17) stays visible as a dashed line. In R2 and R3 the middle waits after the serve contact while the setter runs across its way (up to 1.3 s: 1.3 s in R2, 0.15 s in R3), and still takes off as the pass lands. In R2 that wait is longer than the serve stage (1.15 s), so the middle leaves as the pass starts, after the setter has crossed. The middle's `move.ar` captions, `ATTACK_NOTES.quick`, the Attack feedback and the "Three players receive" rule of thumb say it opens in the middle of the front zone, not on the 3 m line. Grading follows the Learn play as before.
- **Alternatives:** y 0.21 (the exact middle of the front zone, as `BASE_DEF`), which leaves almost no approach before take-off; a take-off closer to the net.
- **Reversible by:** `QUICK_START_Y` in `src/data.py`.

### 93. How Match names a Rotate moment

- **Issue:** #106
- **Problem:** Drill has a picker for H, R or Mixed names (#87). Match has no such setting, and on the same device and online every player of a moment must be asked the same name.
- **Decision:** Match names each Rotate moment H or R at random, as Drill's Mixed. The choice comes from a seed fixed at Start and the moment number, so all players of a moment get the same name; online the seed is the room's `meta.createdAt`, so no new room field is needed. The title shows the full name ("R4 (H4)") after the answer in solo; the pass screen shows only the asked name.
- **Alternatives:** follow the Drill picker (`ksv51:drillName`); add a Match option.
- **Reversible by:** `gRotHow()` in `src/template.html`.

### 94. Match Rotate scoring

- **Issue:** #106
- **Problem:** Match scores one spot per moment (exact 100, close 60, wrong 0), scaled by Show on court. Rotate now asks several markers with nobody on court.
- **Decision:** A Rotate moment is exact (100) only when every marker is in its right zone, else wrong (0), as in Drill (#85); there is no close grade. Show on court does not apply: the multiplier is ×1, the in-play peek is hidden and no peek is counted, as at Attack. The speed bonus allows 2 s more for each marker after the first. Help works as before: the hint text, and at level 2 the area around your own spot.
- **Alternatives:** points per right marker; grade only your own marker and show the others as help.
- **Reversible by:** `gRotCheck()`, `gAnswer()` and `gVisMult()` in `src/template.html`.

### 95. Match Rotate on the same device and online

- **Issue:** #106
- **Problem:** The reveal shows one tap per player. Rotate has several markers per player, and the online database rules accept no new answer fields.
- **Decision:** Same device: the reveal shows each player's own tap and verdict as before, plus a line of per-marker grades ("S: right · OH1: wrong"). Online (flag `match-online` is off): each player's own tap and verdict are written as before, with no per-marker grades on the reveal, so the database rules stay as they are.
- **Alternatives:** draw every player's markers on the reveal; add a grades field to the online answer and its rules.
- **Reversible by:** `swapOut()` and `mpReveal()` in `src/template.html`.

### 96. Side switch captions after the spike

- **Issue:** #73
- **Problem:** After the spike, R1 OP and OH1 switch sides behind the middle and the setter runs from its cover spot across to zone 1 or 2, but the captions said "back off to zone 2/4" or "Go to zone 1", which sounds like a step, not a run across the court. Coach question 11 (#16) may still decide the R1 switch should not happen.
- **Decision:** Build to the current play. A front-row player who passes behind the middle (`SWITCH_VIA`) reads "Cross behind the middle to zone 4: block or defend the next ball." (the zone 4 hitter: "Spike over the net, then cross behind the middle to zone 2."). Any other run to base that changes side of the centre line by more than `CROSS_DX` (0.3) reads "Cross to zone 2: block or defend the next ball." in the front row (the front-row setter in R4 to R6) and "Cross the court to zone 1 and defend while they play the ball." in the back row (the back-row setter in R1 to R3). No L or back-row OH run changes side today, so none of them says "cross".
- **Alternatives:** name the partner the player crosses with ("switch with OH1"); leave the setter's run uncaptioned as a cross because it starts near the centre.
- **Reversible by:** `ATTACK_NOTES.base`, `ATTACK_NOTES.hit[1]` and the `cross` map in `buildReception()` in `src/template.html`.

### 97. The Learn court at 390 × 664

- **Issue:** #113
- **Problem:** At 390 × 664 the court keeps its 381 px floor (#10 above), so back-row markers opened under the sticky Next row (up to 25 px under it in R4 to R6 Reception). The issue asks for the court and your marker in view at rest with Next still in view, without shrinking the markers below 36 px.
- **Decision:** On phone screens up to 700 px high the space above the court is tighter: page top padding 8 px (was 18), tabs 8 px (was 16), rotation and phase chips 6 px (was 10) and the title tag 4 px (was 8) below. The court moves up 30 px; the lowest marker ends about 5 px above the Next row in every rotation, step, role and rule set. Nothing scrolls on arrival, and taller screens are unchanged.
- **Alternatives:** lower the 381 px floor (markers under 36 px); scroll the court into place on arrival (moves the page under the user's finger); a shorter Next row (the primary action gets smaller).
- **Reversible by:** the `max-height: 700px` media query after `.learnmain` in `src/template.html`.

### 98. The gap between the Learn caption and the hint

- **Issue:** #113
- **Problem:** The audit saw about 50 px of empty space between the caption and the hint on Our serve and Base, read as space kept for Reception's "Then:" list. Nothing is kept for that list: the gap is the sticky Next row's own place in the page, which full-page screenshots leave empty because they draw the row at the bottom of the viewport. On a real scroll the row sits in that place. The caption's two-line minimum and the invisible animation bar on static screens (#38 above) are real space, kept so the caption and Next do not jump between screens.
- **Decision:** No layout change. `check_learn_fit()` in `src/tests/qa.py` checks the court against the Next row instead.
- **Alternatives:** drop the bar or the caption minimum on static screens (Next and the hint jump 22 to 52 px between Reception and the other steps).
- **Reversible by:** nothing to reverse.

### 99. Learn flags switched on in PostHog

- **Issue:** none (end of milestone v2: Learn, by the owner's instruction for this run)
- **Problem:** Agents never switch a PostHog flag on; the owner asked for the Learn flags to go on once the milestone was done, without waiting for a phone check.
- **Decision:** On 2026-10-01 `learn-tab`, `learn-animation`, `learn-guides`, `rotations-table` and `rules-official` were switched on in project 635296, at their existing 100% rollout. Every other flag stays off, so the live page shows Learn only. `drill-steps`, `drill-rotate-name` and `match-rotate-name` have no PostHog flag and read as off on the live page.
- **Alternatives:** leave all flags off until the owner checks on a phone; switch on Learn without `rules-official`.
- **Reversible by:** switching the flags off in PostHog; phones pick up the change on their next fresh load.

### 100. A flag of its own for the answer glide

- **Issue:** #25
- **Problem:** The issue lists `drill-tab` as the flag, but the glide and `Watch the move` change Drill and Match, and the owner switches each new feature on after a phone check.
- **Decision:** A new flag `answer-glide`, built-in default on, needing `learn-animation` (it plays Learn's Reception play). It has no PostHog flag yet, so on the live site it reads as off until the owner creates it.
- **Alternatives:** ship it under `drill-tab` (on at once, live for everyone); under `learn-animation`.
- **Reversible by:** the `answer-glide` keys in `FEATURES`, `FEATURE_NEEDS` and `FEATURE_ELEMENTS` in `src/template.html`.

### 101. What Watch the move plays

- **Issue:** #25
- **Problem:** The plan says it "plays this phase". Only Reception has a play (#69); Attack is a moment inside it, and Rotate and Our serve are static.
- **Decision:** Receive and Attack both play Learn's whole Reception play for your role, with the Learn controls, then fade back to the answer picture. Rotate and Our serve offer no button.
- **Alternatives:** play Attack from the pass only; stop the play at the moment the step grades.
- **Reversible by:** `watchOn()` and `watchBuild()` in `src/template.html`.

### 102. One Watch the move at a time

- **Issue:** #25
- **Problem:** Drill, solo Match and the reveal each have an answer court; a play could be left running on a tab you left.
- **Decision:** Only one `Watch the move` exists at a time. Next, a new question, leaving the view and a hidden page stop it; switching tabs returns its court to the answer picture.
- **Alternatives:** one per court, each with its own clock.
- **Reversible by:** the `watch` state and `watchClose()` / `watchRest()` in `src/template.html`.

### 103. Motion on the same-device reveal

- **Issue:** #25 (the reveal motion left from #32, `docs/v2.md` §4.7)
- **Problem:** The reveal shows one marker per role, but several players may share a role, each with their own tap.
- **Decision:** Each role's marker glides from the first tap for that role. `Watch the move` plays for your role online and for the one role on the same device; with several roles it plays with no ring and the lead mover's captions.
- **Alternatives:** one marker per player; no glide on the reveal.
- **Reversible by:** the `glideChip()` and `watchMount()` calls in `mpReveal()` in `src/template.html`.

### 104. Rotate markers glide too

- **Issue:** #25
- **Problem:** The issue speaks of "your marker"; Rotate from the name places several markers (setter, you, your partners).
- **Decision:** Every placed Rotate marker glides 400 ms from its tap to its right spot, in Drill and Match.
- **Alternatives:** only your own marker glides.
- **Reversible by:** the `glideChip()` call in `drawRotate()` in `src/template.html`.

### 105. Where the Zones toggle sits and where the numbers stand

- **Issue:** #41
- **Problem:** `docs/v2.md` §2.3 puts the Zones toggle in an "options fold" that Learn does not have; the issue asks for it near the court. At 390 × 664 the court already ends about 5 px above the sticky Next row (#97), so a new row above or below the court would push markers under Next, and the animation bar has no room left for another 44 px button.
- **Decision:** A "Zones" toggle button (`aria-pressed`, 48 px high like Next) sits left of Next in the sticky row; Next keeps the rest of the width. The numbers are drawn under the markers in `--court-line` at 40%, centred in each zone's column, the front row just in front of the 3 m line (y 0.36) and the back row by the end line (y 0.94), where fewer reception and attack spots stand than at the zone centres. Toggling never restarts a Reception play.
- **Alternatives:** a Learn options fold under the hint (the toggle out of sight below the fold); a chip beside the title tag (adds height above the court); the numbers at the zone centres (hidden under markers in most screens).
- **Reversible by:** `#lZones` and `.lctl .zones` in `src/template.html` for the place, `ZONE_SPOTS` for the numbers.

### 106. Zone numbers only on the Learn court

- **Issue:** #41
- **Problem:** The issue says "on the court" without naming the tab. In Drill and Match the zone numbers would help answer the question the court asks.
- **Decision:** Only the Learn court has the toggle and the numbers. Drill and Match courts are unchanged.
- **Alternatives:** one toggle for every court; a Drill option that also lowers the score in Match like Show on court.
- **Reversible by:** adding `zonesSvg()` after `courtBase()` in the Drill and Match court renders in `src/template.html`.

### 110. Drill names rotations by the setter only

- **Issue:** #116
- **Problem:** The owner asked for Drill to show `H5`, not `R3 (H5)`. Drill also has the Rotate names option (H / R / Mixed), which asks the Rotate question by R on purpose, and its default was Mixed.
- **Decision:** Every Drill screen says `H<n>`: the question title, the feedback, the weak spots and Review weak spots. The Rotate names option stays for the Rotate question only, now with H as its default; a stored R or Mixed is kept. After the answer the feedback says `H<n>` even when the question said `R<n>`. Learn and Match keep `R3 (H5)`.
- **Alternatives:** remove the Rotate names option; keep Mixed as the default.
- **Reversible by:** the `hName()` and `hOnly()` calls in the Drill code of `src/template.html`, and the `drillName` default.

### 111. The back-row opposite waits for the pass, then runs straight to cover

- **Issue:** #119
- **Problem:** In R4 to R6 the back-row opposite does not attack (the set goes to zone 4), but it left at the serve contact for its `ar` spot and only then turned to its deep cover, a run with a corner in it (#68 says it runs straight on).
- **Decision:** A back-row attacker who covers is not released at the serve contact. It waits out of the passing lanes until the pass, then runs in one line to the side deep cover (`DEEP_COVER.side`, 0.62, 0.44), placed just after L so the two runs stay `GAP` apart.
- **Alternatives:** leave at the contact straight for the cover (in R6 it then waits up to 0.8 s for the passer's lane to clear); keep the corner via the `ar` spot.
- **Reversible by:** `released` and the pass stage's `first` in `buildReception()` in `src/template.html`.

### 112. The covers are graded on their cover spot

- **Issue:** #119
- **Problem:** Drill and Match graded L, the deep outside hitter and the back-row opposite where the Learn play had them as the pass lands (#69), a point mid-run, while their hint and feedback (#79) name the cover spot. A tap on the spot the text names read "Not there".
- **Decision:** These three are graded on the cover spot they stand on at the spike (the start of Reception's base stage, `tr.spike`). Everyone else is still graded as the pass lands (#69). This amends #69 for the covers. A cover's question asks for its cover spot as the zone 4 hitter spikes, and its feedback and hint say "cover spot as … spikes". The picture after its answer shows one moment, the spike: everyone where they are then and the ball at the hitter. On a same-device reveal where every player covers, the reveal shows the spike too; with mixed roles it shows the pass landing, with each player's own role ringed on the spot it is graded on.
- **Alternatives:** keep grading mid-run and change the texts to "on the way to …"; ask about the moment of the spike for everyone.
- **Reversible by:** `tr.spike` in `buildReception()`, `coversAttack()`, `answerSpots()`, `momentBall()`, `arQuestion()` and `mpReveal()` in `src/template.html`.

### 113. Detours stay inside the court

- **Issue:** #119
- **Problem:** A detour round a player went through one waypoint a fixed distance to the side, which could lie past a sideline (the R1 setter's run went through x 1.03) or behind the end line.
- **Decision:** A detour waypoint stays between the sidelines and no deeper than the end line or the run's own start or end. A waypoint that would pass a sideline goes level with the player met, on the sideline.
- **Alternatives:** wider detours on the inside only (the R1 setter then waits 0.8 s and the pass flies 1.8 s); let the run wait instead of detouring.
- **Reversible by:** `detours()` in `src/template.html`.

### 114. The zone 4 hitter approaches outside-in

- **Issue:** #119
- **Problem:** The zone 4 hitter started at its `ar` spot by the left sideline (x 0.07) and ran straight along the sideline to the net, which is not the outside-in angle hitters are taught.
- **Decision:** The hit point is 0.08 (about 0.7 m) inside the start (`HIT_IN`), so the approach angles in from the sideline. The 3-2 close cover (#68) is placed round the hit point, so it moves in by the same amount. Every Learn animation check still holds. The `ar` spots are unchanged. Coach question #16 may give a better angle.
- **Alternatives:** start the hitter outside the sideline (off the guide's spot); a curved approach.
- **Reversible by:** `HIT_IN` in `src/template.html`.

### 115. The set call question for a covering back-row opposite

- **Issue:** #119
- **Problem:** In R4 to R6 the back-row opposite is graded as a deep cover (#112), but the set call check asked it the back-row set of its third "for you", as if it attacked from zone 1.
- **Decision:** A player who covers at the Attack step is asked the set call as a watcher: "The setter sets this ball. What is the call?", from every match set, like the libero and the other back row. A back-row opposite who attacks is still asked its own back set.
- **Alternatives:** keep asking the zone 1 set (A) for a later back-row attack; skip the set call check for covers.
- **Reversible by:** `setQ()` in `src/template.html`.

### 116. Drill, Match and Sets switched on in PostHog

- **Issue:** none (owner instruction 2026-10-01: "never wait for me to enable feature flag")
- **Problem:** The Drill, Match and Sets flags were built and deployed but off in PostHog, waiting for the owner's phone check.
- **Decision:** On 2026-10-01, after `392a3cc` deployed, these PostHog flags are on at 100%: `drill-tab`, `drill-review`, `neighbour-check`, `match-solo`, `set-call-check`, `match-same-device`, `sets-tab`, `sets-quiz`, and the new flags `drill-steps`, `drill-rotate-name`, `match-rotate-name`, `answer-glide`. Left off: `match-online` (#33, live database rules), `after-dig` (#35), `downloads` (removed).
- **Alternatives:** wait for the owner's phone check.
- **Reversible by:** switching the flag off in PostHog project 635296.

### 117. Report a problem is in the role list on phones, an icon from 480 px

- **Issue:** #52
- **Problem:** The plan opens the report sheet from the header menu (#76), but #76 shipped a role list, not a general menu, and the issue asks for a 44 px icon next to the theme button. At 390 px the header row (title, "Outside 1 · Simplified ▾", theme button) has no 52 px to spare: an inline icon pushes the title's volleyball onto a second line, and stacking it under the theme button makes the header 48 px taller, which pushes the Learn court under the sticky Next row and the role list off its button.
- **Decision:** From 480 px the sheet opens from its own icon (`#reportBtn`, a speech bubble with "!") after the theme button. Below 480 px the icon is hidden and the role list ends with a 44 px "Report a problem" row (`#reportItem`, not on the first-visit "Pick your role" list), which closes the list and opens the sheet. The header is unchanged on phones.
- **Alternatives:** a shorter role button text on phones ("OH1 · Simplified"); a smaller icon (under 44 px); the icon in the tab bar; the icon stacked under the theme button.
- **Reversible by:** `#reportBtn`, `#reportItem` and the `max-width: 479px` block for them in `src/template.html`.
- **Owner, 2026-10-01 (#127):** the owner chose the icon in the phone header. `#reportBtn` shows at every width and `#reportItem` is gone. Below 480 px the role button reads the role code and the rules initial ("OP · S ▾", "MB1 · O ▾"; its aria-label keeps the full names), which makes room at 360 and 390 px with the title unchanged.

### 118. The report sheet is a native modal dialog

- **Issue:** #52
- **Problem:** The plan says "a panel"; the role list (#76) is a dropdown with no backdrop, which suits a quick pick, not a form with a text box.
- **Decision:** `#reportSheet` is a `<dialog>` opened with `showModal()`: a backdrop, the page inert behind it, Escape and Cancel close it and focus returns to the icon. The Learn arrow keys do nothing while it is open. The sheet opens at once and says "Taking a screenshot…" until the capture is done; the capture leaves the sheet out.
- **Alternatives:** a dropdown like the role list; a full-screen page.
- **Reversible by:** `#reportSheet` and `reportOpen()` in `src/template.html`.

### 119. What the screenshot holds and how small it gets

- **Issue:** #52
- **Problem:** The plan asks for the visible app as a JPEG of at most 1080 px and 250 kB, but not what to do with a busy screen, or with the court, whose SVG colours come from CSS variables that html2canvas does not apply inside an SVG.
- **Decision:** html2canvas 1.4.1 (the latest release) captures the viewport at the current scroll, scaled so the long side is at most 1080 px. Before drawing, the computed fill, stroke, opacity and font of every SVG element are copied inline into the clone, so the court looks as on screen. The JPEG is tried at quality 0.8, 0.6, 0.45 and 0.3 and the first under 333 000 base64 characters (about 250 kB) is kept; if none fits, or the capture fails, the report goes without a screenshot and the sheet says so. The rules allow 350 000 characters.
- **Alternatives:** capture the whole page; send a PNG; shrink the size instead of the quality.
- **Reversible by:** `SHOT_SIDE`, `SHOT_CHARS`, `inlineSvgStyles()` and `reportCapture()` in `src/template.html`.

### 120. The context a report carries

- **Issue:** #52
- **Problem:** The plan lists the context (tab, role, rules, Learn rotation and phase or the Drill and Match state, theme, viewport, user agent, app version, flags) but not its shape.
- **Decision:** Flat fields: `tab` (`learn`, `drill`, `game`, `sets`), `role`, `rules`, `view` (one short string: Learn "R3 rec" plus "playing" while a play runs; Drill the question's rotation and step; Match the mode, the moment number and its rotation and step), `theme`, `viewport` ("390x664@3"), `ua` (first 300 characters), `version` ("2") and `flags` (every key and its value). Never a player name, room code or uid: the report node holds no uid, and the online mode is only the word "online".
- **Alternatives:** nested objects per tab; the full Match queue.
- **Reversible by:** `reportContext()` and `viewText()` in `src/template.html` and `reports` in `infra/database.rules.json`.

### 121. An empty comment is asked for, Send stays on

- **Issue:** #52
- **Problem:** The comment is required, but a disabled primary button looked frozen once before (the neighbour check, see CLAUDE.md "History").
- **Decision:** Send is always enabled. With an empty comment it writes nothing and says "Write a few words about the problem." and puts the cursor in the comment box. After a send the comment is cleared, the sheet says "Thanks, sent." and Cancel reads Close; a failure says "Could not send. Try again." and keeps the comment.
- **Alternatives:** disable Send until there is text.
- **Reversible by:** `reportSend()` in `src/template.html`.

### 122. Reports have no rate limit

- **Issue:** #52
- **Problem:** Anyone who signs in anonymously can create reports. A per-user limit needs the uid in the report or a second node keyed by uid, and the plan says never a uid.
- **Decision:** No rate limit. The rules allow a create only (no read, update or delete), with every field validated and the image at most 350 000 characters, so one report is at most about 360 kB. The Spark plan's quota is the cap, and the owner can delete reports in the Firebase console. A retry of the same comment reuses its push key, so a send that timed out but landed is not written twice: the retry is denied as an overwrite and counts as sent.
- **Alternatives:** a `reportsBy/{uid}` timestamp node checked by the rules; App Check.
- **Reversible by:** `reports` in `infra/database.rules.json`.

### 123. Report a problem needs no other flag

- **Issue:** #52
- **Problem:** Reports go through the same Firebase SDK and anonymous sign-in as Online room, whose flag `match-online` is off (#33).
- **Decision:** `bug-report` has no needs. The Firebase SDK is loaded on the first Send only, as Online room loads it on Create or Join; until the owner's `terraform apply` uploads the new rules every send is denied and says "Could not send. Try again.", so the flag stays off until then (see 124).
- **Alternatives:** make `bug-report` need `match-online`.
- **Reversible by:** `FEATURE_NEEDS` in `src/template.html`.

### 124. Report a problem is off by default

- **Issue:** #52
- **Problem:** The live database rules accept no reports until the owner's `terraform apply`. A first visit has no stored PostHog values and uses the built-in defaults, so a PostHog flag that is off does not hide the icon on that visit.
- **Decision:** `bug-report` is off in `FEATURES`. After the apply, the PostHog flag switches it on.
- **Alternatives:** on by default, with every send denied until the apply.
- **Reversible by:** `FEATURES` in `src/template.html`.

### 125. Drill Reset takes two taps and has no flag

- **Issue:** #124
- **Problem:** The owner asked for a way to reset Drill progress at any time; Reset my progress sat in the closed Drill options fold.
- **Decision:** Reset sits left of the Drill score, always shown and always enabled (with nothing to reset it only draws a new question). The first tap shows "Sure?" for 3 s (one line at a fixed width, so the header and the court do not move; screen readers hear "Tap again to reset"); a second tap clears stats for every role, score, streak and any review. `lastPractice` stays, because Match sets it too. The button moved, so it has no feature flag; it goes with `drill-tab`.
- **Alternatives:** a `confirm()` dialog; hide or disable it when there is nothing to reset; a `drill-reset` flag that keeps the old button while off.
- **Reversible by:** `#dReset` in `src/template.html`.

### 126. Report a problem closes in the sheet after a good send

- **Issue:** #126
- **Problem:** The owner wants the sheet closed after a send, but the user still needs to see that it was sent.
- **Decision:** "Thanks, sent." stays in the sheet for 1.2 s (`REPORT_DONE_MS`), with Send disabled, then the sheet closes by itself and focus returns to the opener. It reuses the sheet's own message line, so nothing new is drawn on the page.
- **Alternatives:** close at once and show a 2.5 s status toast on the page.
- **Reversible by:** `REPORT_DONE_MS` and `reportSend()` in `src/template.html`.

### 127. Online rooms carry an integer version, checked on join

- **Issue:** #33
- **Problem:** A cached v1 app reads a v2 room differently (`rulesMode` `simple`, role `MB`) and plays a different match without a warning. The issue asks for a version guard but leaves its form open.
- **Decision:** `ROOM_V` in `src/template.html` is the integer 2 (v1 rooms had none). Create and Start write `meta.v`. A higher `meta.v` gets "Reload the app to join this room."; a missing or lower one gets "This room is from an older version. Ask the host to make a new room." and clears `ksv51:room`, so the Rejoin row goes; a stale room is still deleted first. The rules require `v` in every `meta` write (not only the create) and accept a number from 1 to 1000; the host's later writes keep it, because `onMeta()` spreads the stored meta and the reset and takeover write single children. A new player node must carry `v` equal to `meta/v`, so an old client that skips the check cannot join either; writes to an existing node (role, presence, colour, score, the host's clears) need no `v`.
- **Alternatives:** the app version string; a range of compatible versions; hide Rejoin for a room of another version.
- **Reversible by:** `ROOM_V` and `onJoin()` in `src/template.html`, `meta/v` in `infra/database.rules.json`.

### 128. Online room stays off by default until the rules apply

- **Issue:** #33
- **Problem:** #15 kept `match-online` off until the live rules accept Simplified; the owner applied those on 2026-09-30. The new rules for `meta.v` and the player `v` are live only after the next `terraform apply`, and the live rules deny `v` (`$other: false`) until then, so Create a room would fail.
- **Decision:** `match-online` stays off in `FEATURES` in this PR. The owner applies the rules and wipes `rooms`, then the PostHog flag goes on, and a follow-up PR flips the built-in default.
- **Alternatives:** flip the default in this PR and accept failing creates between the merge and the apply.
- **Reversible by:** `FEATURES["match-online"]` in `src/template.html` and `DEFAULT_OFF` in `src/tests/flags_test.py`.

### 129. Zone numbers on every court, on by default

- **Issue:** #130
- **Problem:** #105 and #106 put the zone numbers only on the Learn court, off until the Zones toggle is pressed. The owner decided on 2026-10-01 that they belong "everywhere".
- **Decision:** This amends the off-by-default choice of #105 and replaces #106. Every court draws the numbers (Learn, every Drill and Match court, Rotate, the Attack picture, the glide, Watch the move, the same-device and online reveal). An unset `ksv51:zones` reads as on; a stored value is kept, so a player who switched them off keeps them off. One setting for every view: the Learn Zones toggle, and a "Zone numbers on the court" row in Drill options and in Match options. Zones never changes Match scoring. `court-zones` no longer needs `learn-tab`.
- **Alternatives:** a separate key per tab; zones lowering the Match score like Show on court; resetting stored values to on.
- **Reversible by:** the `zonesSvg()` call in `courtBase()` and the `zones` default in `src/template.html`.

### 130. The code sets every feature switch; PostHog flags are not read

- **Issue:** #132
- **Problem:** On the Pages host the PostHog flag values replaced the built-in defaults, but a phone that blocks PostHog kept the defaults, so two players could see different apps. The owner decided on 2026-10-01 that PostHog feature flags are no longer needed.
- **Decision:** `feature()` reads only `FEATURES` and `FEATURE_NEEDS` and the `?ff=` override (`ksv51:ffOverride`). The PostHog flag reading (`flagsFromPosthog()`, `bootstrap.featureFlags`, the first-input gate) is gone, and a stored `ksv51:flags` is removed at start-up. PostHog analytics events are unchanged. `match-online` and `bug-report` go on in `FEATURES`; only `after-dig` stays off (#35). This replaces the "PostHog flag on" step of #128.
- **Alternatives:** keep PostHog flags and accept the split; bootstrap the flags from the built-in defaults so blocked phones match only until the first change.
- **Reversible by:** `featureValues(FEATURES, …)` and `analyticsLoad()` in `src/template.html`.

### 131. A report signs in as a new anonymous user on its own Firebase app

- **Issue:** #136
- **Problem:** On iOS, Firebase Auth's popup/redirect resolver loads apis.google.com and the auth iframe before any sign-in. If either is slow or never answers, the report's 10 s sign-in timeout fires. The compat SDK has no option to leave the resolver out of the default app.
- **Decision:** Report a problem uses a second app named `report`, whose auth is set up with no resolver and in-memory persistence. Every page load that sends a report signs in as a new anonymous user; reports carry no uid, and anonymous auth clean-up removes the old users. Online room keeps the default app and its stored uid. A failed send now names its cause: sign-in, the server, or a refusal.
- **Alternatives:** longer timeouts on the default app; the modular SDK for auth.
- **Reversible by:** `reportReady()` and `REPORT_FAILURE` in `src/template.html`.

### 132. Show on court is fixed at the start of a solo match

- **Issue:** #134
- **Problem:** Solo Match offered the Show on court picker during play as a peek, scored with the most revealing setting shown before the answer, with "Peeked: n moments" on the end screen. The owner decided on 2026-10-01 that the setting is chosen at the start and cannot change during the match, as in same-device and online play.
- **Decision:** This replaces the solo peek. The in-play picker, the peek scoring and "Peeked: n moments" are gone, and `match_finished` drops `peeked`. Every moment scores with the setting chosen at Start. The best-score key stays `v8|`: a match without a peek scores as before, and a best from a match with a peek is lower than the same play scores now, so old bests stay fair to beat.
- **Alternatives:** keep the peek but count it as a separate best; bump the key to `v9|` and drop every old best.
- **Reversible by:** `gVis()`, `gVisMult()` and `gShownHtml()` in `src/template.html`.

### 133. Online room keeps its stored uid with no Google auth iframe

- **Issue:** #140
- **Problem:** Online room signs in on the default Firebase app, whose compat auth starts the popup/redirect resolver on iOS and waits for apis.google.com and the auth iframe, as reports did before #136. The fix of #131 also drops persistence, but Rejoin needs the same anonymous uid after a reload to find the player's node and score.
- **Decision:** `fbSetup()` sets up the default app's auth, and the `report` app's, with no resolver. The default app keeps local persistence (IndexedDB, else localStorage), the same store as before, so a uid signed in before this change is kept. The compat SDK does not export that persistence class, so `fbLocal()` takes it from a short-lived app named `persistence` after `setPersistence(LOCAL)`. If that fails or takes more than 3 s (the IndexedDB check can hang on some iOS versions), sign-in goes on in memory and only Rejoin after a reload joins as a new player. Reports only wait for the scripts, never for that check. Every auth request also waits for Firebase's usage heartbeat, which reads IndexedDB; `fbSetup()` sends it empty after 1 s (`BEAT_MS`), so a hung IndexedDB cannot hold up sign-in, Create or a report.
- **Alternatives:** in-memory persistence, losing Rejoin after a reload; an own localStorage persistence class; the modular SDK for auth.
- **Reversible by:** `fbSetup()` and `fbLocal()` in `src/template.html`.

### 134. Match names rotations by the setter only, and Rotate asks by H

- **Issue:** #135
- **Problem:** Match named rotations `R1 (H1)`, and Match Rotate from the name asked by H or R at random per moment (#93-#95). The owner asked on 2026-10-01 for Match to show only the setter's zone, as Drill does (#110).
- **Decision:** This amends #93-#95. Every Match text names the rotation `H<n>` only: the setup options, the story, the title (before and after the answer), hints, feedback, the pass screen, the reveal and the mistakes lists, in solo, same-device and online play. Match Rotate always asks by H; the H/R pick (`gRotHow()`) and the match seed it read are gone, so every player of a moment gets the same name and online play needs no seed; a phone on a cached older build may still ask by R until it reloads (`ROOM_V` unchanged, as the room data did not change). The best-score key stays `v8|`: Rotate scores the same whichever name it asks by. Learn keeps `R1 (H1)`.
- **Alternatives:** keep the H/R pick for Rotate only; an "R names" option in Match options.
- **Reversible by:** `hName()` and `hOnly()` in the Match code of `src/template.html`.

### 135. Rotation plays a build from the setter

- **Issue:** #146
- **Problem:** A player report asked for Rotation to show how the lineup follows from the setter, not only the finished lineup. Rotation was static: only Reception animated (#78, owner, #69, #94).
- **Decision:** This amends #78 for Rotation only; Our serve and Base stay static. Rotation still opens on the full lineup with the overlap lines, and nothing plays on its own. Play, Step, Step back, the stage dots, the speed and the Play nudge work as on Reception. The play starts on an empty court and adds one marker per stage on its Rotation spot with a 300 ms fade and pop; nobody runs and there is no ball. The order is the setter, the opposite on the setter's diagonal, OH1, OH2 on OH1's diagonal, the front middle in the empty front spot, then L in the empty back spot. It ends on the still, so there is no fade-back; the overlap lines fade in at the end.
- **Alternatives:** replace the still with the build; build from the setter with players walking in from the sideline.
- **Reversible by:** `animPhase()`, `phaseStages()` and `buildRotation()` in `src/template.html`.

### 136. The Rotation build captions every stage

- **Issue:** #146
- **Problem:** While a play runs, the caption shows only your own lines (`captionPlan()`). In the build each player has one line, so you would see the setter's line and then your own, and miss the rules that place everyone in between.
- **Decision:** The build shows every stage's line for its whole stage, changing with each marker. A stage lasts `BUILD_MS`, 1.2 s, with no `CAPTION_MS` hold (owner, #149; first 2.5 s, which made the play last 15 s), so the play lasts 8.4 s for its seven stages plus the end hold. Owner decision 2026-10-03 (#149): the lines teach a zone walk from the setter instead of six separate rules: "Rule 1: setter in zone N (HN). Count up: …; after 6 comes 1.", then each zone up from the setter's (6 wraps to 1) with its step ("Zone 2: next in the walk after the setter, outside hitter 1.", "Zone 6: next is a middle; in the back row the libero plays it."), always S, OH1, a middle, OP, OH2, a middle, and a last stage that adds nobody: "Same job, opposite corners: S–OP, OH–OH, MB–L." (as "Rule 2: …"). In Official R3/R6 the walk meets the serving middle in zone 1 ("it serves, so no libero swap") and the check ends MB–MB. The rotation arrows run clockwise on screen, against the walk (the owner misread R4 (H4) along them), so the build hides them, draws a neutral arrow from zone to zone in the walk direction each stage, and rule 1 says "against the rotation arrows". The walk and the corners are the first two Rules of thumb (`walk`, `corners`), which the first and last stages cite as "Rule 1" and "Rule 2"; the owner shortened every Rules of thumb entry at the same time. Your own stage reads "You (OH1): …". After the play, the rest caption lists the seven steps under "Then:", and reduced motion lists them on the still. Reception keeps the own-line rule.
- **Alternatives:** your own line only, as on Reception; shorter stages with the lines shown after the play.
- **Reversible by:** `captionPlan()` (`tr.build`) and `BUILD_MS` in `src/template.html`.

### 137. Official R3 and R6 build the serving middle in zone 1

- **Issue:** #146
- **Problem:** In Official R3 and R6 the Rotation step is the real lineup (`middleServes()`): the zone 1 middle serves and L is off. The build's last stage would place L.
- **Decision:** The build uses the same lineup as the still. Its last stage places the serving middle in zone 1: "MB1 fills zone 1 and serves: the libero may not serve, so L is off." Simplified always builds MB and L, and Official names the front middle (MB1 or MB2).
- **Alternatives:** build L and then swap it for the serving middle in a seventh stage.
- **Reversible by:** `buildRotation()` in `src/template.html`.

### 138. "Serves next after the setter" names OH1's zone

- **Issue:** #146
- **Superseded:** owner decision 2026-10-03 (#149): the zone walk (#136) names OH1 as "Zone <n+1>: next in the walk after the setter, outside hitter 1."
- **Problem:** Which outside hitter comes "next to the setter" had to match how the app explains the serving order (`S, OH1, MB1, OP, OH2, MB2`; `relation()`: "In the serving order you come 1 after the setter").
- **Decision:** OH1 is always one zone on from the setter (6 wraps to 1), so the caption says "Outside hitter 1 serves next after the setter, one zone on: zone <n+1>." It names the serving order, as `relation()` does, rather than "next to", which on court can mean either side.
- **Alternatives:** "OH1 is next to the setter"; count the zones as in `relation()` ("count 1 zone on").
- **Reversible by:** `buildRotation()` in `src/template.html`.

### 139. Official is the default rule set

- **Issue:** none (owner request, 2026-10-03)
- **Problem:** The app opened in Simplified KSV, but the club plays Official rules and the owner wants new users to learn those first.
- **Decision:** The owner asked on 2026-10-03 for Official as the default. With no stored `ksv51:rulesMode` the app runs Official, so a new user's role list shows MB1 and MB2 and a stored `MB` reads as MB1 (`roleIn()`). A stored choice is kept: `simple` stays Simplified, `official` stays Official, and a stored `drill` from v1 still reads as Simplified. With `rules-official` off the app still runs Simplified.
- **Alternatives:** switch everyone to Official, including users who picked Simplified.
- **Reversible by:** `storedRules()` in `src/template.html`.

### 140. A one-time reset of rules and role to Official

- **Issue:** none (owner decision, 2026-10-03)
- **Problem:** With Official as the default (#139), everyone who had already opened the app kept Simplified, because v1 stored `ksv51:rulesMode` for every user, not only for those who picked it.
- **Decision:** The owner decided on 2026-10-03 that everyone restarts in Official once. On start-up, while `rules-official` is on and `ksv51:officialReset` is not stored, the app removes `ksv51:rulesMode` and `ksv51:role` and stores the mark, so the next screen is a first visit for rules and role: Official, and the role list opens with "Pick your role". Progress, bests, theme, room, zones and every other key are kept. A user who then picks Simplified keeps it. A phone with `rules-official` off is not reset until the flag is on for it. Drill stats of the Simplified `MB` do not carry over to MB1 or MB2.
- **Alternatives:** keep stored choices (#139 alone); map a stored `simple` to Official without clearing the role.
- **Reversible by:** the `officialReset` block after `feature` in `src/template.html`.
