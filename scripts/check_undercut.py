"""Independent re-implementation of ADR 0016 in plain Python over the silver Parquet.

Usage (after export_marts and a local silver copy): python scripts/check_undercut.py
Compares the attempts and outcomes with mart_undercut_events; prints any difference."""

import bisect
import collections
import glob

import polars as pl

G, N, EVAL_OFFSET, MAX_AGE = 3.0, 3, 2, 10.0
ev = pl.read_parquet("data/export/marts/mart_undercut_events.parquet")
mart = {}
for r in ev.iter_rows(named=True):
    ok = (
        r["gap_s"] is not None
        and r["gap_s"] <= G
        and r["response_laps"] is not None
        and 1 <= r["response_laps"] <= N
        and not r["b_stopped_same_or_previous_lap"]
        and not r["neutralised_in_window"]
    )
    if ok:
        mart[(r["session_key"], r["a_driver"], r["stop_lap"])] = (r["b_driver"], r["outcome"])
found = {}
for sdir in sorted(glob.glob("data/silver/season=*/session_key=*")):
    sk = int(sdir.split("session_key=")[1])
    laps = pl.read_parquet(f"{sdir}/laps.parquet")
    pit = pl.read_parquet(f"{sdir}/pit.parquet")
    pos = pl.read_parquet(f"{sdir}/position.parquet")
    itv = pl.read_parquet(f"{sdir}/intervals.parquet")
    if pit.height == 0 or pos.height == 0:
        continue
    lap_start = {
        (r["driver_number"], r["lap_number"]): r["date_start"]
        for r in laps.iter_rows(named=True)
        if r["date_start"] is not None
    }
    lap_status = {
        (r["driver_number"], r["lap_number"]): r["track_status"] for r in laps.iter_rows(named=True)
    }
    neutral = {r["lap_number"] for r in laps.iter_rows(named=True) if r["track_status"] != "GREEN"}
    pe = collections.defaultdict(list)
    for r in pos.sort("date").iter_rows(named=True):
        pe[r["driver_number"]].append((r["date"], r["race_position"]))
    pe_t = {d: [x[0] for x in v] for d, v in pe.items()}
    ie = collections.defaultdict(list)
    for r in itv.sort("date").iter_rows(named=True):
        ie[r["driver_number"]].append((r["date"], r["interval_s"], r["laps_down"]))
    ie_t = {d: [x[0] for x in v] for d, v in ie.items()}

    def pos_at(d, t, pe=pe, pe_t=pe_t):
        if d not in pe:
            return None
        k = bisect.bisect_right(pe_t[d], t) - 1
        return pe[d][k][1] if k >= 0 else None

    stops = {
        (r["driver_number"], r["lap_number"])
        for r in pit.iter_rows(named=True)
        if (r["lane_duration"] or 0) <= 60
    }
    all_stops = collections.defaultdict(set)
    for r in pit.iter_rows(named=True):
        all_stops[r["driver_number"]].add(r["lap_number"])
    for a, L in stops:
        if lap_status.get((a, L)) != "GREEN" or (a, L) not in lap_start:
            continue
        t0 = lap_start[(a, L)]
        order = {d: pos_at(d, t0) for d in pe}
        if order.get(a) is None:
            continue
        pa = order[a]
        if sum(1 for v in order.values() if v == pa) != 1:
            continue
        ahead = [d for d, v in order.items() if v == pa - 1]
        if len(ahead) != 1:
            continue
        b = ahead[0]
        # gap
        k = bisect.bisect_right(ie_t.get(a, []), t0) - 1
        if k < 0:
            continue
        t_i, gap, down = ie[a][k]
        if (t0 - t_i).total_seconds() >= MAX_AGE or down is not None or gap is None or gap > G:
            continue
        b_stops = [lap for lap in all_stops[b] if L - 1 <= lap <= L + 10]
        if any(lap in (L - 1, L) for lap in b_stops):
            continue
        later = [lap for lap in b_stops if lap > L]
        if not later:
            continue
        lb = min(later)
        if not (1 <= lb - L <= N):
            continue
        if any(n for n in neutral if L <= n <= lb + 2):
            continue
        te = lap_start.get((b, lb + 2))
        if te is None or (a, lb + 2) not in lap_start:
            outcome = "inconclusive"
        else:
            qa, qb = pos_at(a, te), pos_at(b, te)
            outcome = (
                "inconclusive"
                if qa is None or qb is None
                else ("success" if qa < qb else "failure")
            )
        found[(sk, a, L)] = (b, outcome)
print("mart primary attempts", len(mart), "independent", len(found))
only_m = set(mart) - set(found)
only_i = set(found) - set(mart)
print(
    "only in mart",
    len(only_m),
    sorted(only_m)[:5],
    "only in independent",
    len(only_i),
    sorted(only_i)[:5],
)
both = set(mart) & set(found)
diff = [k for k in both if mart[k] != found[k]]
print(
    "shared",
    len(both),
    "differing (B or outcome)",
    len(diff),
    [(k, mart[k], found[k]) for k in diff[:5]],
)
c = collections.Counter(v[1] for v in found.values())
print("independent outcomes", dict(c))
