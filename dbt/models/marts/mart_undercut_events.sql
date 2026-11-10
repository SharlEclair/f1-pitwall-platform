{#- Question 3: every undercut candidate with its outcome. Grain: one row per (session, A, stop lap).
    `outcome` is null when B did not stop within the horizon. Which rows count as attempts, and
    under which thresholds, is decided in mart_undercut_summary (ADR 0016). -#}
select
    c.session_key, c.season, c.circuit_short_name,
    c.a_driver, c.b_driver, c.stop_lap, c.b_stop_lap, c.response_laps,
    c.a_position, c.b_position, c.gap_s,
    c.b_stopped_same_or_previous_lap, c.neutralised_in_window,
    o.a_position_at_evaluation, o.b_position_at_evaluation,
    o.outcome
from {{ ref('int_undercut_candidates') }} as c
left join {{ ref('int_undercut_outcomes') }} as o
    on c.session_key = o.session_key and c.a_driver = o.a_driver and c.stop_lap = o.stop_lap
