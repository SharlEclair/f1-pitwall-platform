{#- Undercut candidates: every ordinary green-flag pit stop by a car (A) that had another car (B)
    directly ahead when the in-lap began. Question 3 (how often does an undercut work?).
    Race order comes from `position` events (the latest event at or before the instant) and the
    gap from the latest `intervals` row of A within `undercut_max_gap_age_s` seconds of it; a
    missing or stale gap stays null (unknown), never imputed (ADR 0015). B's response is its
    next stop within `undercut_horizon_laps` laps. This model has NO outcome column on purpose:
    the definition is frozen in an ADR before any outcome is computed (see int_undercut_outcomes).
    Grain: one row per (session, A, stop lap). -#}
with stops as (
    select
        p.session_key, p.season, p.circuit_short_name,
        p.driver_number as a_driver, p.lap_number as stop_lap, l.date_start as in_lap_start
    from {{ ref('fct_pit_stops') }} as p
    inner join {{ ref('fct_laps') }} as l
        on p.session_key = l.session_key
        and p.driver_number = l.driver_number
        and p.lap_number = l.lap_number
    where not p.is_long_stop
        and p.track_status_at_pit = 'GREEN'
        and l.date_start is not null
),

order_at_start as (
    select
        s.session_key, s.a_driver, s.stop_lap,
        pos.driver_number as other_driver, pos.race_position
    from stops as s
    inner join {{ ref('stg_position') }} as pos
        on pos.session_key = s.session_key
        and pos.date <= s.in_lap_start
    qualify row_number() over (
        partition by s.session_key, s.a_driver, s.stop_lap, pos.driver_number
        order by pos.date desc
    ) = 1
),

-- A tie (two cars sharing a position in the stream, a missed update) makes "directly ahead"
-- ambiguous, so pairs where A's place or the place ahead is shared are not candidates.
unique_order as (
    select
        o.*,
        count(*) over (
            partition by session_key, a_driver, stop_lap, race_position
        ) as n_at_position
    from order_at_start as o
),

with_car_ahead as (
    select
        s.*,
        a.race_position as a_position,
        b.other_driver as b_driver
    from stops as s
    inner join unique_order as a
        on s.session_key = a.session_key and s.a_driver = a.a_driver
        and s.stop_lap = a.stop_lap and a.other_driver = s.a_driver and a.n_at_position = 1
    inner join unique_order as b
        on s.session_key = b.session_key and s.a_driver = b.a_driver
        and s.stop_lap = b.stop_lap and b.race_position = a.race_position - 1
        and b.n_at_position = 1
),

gap_at_start as (
    select
        c.session_key, c.a_driver, c.stop_lap,
        i.interval_s, i.laps_down, i.date as gap_measured_at
    from with_car_ahead as c
    inner join {{ ref('stg_intervals') }} as i
        on i.session_key = c.session_key
        and i.driver_number = c.a_driver
        and i.date <= c.in_lap_start
        and i.date > {{ seconds_before('c.in_lap_start', var('undercut_max_gap_age_s')) }}
    qualify row_number() over (
        partition by c.session_key, c.a_driver, c.stop_lap order by i.date desc
    ) = 1
),

b_response as (
    select
        c.session_key, c.a_driver, c.stop_lap,
        min(case when bp.lap_number > c.stop_lap then bp.lap_number end) as b_stop_lap,
        max(case when bp.lap_number in (c.stop_lap - 1, c.stop_lap) then 1 else 0 end)
            as b_stopped_same_or_previous_lap
    from with_car_ahead as c
    left join {{ ref('fct_pit_stops') }} as bp
        on bp.session_key = c.session_key
        and bp.driver_number = c.b_driver
        and bp.lap_number between c.stop_lap - 1 and c.stop_lap + {{ var('undercut_horizon_laps') }}
    group by c.session_key, c.a_driver, c.stop_lap
),

neutralised_laps as (
    select distinct session_key, lap_number
    from {{ ref('fct_laps') }}
    where track_status <> 'GREEN'
)

select
    c.session_key, c.season, c.circuit_short_name,
    c.a_driver, c.b_driver, c.stop_lap, c.in_lap_start,
    c.a_position, c.a_position - 1 as b_position,
    case when g.laps_down is null then g.interval_s end as gap_s,
    r.b_stop_lap,
    r.b_stop_lap - c.stop_lap as response_laps,
    r.b_stopped_same_or_previous_lap = 1 as b_stopped_same_or_previous_lap,
    -- any lap number from A's stop to two laps after B's stop was under SC, VSC or red flag
    exists (
        select 1 from neutralised_laps as n
        where n.session_key = c.session_key
            and n.lap_number between c.stop_lap and coalesce(r.b_stop_lap, c.stop_lap) + 2
    ) as neutralised_in_window
from with_car_ahead as c
left join gap_at_start as g
    on c.session_key = g.session_key and c.a_driver = g.a_driver and c.stop_lap = g.stop_lap
inner join b_response as r
    on c.session_key = r.session_key and c.a_driver = r.a_driver and c.stop_lap = r.stop_lap
