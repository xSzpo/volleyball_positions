# Our serve and After dig

## Stage 1 (done): Our serve

The `serve` phase (shown as "Our serve") is where everyone stands when we
serve. Since the FIVB 2025-2028 rules (7.4, adopted by Volleyball Danmark in
September 2025) the serving team has no overlap rule, so there is no switch
after the serve: everyone except the server stands in their base spot before
the serve. The server serves from behind the end line in zone 1, then runs to
their base spot; the app and the schema draw only that arrow. Rows still count
for play: back-row players may not block. Spots come from `BASE_DEF` in
`src/data.py`, one per zone: the front row stands in the middle of its zone
(4, 3, 2 at y 0.21), not at the net, because the coach has not confirmed these
spots; the back row defends deep (5, 6, 1). A back-row setter defends zone 1, a
front-row setter takes zone 2, the libero always takes zone 5. In R3 and R6 under official rules the middle
serves, stays on and runs to zone 6. The phase key, `meta` fields and step
indices are unchanged, so the live database rules still accept it.

In a match, one rotation R runs: Rotation (we won the rally and rotate into
R), Our serve (we serve in R), Reception (we lost the rally, the opponent
serves) and After reception (good pass), then we win and rotate into R+1.

## Stage 2 (planned): After dig

A new phase `tr` (transition) follows Our serve: we dig the opponent's
attack and go to attack.

- Positions per rotation in `data.py`, shaped like `ar`: `(player, x, y, kind)`
  with kind `front`, `back`, `set` or `None`. The app draws attack and setter
  lines as `arLayer()` does, with arrows from the `BASE_DEF` spot.
- Back-row setter (R1-R3): releases from zone 1 to the setting spot, about
  (0.69, 0.10), after the dig.
- Front-row setter (R4-R6): leaves the right block for the setting spot. The
  OP is then a back-row attacker from zone 1, behind the 3 m line.
- Front-row hitters come off the net to the 3 m line to approach; the libero
  and back-row outside stay in defence or cover.
- `describe()`, `gStory()`, `gHint()`, Learn, Drill, Match and the audit get a
  `tr` branch. The best key prefix goes up again.

### Database rules change first

The online room stores steps and phases, and the live rules reject unknown
values. Before the app with `tr` merges, change `infra/database.rules.json` and
apply it:

- `meta/steps/$k`: `^[0-3]$` → `^[0-4]$`
- add `|tr` to the phase regexes for `meta/steps`, `meta/queue/{i}/phase` and
  `players/{uid}/misses/{k}/phase`

Apply the rules (`terraform apply`, by the owner) **before** merging the app.

Old clients break in rooms that use `tr` until they reload. A cached client's
`onClean()`/`cleanSteps` drops the unknown `tr` entries from the queue, so its
`i` no longer lines up with the host's and it shows the wrong moment. Phones
cache aggressively, so this will happen.

Mitigation, to ship with stage 2 (or earlier, as its own change):

- a guard in `onClean()`: if the room's queue or steps hold a phase the client
  does not know, stop and show "This room needs a newer version. Reload the
  page." instead of dropping the entry;
- or a client version field (`meta/v`, needs its own rules entry) written by
  the host at Start, with the same reload message when it is newer than the
  client's.

The guard needs no rules change, so it can ship in a stage 1 follow-up and be
live on phones before any room uses `tr`.

## Open questions for the coach

- Base defence spots: the front row (now mid-zone, y 0.21), perimeter depth for 5 and 1 (y 0.66) and 6 (y 0.86), and
  whether zone 6 should play up instead.
- When exactly the back-row setter releases: on the dig, or already when the
  opponent's attack is clearly not coming to zone 1.
- Who takes the second ball when the setter digs.
- Whether the front-row setter blocks right or releases early in R4-R6.
- In R3 and R6, whether the serving middle defends 6 or 1 (with the OH at 6).
- Set calls in transition: the same calls as after reception, or a shorter
  list.
- Still open from before: "Po" and "4", and the serve column in general.
