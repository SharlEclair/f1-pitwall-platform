{#- Question 2: what does a pit stop cost, normally and under Safety Car / VSC?
    Grain: race (or sprint) x track status at the time of the stop. Stops over 60 s (red-flag
    waits, flagged DQ-PIT-001) are excluded so they do not distort the medians. -#}
select
    session_key,
    circuit_short_name,
    track_status_at_pit as track_status,
    count(*) as n_stops,
    count(pit_loss_s) as n_stops_with_loss,
    median(lane_duration) as median_lane_duration_s,
    median(pit_loss_s) as median_pit_loss_s
from {{ ref('fct_pit_stops') }}
where not is_long_stop and track_status_at_pit is not null
group by session_key, circuit_short_name, track_status_at_pit
