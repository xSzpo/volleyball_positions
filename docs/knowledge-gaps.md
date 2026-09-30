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
