{#- After alignment, ordinary pit stops should fall on the last lap of a stint. Fails for any race
    where fewer than 90% do, which would mean a third stint-boundary convention. Stops over 60 s
    (flagged DQ-PIT-001, red-flag tyre changes) are excluded: their stints are zero-length and
    were quarantined, so they cannot match. -#}
with matched as (
    select
        p.session_key,
        count(*) as n_stops,
        sum(case when s.lap_number is not null then 1 else 0 end) as n_matched
    from (
        select distinct session_key, driver_number, lap_number
        from {{ ref('stg_pit') }}
        where not {{ has_flag('dq_flags', 'DQ-PIT-001') }}
    ) as p
    left join (
        select session_key, driver_number, lap_end as lap_number
        from {{ ref('fct_stints') }}
    ) as s
        on p.session_key = s.session_key
        and p.driver_number = s.driver_number
        and p.lap_number = s.lap_number
    group by p.session_key
)

select session_key, n_stops, n_matched
from matched
where n_matched * 1.0 / n_stops < 0.9
