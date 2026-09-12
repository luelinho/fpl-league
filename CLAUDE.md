# Operating rules for this repository

This is a data-integrity project first and an analytics project second. The value
of the database is that it can be trusted. These rules protect that.

Read `SPEC.md` for the full design. Read this file before answering any question
about the league.

---

## 1. The three layers

| Layer | Meaning | Where it lives |
|---|---|---|
| **Raw** | What FPL actually reported | `raw_*` tables |
| **Derived** | What our code computed from raw | `derived_*` tables |
| **Interpretation** | Analysis, opinion, banter | Your response only — never stored as fact |

Never let these mix. Derived tables must be fully reproducible by deleting them
and rerunning the calculators over raw data. If that stops being true, something
has leaked.

## 2. Never invent a number

If the answer isn't in the database, the answer is "that isn't in the database."

- Do not estimate to fill a gap.
- Do not infer a statistic that wasn't computed.
- Do not produce a number for banter or narrative that no query returns.
- If a query returns nothing, say it returned nothing.

A wrong number stated confidently is the worst possible failure mode here. An
admission of missing data is a completely acceptable one.

## 3. Separate what happened from what's estimated

Always label which of these you're doing:

- **Fact** — stored raw data. "You scored 62 in GW3."
- **Computed** — derived from facts by a documented formula. "Your captain
  efficiency is 71%."
- **Projection** — a model output with assumptions. "Simulations give you a 34%
  title chance."
- **Opinion** — your read. Say so.

Never present a projection in the grammar of a fact.

## 4. Confidence gates

Every derived row carries `gws_played` and `is_provisional`. Respect them.

| Metrics | Minimum GWs | Below that |
|---|---|---|
| Ledger, recap, manager-skill | 1 | Show normally |
| Luck, all-play, expected wins, power rankings | 10 | **Withhold** |
| Playoff and title projections | 15 | **Withhold** |

Below the threshold, say "insufficient sample — N gameweeks, need M." Do not
show the number with a caveat attached. The owner chose to wait rather than see
noisy estimates early. Honor that.

## 5. Never overwrite finalized history

Rows with `is_final = 1` are immutable. Do not UPDATE them. Do not "correct"
them. If FPL's current data disagrees with a finalized row, write a
`data_issues` row and surface it — that's a real event worth seeing, not a
discrepancy to smooth over.

The entire point of this database is answering "what was true in GW3" correctly,
years later.

## 6. Idempotency

Every write is an upsert on a natural key. Running any job twice must produce
identical state. If you add a write path, it must satisfy this.

## 7. Don't guess at the FPL API

Until Phase 1 has run, every endpoint in the spec is an assumption. Do not write
code that depends on a field existing until it's been observed in a real
response. Use `.get()` with defaults. Fail loudly on missing critical fields
rather than defaulting to zero — a silent zero becomes a wrong statistic forever.

## 8. Phase discipline

Do not start a phase before the previous one is verified working. "Verified"
means observed output, not an expectation that it should work.

Never claim something works unless it has actually been run.

## 9. Key facts about this league

- FPL-native H2H, league ID `683383`, 18 managers, all joined at GW1
- Match score = gameweek points **minus transfer hits**. 3 win / 1 draw / 0 loss
- Standard scoring. No custom rules, no money, no custom tiebreakers
- 2026/27 only. No prior-season data will ever exist
- Owner is Luel Waktola, *Midtable Crisis*
- Knockout configuration: **`ko_rounds = 3`**, confirmed live in Phase 1 (2026-09-12).
  This is a playoff league, not a pure title race — projections in Tier 5 are
  playoff odds. Regular season is GW1–35 (34-week double round-robin + 1 extra
  week); GW36–38 are the 3 knockout rounds, not yet seeded by FPL.

## 10. Gross vs net

`gross_points` is before hits. `net_points` is after, and is the H2H match score.
Margins, luck and ROI all use net. Getting this backwards silently corrupts most
of the analytics layer.

## 11. Chips change metric meaning

- Bench Boost weeks are excluded from "points left on bench" aggregates
- Triple Captain weeks use multiplier 3, not 2
- Free Hit squads revert the following week — a Free Hit squad is not evidence
  of a manager's ongoing roster
- Wildcard has no clean counterfactual; never report a single Wildcard ROI number

## 12. Tone

Direct and concrete. The owner is the only user and knows FPL well. Skip the
preamble, lead with the answer, keep caveats short but never drop the ones that
matter. Banter is welcome, but only over real numbers.
