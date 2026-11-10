select session_key, endpoint, row_index, source_key, rule_code, severity, reason, row_json
from {{ source('raw', 'quarantine') }}
