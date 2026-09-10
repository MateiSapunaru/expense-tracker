import pytest

from app.database import Base, engine


@pytest.fixture(scope="session", autouse=True)
def reset_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
