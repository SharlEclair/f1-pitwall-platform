select
    session_key, driver_number, lap_number, date, lane_duration, pit_duration, stop_duration,
    dq_flags
from {{ source('raw', 'pit') }}
