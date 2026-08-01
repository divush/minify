"""`ProfileService` adapter backed by `Repository`.

Only concrete adapter for now — there's no alternative profile *storage*
strategy to swap in, unlike the other ports in this codebase where multiple
implementations are expected. Still kept behind the `ProfileService`
protocol for consistency and so callers never depend on `Repository`
directly for profile logic.
"""

import uuid

from minify.models import ReaderProfile
from minify.storage import Repository

DEFAULT_LABEL = "General reader"
DEFAULT_BACKGROUND = (
    "No specific background assumed — explain concepts accessibly, "
    "defining specialized terms as they come up."
)
DEFAULT_INTENT = (
    "General understanding; reading for broad comprehension rather than a "
    "specific exam or task."
)


class DefaultProfileService:
    """`ProfileService` implementation. See `interface.py` for the contract."""

    def __init__(self, repository: Repository) -> None:
        self._repository = repository

    def get_default(self) -> ReaderProfile:
        existing = self._repository.get_default_reader_profile()
        if existing is not None:
            return existing

        default_profile = ReaderProfile(
            id=str(uuid.uuid4()),
            label=DEFAULT_LABEL,
            background=DEFAULT_BACKGROUND,
            intent=DEFAULT_INTENT,
            is_default=True,
        )
        self._repository.save_reader_profile(default_profile)
        return default_profile

    def create(self, background: str, intent: str, label: str | None = None) -> ReaderProfile:
        profile = ReaderProfile(
            id=str(uuid.uuid4()),
            label=label,
            background=background,
            intent=intent,
            is_default=False,
        )
        self._repository.save_reader_profile(profile)
        return profile

    def get(self, profile_id: str) -> ReaderProfile | None:
        return self._repository.get_reader_profile(profile_id)

    def update(
        self, profile_id: str, background: str, intent: str, label: str | None = None
    ) -> ReaderProfile:
        existing = self._repository.get_reader_profile(profile_id)
        if existing is None:
            raise ValueError(f"Reader profile {profile_id} not found")

        updated = existing.model_copy(update={"background": background, "intent": intent, "label": label})
        # save_reader_profile merges on id, so this updates the existing row rather than
        # inserting a duplicate.
        self._repository.save_reader_profile(updated)
        return updated
