{#- Joins only, no business rules. Adds the stint (compound, tyre age) and the latest weather
    reading at or before each lap's start. A weather join without ASOF keeps the SQL portable. -#}
with laps as (
    select * from {{ ref('stg_laps') }}
),

laps_with_stint as (
    select
        l.*,
        s.stint_number,
        s.compound,
        s.tyre_age_at_start + (l.lap_number - s.aligned_lap_start) as tyre_age
    from laps as l
    left join {{ ref('int_stints_aligned') }} as s
        on l.session_key = s.session_key
        and l.driver_number = s.driver_number
        and l.lap_number between s.aligned_lap_start and s.aligned_lap_end
),

latest_weather as (
    select
        l.session_key, l.driver_number, l.lap_number,
        w.track_temperature, w.air_temperature, w.rainfall
    from laps as l
    inner join {{ ref('stg_weather') }} as w
        on l.session_key = w.session_key
        and w.date <= l.date_start
    qualify row_number() over (
        partition by l.session_key, l.driver_number, l.lap_number
        order by w.date desc
    ) = 1
)

select
    ls.*,
    lw.track_temperature,
    lw.air_temperature,
    lw.rainfall
from laps_with_stint as ls
left join latest_weather as lw
    on ls.session_key = lw.session_key
    and ls.driver_number = lw.driver_number
    and ls.lap_number = lw.lap_number
