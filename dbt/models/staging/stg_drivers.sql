select
    session_key, driver_number, name_acronym, full_name, team_name, team_colour, country_code
from {{ source('raw', 'drivers') }}
