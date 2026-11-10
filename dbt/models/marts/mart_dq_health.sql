{#- Data-quality health for the dashboard: rows quarantined and rows flagged, per race and rule. -#}
with quarantined as (
    select session_key, rule_code, 'quarantined' as outcome, count(*) as n_rows
    from {{ ref('stg_quarantine') }}
    group by session_key, rule_code
),

flagged as (
    select session_key, 'DQ-LAP-003' as rule_code, 'flagged' as outcome, count(*) as n_rows
    from {{ ref('stg_laps') }} where {{ has_flag('dq_flags', 'DQ-LAP-003') }}
    group by session_key
    union all
    select session_key, 'DQ-LAP-004', 'flagged', count(*)
    from {{ ref('stg_laps') }} where {{ has_flag('dq_flags', 'DQ-LAP-004') }}
    group by session_key
    union all
    select session_key, 'DQ-STINT-002', 'flagged', count(*)
    from {{ ref('stg_stints') }} where {{ has_flag('dq_flags', 'DQ-STINT-002') }}
    group by session_key
    union all
    select session_key, 'DQ-STINT-004', 'flagged', count(*)
    from {{ ref('stg_stints') }} where {{ has_flag('dq_flags', 'DQ-STINT-004') }}
    group by session_key
    union all
    select session_key, 'DQ-PIT-001', 'flagged', count(*)
    from {{ ref('stg_pit') }} where {{ has_flag('dq_flags', 'DQ-PIT-001') }}
    group by session_key
)

select
    u.session_key,
    ses.circuit_short_name,
    ses.session_name,
    u.rule_code,
    u.outcome,
    u.n_rows
from (select * from quarantined union all select * from flagged) as u
inner join {{ ref('stg_sessions') }} as ses
    on u.session_key = ses.session_key
