select
    session_key, driver_number, lap_number, date_start,
    duration_sector_1, duration_sector_2, duration_sector_3, lap_duration,
    is_pit_out_lap, is_in_lap, track_status, i1_speed, i2_speed, st_speed, dq_flags
from {{ source('raw', 'laps') }}
