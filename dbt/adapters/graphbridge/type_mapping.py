from typing import Any, Dict, List
from datetime import date, datetime, time, timedelta
from neo4j.time import Date, DateTime, Time, Duration
from neo4j.spatial import Point


def python_to_neo4j(value: Any, graph_type: str = "") -> Any:
    if value is None:
        return None
    if isinstance(value, (bool, int, float, str, list)):
        return value
    if isinstance(value, date) and not isinstance(value, datetime):
        return Date(value.year, value.month, value.day)
    if isinstance(value, datetime):
        return DateTime.from_native(value)
    if isinstance(value, time):
        return Time.from_native(value)
    if isinstance(value, timedelta):
        return Duration(seconds=value.total_seconds())
    if isinstance(value, dict):
        if "latitude" in value and "longitude" in value:
            return Point((value["longitude"], value["latitude"]))
        return value
    return str(value)


def row_to_neo4j_properties(
    row: Dict[str, Any],
    columns: Dict[str, Any],
    exclude_keys: List[str] = None,
) -> Dict[str, Any]:
    exclude = set(exclude_keys or [])
    result = {}
    for key, value in row.items():
        if key in exclude:
            continue
        if value is None:
            continue
        col = columns.get(key)
        if col:
            result[key] = python_to_neo4j(value, getattr(col, 'graph_type', ''))
        else:
            result[key] = python_to_neo4j(value)
    return result
