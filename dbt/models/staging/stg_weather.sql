select
    session_key, date, air_temperature, track_temperature, humidity, pressure, rainfall,
    wind_speed, wind_direction
from {{ source('raw', 'weather') }}
