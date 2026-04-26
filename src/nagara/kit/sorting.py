"""Typed sort criteria for list endpoints.

Convention: clients send ``?sort=foo,-bar`` — ``foo`` ascending, ``-bar``
descending. Each domain defines a ``SortProperty(StrEnum)`` listing the
fields it allows; :func:`parse_sorting` turns the raw query string into a
list of ``(property, descending)`` tuples and raises :class:`ValidationFailed`
on unknown property names.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum

from nagara.exceptions import ValidationFailed

type Sorting[PE: StrEnum] = tuple[PE, bool]


def parse_sorting[PE: StrEnum](
    raw: str | Sequence[str] | None,
    enum: type[PE],
    *,
    default: Sequence[str] = (),
) -> list[Sorting[PE]]:
    """Parse the ``?sort=`` query value into typed sort criteria.

    Accepts a comma-separated string (`"foo,-bar"`) or a pre-split
    sequence. Raises :class:`ValidationFailed` with a per-criterion
    structured error so the frontend can highlight the bad value.
    """
    if raw is None or raw == "" or raw == []:
        items: Sequence[str] = default
    elif isinstance(raw, str):
        items = [s.strip() for s in raw.split(",") if s.strip()]
    else:
        items = raw

    parsed: list[Sorting[PE]] = []
    errors = []
    for criterion in items:
        desc = criterion.startswith("-")
        name = criterion[1:] if desc else criterion
        try:
            parsed.append((enum(name), desc))
        except ValueError:
            errors.append(
                {
                    "loc": ("query", "sort"),
                    "msg": f"unknown sort field: {name!r}",
                    "type": "enum",
                    "input": criterion,
                }
            )
    if errors:
        raise ValidationFailed("invalid sort criteria", errors=errors)
    return parsed
