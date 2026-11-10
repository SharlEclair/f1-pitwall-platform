{#- Question 3: how often does an undercut work, under the definition in ADR 0016?
    One row per sensitivity-grid cell (seeds/undercut_grid.csv) and season scope ('all' or a
    season). Attempts are candidates with a known gap at most the cell's threshold whose car ahead
    stopped within the cell's response window, not on the same or previous lap, and (when the cell
    says so) with no neutralised lap in the window. The rate is successes over successes plus
    failures; inconclusive attempts are counted but excluded from it. Interval: 95% Wilson. -#}
with scoped as (
    select
        g.grid_id, g.gap_s as gap_threshold_s, g.response_laps as response_window_laps,
        g.exclude_neutralised, g.is_primary,
        e.season, e.session_key, e.outcome
    from {{ ref('undercut_grid') }} as g
    inner join {{ ref('mart_undercut_events') }} as e
        on e.gap_s <= g.gap_s
        and e.response_laps between 1 and g.response_laps
        and not e.b_stopped_same_or_previous_lap
        and (not g.exclude_neutralised or not e.neutralised_in_window)
),

by_scope as (
    select grid_id, gap_threshold_s, response_window_laps, exclude_neutralised, is_primary,
        'all' as season_scope, outcome, session_key
    from scoped
    union all
    select grid_id, gap_threshold_s, response_window_laps, exclude_neutralised, is_primary,
        cast(season as varchar), outcome, session_key
    from scoped
),

counts as (
    select
        grid_id, gap_threshold_s, response_window_laps, exclude_neutralised, is_primary,
        season_scope,
        count(*) as n_attempts,
        sum(case when outcome = 'success' then 1 else 0 end) as n_success,
        sum(case when outcome = 'failure' then 1 else 0 end) as n_failure,
        sum(case when outcome = 'inconclusive' then 1 else 0 end) as n_inconclusive,
        count(distinct session_key) as n_sessions
    from by_scope
    group by grid_id, gap_threshold_s, response_window_laps, exclude_neutralised, is_primary,
        season_scope
),

rates as (
    select
        *,
        n_success + n_failure as n_decided,
        n_success * 1.0 / nullif(n_success + n_failure, 0) as success_rate
    from counts
)

select
    *,
    {#- Wilson score interval, z = 1.96 -#}
    (success_rate + 1.96 * 1.96 / (2 * n_decided))
        / (1 + 1.96 * 1.96 / n_decided)
        - 1.96 * sqrt(success_rate * (1 - success_rate) / n_decided
            + 1.96 * 1.96 / (4 * n_decided * n_decided))
        / (1 + 1.96 * 1.96 / n_decided) as wilson_low,
    (success_rate + 1.96 * 1.96 / (2 * n_decided))
        / (1 + 1.96 * 1.96 / n_decided)
        + 1.96 * sqrt(success_rate * (1 - success_rate) / n_decided
            + 1.96 * 1.96 / (4 * n_decided * n_decided))
        / (1 + 1.96 * 1.96 / n_decided) as wilson_high
from rates
