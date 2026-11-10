# ADR 0016: Definition of an undercut attempt (frozen before any outcome was computed)

- Status: accepted and frozen
- Date: 2026-11-11

## Context
Question 3 asks how often an undercut works. The answer is a frequency under a stated definition, not
"the" undercut rate, and it is not a validation of any single-stop model probability (such as the 53.77%
an earlier, separate simulator reported for one hypothetical Monza stop; that is a model estimate for
one stop, this is a historical frequency over many). Every threshold below was chosen from the
distribution of the candidates' gaps and response timing, **before any outcome (who ended up ahead)
was computed**. The candidate model (`int_undercut_candidates`) has no outcome column; the outcome model
was added only after this ADR was committed.

## What was looked at before freezing (2023 to 2025 candidates, one logged query)
- 1,588 green-flag ordinary pit stops had a car directly ahead when the in-lap began; 1,463 of them had
  a usable gap. Gap quartiles 1.26, 2.71 and 5.69 s (10th and 90th percentiles 0.68 and 10.1 s).
- The share of candidates whose car ahead stopped within 8 laps (not on the same or previous lap, no
  neutralisation) is 27% to 42% across gap buckets, with no natural break in the gap distribution.
  The gap threshold is therefore a judgement call, and the sensitivity table is part of the result.
- Laps from A's stop to B's stop (gap up to 3 s): 103 stops one lap later, 39 two laps, 22 three laps,
  then a flat 14 to 20 per lap up to ten laps. The flat tail is stops that do not respond to A; the
  excess over it is in the first three laps.

## Definition (primary)
An **attempt** is a pair (A, B) in one race or sprint session where:
1. A makes an ordinary pit stop on lap L (not over 60 s, under green flag), and B was directly ahead of A
   (race position one better) when A's lap L began; positions come from the latest `position` event at or
   before that instant.
2. The gap at that instant (A's latest `intervals` value, at most 10 s old, not a lapped-car value) is
   **at most 3.0 s**. A missing or stale gap excludes the pair; it is never imputed.
3. B did not stop on lap L-1 or L, and stops on lap L+1 to **L+3** (the response window, N = 3).
4. No lap number from L to B's stop lap + 2 was under a Safety Car, VSC or red flag for any car.

**Outcome**, measured at the start of B's lap (B's stop lap + 2), after B's out-lap, from the same
position events:
- **Success:** A is ahead of B. **Failure:** B is ahead of A.
- **Inconclusive:** either car has no position or no lap at that instant (for example a retirement).
  Inconclusive attempts are counted and reported but are not in the rate's denominator.
- Pairs not meeting 1 to 4 are not attempts ("excluded"); pairs whose B stops after more than N laps, or
  never within ten laps, are counted separately as "no response within N".

The rate is successes over (successes + failures).

## Reporting rules
- Every rate carries n and a 95% Wilson interval; the primary also carries a bootstrap interval over
  races, because attempts within one race are not independent.
- A sensitivity grid is published with the primary: gap threshold 1, 2, 3, 5 and 10 s; response window
  1, 2, 3 and 5 laps; neutralised windows excluded or included. If the answer swings widely, that is the
  finding.
- Results are reported pooled and per season, with n in every row.

## Confounders (what the rate does not control)
- **Pace difference between the two cars**: a faster car passes anyway, an undercut or not. Not controlled
  (a descriptive pace-gap split may be shown, labelled exploratory).
- Tyre compound and age of both cars, out-lap traffic, DRS and overtaking difficulty by circuit, team stop
  speed (`stop_duration` is missing for 2023 and most of 2024), drivers' choices after the stop, and
  positions gained or lost to cars other than B. None is controlled.
- Position is the on-track order from the data, not the official classification.
- Sample size is limited by the definition (164 attempts under the primary, from 49 sessions, before
  inconclusive ones are removed); wider data is the only honest remedy.

## Consequences
- The published rate means "under this definition". Changing a threshold produces a different, equally
  valid number; the grid shows how much.
- Any later change to the primary definition needs a new ADR that says why and supersedes this one.

## Addendum (before any outcome was computed)
Building the mart showed one candidate with two cars sharing the position ahead of A (a missed position
update at Hungary 2024), which made "directly ahead" ambiguous and the event key non-unique. Pairs where
A's place or the place ahead is shared by two cars are now not candidates. This is a correction to
rule 1, found by a uniqueness test on the candidate grain, and was made without looking at outcomes.

## Result and cross-check (2026-11-11, after the freeze)
- Under the primary definition there are 164 attempts in 49 sessions: 73 successes, 90 failures and 1
  inconclusive (rate 44.8%, 95% Wilson 37.4% to 52.5%; bootstrapping races, 35.2% to 53.4%). Per season:
  47.9% (2023), 45.5% (2024) and 40.8% (2025). Full tables: `docs/UNDERCUT-RESULTS.md`.
- The sensitivity grid moves the answer far more than the primary cell suggests: with a 3-lap window the
  rate runs from 73% (gap up to 1 s, n=48) to 28% (gap up to 10 s, n=298). The headline is one point on
  that curve, not a stand-alone number.
- **Independent check:** a separate plain-Python implementation of this definition, run over the silver
  Parquet, produced the same 164 attempts, the same car ahead for each, and the same 73/90/1 outcomes
  as the dbt mart (0 differences). Seven hand-built golden scenarios (dbt unit tests) cover a
  success, a failure, an inconclusive attempt, a stale gap, a neutralised window, a tied position and
  the choice of the car directly ahead.
