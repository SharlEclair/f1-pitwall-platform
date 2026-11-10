{#- Use the schema names in dbt_project.yml as-is (staging, intermediate, marts) instead of
    prefixing them with the target schema. -#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}

{#- dq_flags is a Snowflake ARRAY and a DuckDB LIST; these macros are the only place that differs. -#}
{% macro has_flag(column, code) -%}
    {{ return(adapter.dispatch('has_flag', 'f1_pitwall')(column, code)) }}
{%- endmacro %}

{% macro duckdb__has_flag(column, code) -%}
    list_contains({{ column }}, '{{ code }}')
{%- endmacro %}

{% macro snowflake__has_flag(column, code) -%}
    array_contains('{{ code }}'::variant, {{ column }})
{%- endmacro %}

{% macro no_flags(column) -%}
    {{ return(adapter.dispatch('no_flags', 'f1_pitwall')(column)) }}
{%- endmacro %}

{% macro duckdb__no_flags(column) -%}
    coalesce(len({{ column }}), 0) = 0
{%- endmacro %}

{% macro snowflake__no_flags(column) -%}
    coalesce(array_size({{ column }}), 0) = 0
{%- endmacro %}
