{{ config(severity='warn') }}
{#- Warns (does not fail) for every session whose stints and pit stops disagree. Such sessions are
    already excluded from clean laps by int_session_stint_check, so the warning is a visible
    reminder of the data problem, not a build breaker. Phase 1 used this as a hard failure to
    detect a third stint-boundary convention; the wider data found one (see ADR 0017). -#}
select session_key, n_stops, n_matched
from {{ ref('int_session_stint_check') }}
where not stint_boundaries_consistent
