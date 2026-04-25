from __future__ import annotations

import gzip
import json
from typing import Any

from fastapi.encoders import jsonable_encoder
from starlette.responses import Response


def gzip_json_response(data: Any, *, level: int = 6, status_code: int = 200) -> Response:
    """Return a pre-compressed JSON response. Faster than relying on
    starlette's GZipMiddleware for endpoints with known-large payloads
    because we skip the streaming dance and the encoded body is built
    once."""
    body = json.dumps(jsonable_encoder(data), separators=(",", ":")).encode("utf-8")
    compressed = gzip.compress(body, compresslevel=level)
    return Response(
        content=compressed,
        status_code=status_code,
        media_type="application/json",
        headers={
            "Content-Encoding": "gzip",
            "Content-Length": str(len(compressed)),
            "Vary": "Accept-Encoding",
        },
    )
