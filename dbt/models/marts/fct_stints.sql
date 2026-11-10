{#- One row per stint, using stint boundaries aligned so a stint ends on its in-lap (see
    int_stints_aligned). A stint that ends with a pit stop is right-censored for tyre life: teams
    pit before the tyre falls off a cliff, so stint length is not tyre life. The original OpenF1
    boundaries are kept as source_lap_start / source_lap_end. -#}
with pit_laps as (
    select distinct session_key, driver_number, lap_number
    from {{ ref('stg_pit') }}
)

select
    s.session_key,
    ses.circuit_short_name,
    s.driver_number,
    s.stint_number,
    s.compound,
    s.aligned_lap_start as lap_start,
    s.aligned_lap_end as lap_end,
    s.aligned_lap_end - s.aligned_lap_start + 1 as stint_laps,
    s.tyre_age_at_start,
    p.lap_number is not null as ended_by_pit,
    s.is_final_stint,
    s.was_shifted,
    s.lap_start as source_lap_start,
    s.lap_end as source_lap_end,
    s.dq_flags
from {{ ref('int_stints_aligned') }} as s
inner join {{ ref('stg_sessions') }} as ses
    on s.session_key = ses.session_key
left join pit_laps as p
    on s.session_key = p.session_key
    and s.driver_number = p.driver_number
    and s.aligned_lap_end = p.lap_number
