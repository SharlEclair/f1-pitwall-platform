{#- One row per lap. `is_clean_lap` is the definition used for degradation and the lap-time model:
    a timed, non-first lap that is not an in/out lap, ran under green flags, belongs to a known
    stint in a session whose stints agree with its pit stops (int_session_stint_check) and carries no data-quality flags. `fuel_corrected_duration` adds back the time the car
    gained from burning fuel, using the fuel_effect_s_per_lap assumption in dbt_project.yml. -#}
select
    c.session_key,
    ses.session_name,
    ses.circuit_short_name,
    ses.race_date,
    ses.year as season,
    c.driver_number,
    c.lap_number,
    c.date_start,
    c.lap_duration,
    c.duration_sector_1,
    c.duration_sector_2,
    c.duration_sector_3,
    c.is_pit_out_lap,
    c.is_in_lap,
    c.track_status,
    c.stint_number,
    c.compound,
    c.tyre_age,
    c.track_temperature,
    c.air_temperature,
    c.rainfall,
    c.dq_flags,
    chk.stint_boundaries_consistent,
    coalesce(
        c.lap_duration > 0
        and c.lap_number > 1
        and not c.is_pit_out_lap
        and not c.is_in_lap
        and c.track_status = 'GREEN'
        and c.compound is not null
        and chk.stint_boundaries_consistent
        and {{ no_flags('c.dq_flags') }},
        false
    ) as is_clean_lap,
    c.lap_duration + {{ var('fuel_effect_s_per_lap') }} * (c.lap_number - 1)
        as fuel_corrected_duration
from {{ ref('int_lap_context') }} as c
inner join {{ ref('stg_sessions') }} as ses
    on c.session_key = ses.session_key
inner join {{ ref('int_session_stint_check') }} as chk
    on c.session_key = chk.session_key
