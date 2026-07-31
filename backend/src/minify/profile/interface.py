"""The reader profile port.

Wraps the `ReaderProfile` schema (M1) with the actual business logic of
"what profile does a book get processed under" — in particular, provisioning
a sensible default the first time one's needed, which M1 deliberately left
out of scope (schema only, no default-provisioning behavior).
"""

from typing import Protocol

from minify.models import ReaderProfile


class ProfileService(Protocol):
    """Reader profile lookups and creation, backed by `Repository`."""

    def get_default(self) -> ReaderProfile:
        """Returns the default reader profile, creating and persisting one
        on first use if none exists yet."""
        ...

    def create(self, background: str, intent: str, label: str | None = None) -> ReaderProfile: ...

    def get(self, profile_id: str) -> ReaderProfile | None: ...
