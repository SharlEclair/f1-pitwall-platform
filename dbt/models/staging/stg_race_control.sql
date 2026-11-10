select session_key, date, driver_number, lap_number, category, flag, scope, message
from {{ source('raw', 'race_control') }}
