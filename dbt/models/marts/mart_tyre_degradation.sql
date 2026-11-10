{#- Question 1: how fast does each compound degrade, after correcting for fuel burn?
    Grain: race (or sprint) x dry compound. The slope is seconds per lap of tyre age from a
    within-stint (fixed-effects) least-squares fit on clean laps: each lap's time and tyre age are
    centred on its own stint's mean, so differences in driver pace and stint level do not leak
    into the slope. `slope_pooled_s_per_lap` is the simpler pooled fit, kept for comparison; the
    two can differ a lot. A slope is only reported with enough laps and spread in tyre age.
    `slope_uncorrected` shows how much fuel burn masks degradation. `censored_stint_share` is the
    share of those stints that ended in a pit stop (right-censored). The fuel effect is an
    assumption (dbt_project.yml), not a fitted value. -#}
with clean as (
    select * from {{ ref('fct_laps') }}
    where is_clean_lap and compound in ('SOFT', 'MEDIUM', 'HARD')
),

centred as (
    select
        session_key,
        circuit_short_name,
        session_name,
        compound,
        driver_number,
        stint_number,
        tyre_age,
        fuel_corrected_duration,
        lap_duration,
        tyre_age - avg(tyre_age)
            over (partition by session_key, driver_number, stint_number) as x,
        fuel_corrected_duration - avg(fuel_corrected_duration)
            over (partition by session_key, driver_number, stint_number) as y_corrected,
        lap_duration - avg(lap_duration)
            over (partition by session_key, driver_number, stint_number) as y_raw
    from clean
),

fits as (
    select
        session_key,
        circuit_short_name,
        session_name,
        compound,
        count(*) as n_clean_laps,
        count(distinct driver_number * 1000 + stint_number) as n_stints,
        count(distinct tyre_age) as n_tyre_ages,
        sum(x * y_corrected) / nullif(sum(x * x), 0) as slope_s_per_lap,
        sum(x * y_raw) / nullif(sum(x * x), 0) as slope_uncorrected,
        covar_samp(fuel_corrected_duration, tyre_age) / nullif(var_samp(tyre_age), 0)
            as slope_pooled_s_per_lap
    from centred
    group by session_key, circuit_short_name, session_name, compound
),

censoring as (
    select
        session_key, compound,
        avg(case when ended_by_pit then 1.0 else 0.0 end) as censored_stint_share
    from {{ ref('fct_stints') }}
    group by session_key, compound
)

select
    f.session_key,
    f.circuit_short_name,
    f.session_name,
    f.compound,
    f.n_clean_laps,
    f.n_stints,
    case when f.n_clean_laps >= {{ var('min_laps_for_slope') }} and f.n_tyre_ages >= 3
        then f.slope_s_per_lap end as slope_s_per_lap,
    case when f.n_clean_laps >= {{ var('min_laps_for_slope') }} and f.n_tyre_ages >= 3
        then f.slope_uncorrected end as slope_uncorrected,
    case when f.n_clean_laps >= {{ var('min_laps_for_slope') }} and f.n_tyre_ages >= 3
        then f.slope_pooled_s_per_lap end as slope_pooled_s_per_lap,
    c.censored_stint_share
from fits as f
left join censoring as c
    on f.session_key = c.session_key and f.compound = c.compound
