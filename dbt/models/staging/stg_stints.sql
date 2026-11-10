select
    session_key, driver_number, stint_number, lap_start, lap_end, compound, tyre_age_at_start,
    dq_flags
from {{ source('raw', 'stints') }}
