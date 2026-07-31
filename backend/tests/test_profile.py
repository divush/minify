import pytest
from sqlalchemy import create_engine

from minify.profile.service import DefaultProfileService
from minify.storage.orm import Base
from minify.storage.sqlite_adapter import SqliteRepository


@pytest.fixture
def service(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    return DefaultProfileService(SqliteRepository(engine))


def test_get_default_creates_one_on_first_call(service):
    profile = service.get_default()

    assert profile.is_default is True
    assert profile.label == "General reader"
    assert service.get(profile.id) == profile


def test_get_default_is_idempotent(service):
    first = service.get_default()
    second = service.get_default()

    assert first == second


def test_create_persists_a_custom_profile(service):
    profile = service.create(background="PhD in biology", intent="Exam prep", label="Expert")

    assert profile.is_default is False
    fetched = service.get(profile.id)
    assert fetched == profile
    assert fetched.background == "PhD in biology"
