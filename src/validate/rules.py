"""Rule registry: every data-quality rule is data (code, severity, description, rationale).

Severities (ADR 0005):
  reject - row cannot be trusted; goes to quarantine, not to silver.
  flag   - row is kept in silver with the code in `dq_flags`; never silently dropped.
  warn   - counted in the run summary only.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Rule:
    code: str
    entity: str
    severity: str
    description: str
    rationale: str


RULES = [
    Rule("DQ-API-001", "response", "reject",
         "Row is missing a field the endpoint is expected to return",
         "Schema drift breaks typed loads and downstream models"),
    Rule("DQ-API-002", "response", "warn",
         "Row has a field that is not in the expected schema",
         "Early signal that the API changed; new fields are ignored until reviewed"),
    Rule("DQ-LAP-001", "lap", "reject",
         "Duplicate (session, driver, lap_number)",
         "Duplicates double-count laps and break the lap grain"),
    Rule("DQ-LAP-002", "lap", "reject",
         "Null lap_duration that is not lap 1, a red-flag lap or the driver's last recorded lap",
         "An unexplained missing time biases degradation fits"),
    Rule("DQ-LAP-003", "lap", "flag",
         "Null lap_duration on lap 1, a red-flag lap or the driver's last recorded lap",
         "Expected (start, red flag, retirement) but the lap has no usable time"),
    Rule("DQ-LAP-004", "lap", "flag",
         "Green-flag, non-pit lap slower than 1.3x the session median",
         "Unexplained slow laps contaminate clean-lap models; review before exclusion"),
    Rule("DQ-LAP-005", "lap", "reject",
         "Sector times differ from lap_duration by more than 0.05 s",
         "Inconsistent timing; one of the values is wrong"),
    Rule("DQ-STINT-001", "stint", "reject",
         "Stint ends before it starts, or leaves a gap or overlap with the previous stint",
         "Broken stints give wrong tyre ages"),
    Rule("DQ-STINT-002", "stint", "flag",
         "Driver's last stint ends on a different lap from their last recorded lap",
         "Tyre age on the final lap may be off by one"),
    Rule("DQ-STINT-003", "stint", "reject",
         "Compound is missing or not one of SOFT, MEDIUM, HARD, INTERMEDIATE, WET, UNKNOWN",
         "Unknown categories break compound-level analysis"),
    Rule("DQ-STINT-004", "stint", "flag",
         "Compound is UNKNOWN",
         "Valid API value, but unusable for compound degradation"),
    Rule("DQ-PIT-001", "pit", "flag",
         "lane_duration over 60 s",
         "Red-flag waits and long stops would distort pit-loss estimates"),
    Rule("DQ-PIT-002", "pit", "warn",
         "stop_duration is null",
         "Stationary time is only published for some sessions (ADR 0004)"),
    Rule("DQ-POS-001", "position", "reject",
         "Position is not a whole number from 1 to 22",
         "The grid has at most 22 cars; anything else is a corrupt value (ADR 0015)"),
    Rule("DQ-POS-002", "position", "reject",
         "More than one position row for the same driver at the same timestamp",
         "Position is an event stream: two values at one instant cannot both be the order"),
    Rule("DQ-POS-003", "position", "reject",
         "Driver number is not in the session's drivers",
         "An unknown driver cannot be joined to laps or stints"),
    Rule("DQ-POS-004", "position", "flag",
         "Two or more drivers hold the same position for more than 10 s",
         "A race order is a permutation; a lasting duplicate means a missed update"),
    Rule("DQ-INT-001", "interval", "reject",
         "interval or gap_to_leader is not a number, null or text like '+1 LAP'",
         "Unexpected types break typed loads and gap arithmetic"),
    Rule("DQ-INT-002", "interval", "reject",
         "interval or gap_to_leader is negative",
         "A gap to the car ahead or the leader cannot be negative"),
    Rule("DQ-INT-003", "interval", "flag",
         "gap_to_leader is smaller than interval",
         "The gap to the leader cannot be smaller than the gap to the car ahead"),
    Rule("DQ-SESS-001", "driver", "reject",
         "Driver number is mapped to more than one team in a session",
         "Ambiguous driver identity breaks joins"),
    Rule("DQ-SESS-002", "session", "warn",
         "Endpoint returned no rows for a finished session",
         "May be legitimate (a sprint with no pit stops) or a data gap"),
    Rule("DQ-FRESH-001", "session", "warn",
         "Finished session has not been ingested after the allowed delay",
         "Distinguishes 'not yet run' from 'missing data'"),
]

REGISTRY = {rule.code: rule for rule in RULES}

KNOWN_COMPOUNDS = {"SOFT", "MEDIUM", "HARD", "INTERMEDIATE", "WET", "UNKNOWN"}

# Fields OpenF1 documents as deprecated and to be removed at the end of the 2026 season. They stay
# accepted when present but are no longer required, so their removal does not quarantine every row.
OPTIONAL_FIELDS = {"pit": {"pit_duration"}, "drivers": {"country_code"}}

# Field sets observed identically across all ingested 2023 to 2025 sessions.
EXPECTED_FIELDS = {
    "laps": {
        "meeting_key", "session_key", "driver_number", "lap_number", "date_start",
        "duration_sector_1", "duration_sector_2", "duration_sector_3", "i1_speed", "i2_speed",
        "is_pit_out_lap", "lap_duration", "segments_sector_1", "segments_sector_2",
        "segments_sector_3", "st_speed",
    },
    "stints": {
        "meeting_key", "session_key", "stint_number", "driver_number", "lap_start", "lap_end",
        "compound", "tyre_age_at_start",
    },
    "pit": {
        "date", "session_key", "stop_duration", "lap_number", "lane_duration", "meeting_key",
        "driver_number", "pit_duration",
    },
    "position": {"date", "session_key", "meeting_key", "driver_number", "position"},
    "intervals": {
        "date", "session_key", "meeting_key", "driver_number", "interval", "gap_to_leader",
    },
    "drivers": {
        "meeting_key", "session_key", "driver_number", "broadcast_name", "full_name",
        "name_acronym", "team_name", "team_colour", "first_name", "last_name", "headshot_url",
        "country_code",
    },
    "race_control": {
        "meeting_key", "session_key", "date", "driver_number", "lap_number", "category", "flag",
        "scope", "sector", "qualifying_phase", "message",
    },
    "weather": {
        "date", "session_key", "rainfall", "humidity", "air_temperature", "pressure",
        "wind_direction", "meeting_key", "track_temperature", "wind_speed",
    },
}
