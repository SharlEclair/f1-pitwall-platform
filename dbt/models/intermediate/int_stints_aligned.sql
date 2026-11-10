{#- OpenF1 stint boundaries are not consistent between races. The pit endpoint always gives the
    in-lap (the next lap is the out-lap), but the stints endpoint either ends a stint ON that lap
    (most races) or starts the next stint on it (e.g. Melbourne, Montreal, Monaco 2024). Left
    alone, the second convention makes tyre age one lap too high and hides pit-ended stints.
    The convention is detected per session from its own pit stops (no race names hard-coded) and
    the stints are shifted so a stint always ends on its in-lap. -#}
with stints as (
    select * from {{ ref('stg_stints') }}
),

pit_laps as (
    select distinct session_key, driver_number, lap_number from {{ ref('stg_pit') }}
),

last_stint as (
    select session_key, driver_number, max(stint_number) as last_stint_number
    from stints
    group by session_key, driver_number
),

ends_on_pit_lap as (
    select p.session_key, count(*) as n
    from pit_laps as p
    inner join stints as s
        on p.session_key = s.session_key
        and p.driver_number = s.driver_number
        and p.lap_number = s.lap_end
    group by p.session_key
),

starts_on_pit_lap as (
    select p.session_key, count(*) as n
    from pit_laps as p
    inner join stints as s
        on p.session_key = s.session_key
        and p.driver_number = s.driver_number
        and p.lap_number = s.lap_start
        and s.stint_number > 1
    group by p.session_key
),

alignment as (
    select
        ses.session_key,
        case when coalesce(sp.n, 0) > coalesce(ep.n, 0) then 1 else 0 end as lap_shift
    from {{ ref('stg_sessions') }} as ses
    left join ends_on_pit_lap as ep on ses.session_key = ep.session_key
    left join starts_on_pit_lap as sp on ses.session_key = sp.session_key
)

select
    s.session_key,
    s.driver_number,
    s.stint_number,
    s.compound,
    s.tyre_age_at_start,
    s.lap_start,
    s.lap_end,
    case when a.lap_shift = 1 and s.stint_number > 1 then s.lap_start + 1 else s.lap_start end
        as aligned_lap_start,
    case when a.lap_shift = 1 and s.stint_number < ls.last_stint_number then s.lap_end + 1
        else s.lap_end end as aligned_lap_end,
    a.lap_shift = 1 as was_shifted,
    s.stint_number = ls.last_stint_number as is_final_stint,
    s.dq_flags
from stints as s
inner join alignment as a on s.session_key = a.session_key
inner join last_stint as ls
    on s.session_key = ls.session_key and s.driver_number = ls.driver_number
