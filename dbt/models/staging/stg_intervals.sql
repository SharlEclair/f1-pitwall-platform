select session_key, driver_number, date, interval_s, gap_to_leader_s, laps_down, dq_flags
from {{ source('raw', 'intervals') }}
