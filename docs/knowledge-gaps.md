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

### 45. L covers from the guide's zone 5 spot

- **Issue:** #53
- **Problem:** The cup ran L across the court in front of the deep outside hitter. The guide's after-reception picture already has L in zone 5 at about y 0.72, behind the zone 4 attack.
- **Decision:** L does not move in stage 3: it covers from its `ar` spot, reached in stage 2. In R3, R4 and R6 L curves behind the deep outside hitter where the two cross; in R1 OH2 curves behind L, which runs straight; in R2 and R5 nobody crosses. The caption: "Cover X from zone 5: play a ball the block sends back."
- **Alternatives:** L in the close cup (#37).
- **Reversible by:** the L branch of stage 3 in `buildStages()` in `src/template.html`.

### 46. The deep outside hitter stays deep

- **Issue:** #53
- **Problem:** The back-row outside hitter came forward into the cup and back again, which the guide does not draw.
- **Decision:** The back-row outside hitter goes to y 0.86 or deeper at the set (`DEEP_Y`, the zone 6 base depth) and never comes forward of its reception or after-reception spot before the spike; it covers wipes deep.
- **Alternatives:** the deep cup spot (#37).
- **Reversible by:** `DEEP_Y` in `src/template.html`.

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
