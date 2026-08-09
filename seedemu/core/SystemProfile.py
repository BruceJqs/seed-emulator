from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SystemProfile:
    """Compiler-neutral identifier for a node runtime system."""

    name: str

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("system profile name must be a non-empty string")
        if self.name != self.name.strip():
            raise ValueError("system profile name must not contain surrounding whitespace")

    @property
    def value(self) -> str:
        """Return the stable profile name."""
        return self.name

    def __str__(self) -> str:
        return self.name
