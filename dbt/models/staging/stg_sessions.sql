select
    session_key, meeting_key, session_name, circuit_short_name, country_name, location,
    cast(race_date as date) as race_date, year
from {{ ref('sessions') }}
