{#- One row per pit stop. `pit_loss_s` is an estimate: the in-lap plus the out-lap time minus two
    reference laps. Under green flags the reference is the driver's median clean lap in that
    session; under SC / VSC it is the session's median lap by cars that were not pitting, in the
    same status, so the slowdown everyone suffers is not counted as pit loss. It is only estimated
    when the in-lap and out-lap share a track status (a VSC that ends mid-stop would otherwise
    produce a nonsense negative loss); otherwise it is null. Fuel burn makes early laps slower
    than the median, so the estimate is approximate. lane_duration is the
    pit-lane transit time; stop_duration (stationary time) exists only for the last races of 2024. -#}
with driver_reference as (
    select session_key, driver_number, median(lap_duration) as reference_lap_duration
    from {{ ref('fct_laps') }}
    where is_clean_lap
    group by session_key, driver_number
),

status_reference as (
    select session_key, track_status, median(lap_duration) as status_reference_lap_duration
    from {{ ref('fct_laps') }}
    where lap_duration > 0 and lap_number > 1 and not is_pit_out_lap and not is_in_lap
    group by session_key, track_status
)

select
    p.session_key,
    ses.circuit_short_name,
    p.driver_number,
    p.lap_number,
    p.date,
    p.lane_duration,
    p.stop_duration,
    in_lap.track_status as track_status_at_pit,
    in_lap.lap_duration as in_lap_duration,
    out_lap.lap_duration as out_lap_duration,
    case when in_lap.track_status = 'GREEN'
        then r.reference_lap_duration
        else sr.status_reference_lap_duration
    end as reference_lap_duration,
    case when in_lap.track_status = out_lap.track_status then
        in_lap.lap_duration + out_lap.lap_duration - 2 * (
            case when in_lap.track_status = 'GREEN'
                then r.reference_lap_duration
                else sr.status_reference_lap_duration
            end
        )
    end as pit_loss_s,
    {{ has_flag('p.dq_flags', 'DQ-PIT-001') }} as is_long_stop,
    p.dq_flags
from {{ ref('stg_pit') }} as p
inner join {{ ref('stg_sessions') }} as ses
    on p.session_key = ses.session_key
left join {{ ref('fct_laps') }} as in_lap
    on p.session_key = in_lap.session_key
    and p.driver_number = in_lap.driver_number
    and p.lap_number = in_lap.lap_number
left join {{ ref('fct_laps') }} as out_lap
    on p.session_key = out_lap.session_key
    and p.driver_number = out_lap.driver_number
    and p.lap_number + 1 = out_lap.lap_number
    and out_lap.is_pit_out_lap
left join driver_reference as r
    on p.session_key = r.session_key and p.driver_number = r.driver_number
left join status_reference as sr
    on p.session_key = sr.session_key and in_lap.track_status = sr.track_status
