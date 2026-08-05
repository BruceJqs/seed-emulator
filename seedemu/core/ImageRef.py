from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ImageRef:
    """Compiler-neutral reference to an OCI/Docker base image.

    ``repository`` may include a registry and port. Exactly one of ``tag`` or
    ``digest`` must be supplied. ``platform`` is optional; when present, a node
    may register one image reference per target platform.
    """

    repository: str
    tag: Optional[str] = None
    digest: Optional[str] = None
    platform: Optional[str] = None

    def __post_init__(self):
        if not isinstance(self.repository, str) or not self.repository.strip():
            raise ValueError("image repository must be a non-empty string")
        if self.repository != self.repository.strip():
            raise ValueError("image repository must not contain surrounding whitespace")
        if "@" in self.repository:
            raise ValueError("put the image digest in the digest field")
        if (self.tag is None) == (self.digest is None):
            raise ValueError("exactly one of image tag or digest must be set")
        if self.tag is not None and (
            not isinstance(self.tag, str)
            or not self.tag
            or self.tag != self.tag.strip()
        ):
            raise ValueError("image tag must be a non-empty string without surrounding whitespace")
        if self.digest is not None and (
            not isinstance(self.digest, str)
            or not self.digest
            or self.digest != self.digest.strip()
        ):
            raise ValueError("image digest must be a non-empty string without surrounding whitespace")
        if self.platform is not None and (
            not isinstance(self.platform, str)
            or not self.platform
            or self.platform != self.platform.strip()
        ):
            raise ValueError("image platform must be a non-empty string without surrounding whitespace")

    @classmethod
    def parse(cls, reference: str, platform: Optional[str] = None) -> "ImageRef":
        """Parse a familiar image reference, using ``latest`` when untagged."""

        if not isinstance(reference, str) or not reference.strip():
            raise ValueError("image reference must be a non-empty string")
        if reference != reference.strip():
            raise ValueError("image reference must not contain surrounding whitespace")

        if "@" in reference:
            repository, digest = reference.rsplit("@", 1)
            if ":" in repository.rsplit("/", 1)[-1]:
                raise ValueError("references containing both a tag and digest are not supported")
            return cls(repository=repository, digest=digest, platform=platform)

        last_component = reference.rsplit("/", 1)[-1]
        if ":" in last_component:
            repository, tag = reference.rsplit(":", 1)
            return cls(repository=repository, tag=tag, platform=platform)

        return cls(repository=reference, tag="latest", platform=platform)

    def __str__(self) -> str:
        if self.digest is not None:
            return f"{self.repository}@{self.digest}"
        return f"{self.repository}:{self.tag}"
