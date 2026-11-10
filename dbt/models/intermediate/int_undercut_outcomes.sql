{#- Outcome of each candidate whose car ahead (B) stopped within the horizon: who was ahead at the
    start of B's lap (B's stop lap + 2), after B's out-lap. Added only after the definition was
    frozen in ADR 0016. Inconclusive means either car has no lap or no position at that instant
    (for example a retirement). Grain: one row per candidate. -#}
with responded as (
    select
        c.session_key, c.a_driver, c.b_driver, c.stop_lap, c.b_stop_lap,
        bl.date_start as evaluated_at,
        al.lap_number as a_lap_at_evaluation
    from {{ ref('int_undercut_candidates') }} as c
    left join {{ ref('fct_laps') }} as bl
        on bl.session_key = c.session_key
        and bl.driver_number = c.b_driver
        and bl.lap_number = c.b_stop_lap + 2
    left join {{ ref('fct_laps') }} as al
        on al.session_key = c.session_key
        and al.driver_number = c.a_driver
        and al.lap_number = c.b_stop_lap + 2
    where c.b_stop_lap is not null
),

positions as (
    select
        r.session_key, r.a_driver, r.stop_lap, p.driver_number, p.race_position
    from responded as r
    inner join {{ ref('stg_position') }} as p
        on p.session_key = r.session_key
        and p.driver_number in (r.a_driver, r.b_driver)
        and p.date <= r.evaluated_at
    qualify row_number() over (
        partition by r.session_key, r.a_driver, r.stop_lap, p.driver_number
        order by p.date desc
    ) = 1
)

select
    r.session_key, r.a_driver, r.stop_lap,
    r.evaluated_at,
    pa.race_position as a_position_at_evaluation,
    pb.race_position as b_position_at_evaluation,
    case
        when r.evaluated_at is null or r.a_lap_at_evaluation is null
            or pa.race_position is null or pb.race_position is null then 'inconclusive'
        when pa.race_position < pb.race_position then 'success'
        else 'failure'
    end as outcome
from responded as r
left join positions as pa
    on r.session_key = pa.session_key and r.a_driver = pa.a_driver
    and r.stop_lap = pa.stop_lap and pa.driver_number = r.a_driver
left join positions as pb
    on r.session_key = pb.session_key and r.a_driver = pb.a_driver
    and r.stop_lap = pb.stop_lap and pb.driver_number = r.b_driver
