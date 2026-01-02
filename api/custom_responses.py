"""
Custom response classes for high-performance serialization.
"""
from typing import Any

import orjson # type: ignore
from fastapi.responses import JSONResponse # type: ignore


class ORJSONResponse(JSONResponse):
    """
    A custom response class that uses `orjson` for serialization.
    `orjson` is significantly faster than the standard `json` library
    and produces smaller output.
    """
    media_type = "application/json"

    def render(self, content: Any) -> bytes:
        return orjson.dumps(
            content, 
            option=orjson.OPT_NAIVE_UTC | orjson.OPT_SERIALIZE_NUMPY
        )
