"""Optional :class:`SecretBackend` implementations.

Each submodule imports its own SDK lazily so they're safe to reference even
without the extras installed. The actual class is only importable when
``pip install nagara[<extra>]`` has pulled in the dependency.
"""
