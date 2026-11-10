{#- Do the stints and the pit stops of a session agree? After alignment (ADR 0012) an ordinary pit
    stop should fall on the last lap of a stint. In 2024 every session with pit stops matched at
    least 97%; in 2025 five sessions matched 10% to 88% (Miami race and sprint, Spa, Monaco, and
    Lusail sprint on 3 stops), so their tyre ages cannot be trusted. A session is treated as
    inconsistent when it has at least 5 ordinary stops and fewer than 90% match; with fewer
    stops there is too little evidence either way, so it is kept. Stops over 60 s (flagged
    DQ-PIT-001, red-flag tyre changes) are excluded because their stints were quarantined. -#}
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

select
    ses.session_key,
    coalesce(m.n_stops, 0) as n_stops,
    coalesce(m.n_matched, 0) as n_matched,
    m.n_matched * 1.0 / nullif(m.n_stops, 0) as match_share,
    not coalesce(m.n_stops >= 5 and m.n_matched * 1.0 / m.n_stops < 0.9, false)
        as stint_boundaries_consistent
from {{ ref('stg_sessions') }} as ses
left join matched as m
    on ses.session_key = m.session_key
