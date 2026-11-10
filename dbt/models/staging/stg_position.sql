select session_key, driver_number, date, race_position, dq_flags
from {{ source('raw', 'position') }}
