"""IL2CPP support package."""

from dualforge.il2cpp.metadata import (
    MAGIC,
    MAX_SUPPORTED,
    MIN_SUPPORTED,
    MetadataError,
    MetadataInfo,
    dump_strings,
    iter_string_literals,
    parse_metadata,
    string_text,
)

__all__ = [
    "MAGIC",
    "MAX_SUPPORTED",
    "MIN_SUPPORTED",
    "MetadataError",
    "MetadataInfo",
    "dump_strings",
    "iter_string_literals",
    "parse_metadata",
    "string_text",
]