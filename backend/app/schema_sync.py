"""Добавляет недостающие колонки в уже созданную SQLite-базу.

create_all создаёт новые таблицы, но не меняет старые. Этот шаг нужен,
чтобы существующий файл codearena.db пережил расширение моделей.
"""

from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from .database import Base


def _default_sql(column) -> str:
    default = column.default
    if default is None or not getattr(default, "is_scalar", False):
        return ""
    value = default.arg
    if callable(value):
        return ""
    if isinstance(value, bool):
        return " DEFAULT 1" if value else " DEFAULT 0"
    if isinstance(value, (int, float)):
        return f" DEFAULT {value}"
    if isinstance(value, str):
        escaped = value.replace("'", "''")
        return f" DEFAULT '{escaped}'"
    return ""


def ensure_columns(engine: Engine) -> None:
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as connection:
        for table in Base.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue
            present = {item["name"] for item in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in present:
                    continue
                column_type = column.type.compile(dialect=engine.dialect)
                null_sql = "" if column.nullable else " NOT NULL"
                default_sql = _default_sql(column)
                if not column.nullable and not default_sql:
                    raise RuntimeError(f"Нельзя добавить обязательную колонку {table.name}.{column.name} без значения по умолчанию")
                connection.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN {column.name} {column_type}{null_sql}{default_sql}'))
