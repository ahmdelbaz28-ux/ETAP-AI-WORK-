"""Typed identifier aliases.

These are validated identifiers used as ``id`` (request) and ``trace_id``
(progress / audit correlation). Using ``Annotated`` so pydantic can
apply the constraint automatically.

JSON-RPC 2.0 spec allows ``id`` to be Union[``string, number] | null``.
The ``RequestId`` type accepts both ``str`` and ``int``; the null case
is handled by making the field ``Optional[RequestId]``.
"""

from __future__ import annotations

try:
    from typing import Annotated, Optional, Union
except ImportError:
    from typing_extensions import Annotated

from pydantic import StringConstraints

ID_PATTERN = r"^[A-Za-z0-9_\-]{1,128}$"

# ``RequestId`` must be unique per session; ``TraceId`` may repeat.
# JSON-RPC 2.0 allows id to be string or int.
# JSON-RPC 2.0 allows id to be string or int. Only apply pattern constraints to strings.
from typing import Optional, Union

RequestId = Union[
    Annotated[str, StringConstraints(pattern=ID_PATTERN, min_length=1, max_length=128)],
    int,
]
TraceId = Annotated[str, StringConstraints(pattern=ID_PATTERN, min_length=1, max_length=128)]
