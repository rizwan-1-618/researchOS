from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum

from sqlalchemy import Enum as SAEnum
from sqlalchemy import MetaData, event
from sqlalchemy.orm import DeclarativeBase

convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=convention)


@event.listens_for(Base, "before_update", propagate=True)
def touch_updated_at(_mapper, _connection, target) -> None:
    if hasattr(target, "updated_at"):
        target.updated_at = datetime.now(UTC)


def pg_enum(enum_cls: type[Enum], name: str) -> SAEnum:
    return SAEnum(
        enum_cls,
        name=name,
        native_enum=False,
        validate_strings=True,
        length=48,
        values_callable=lambda members: [member.value for member in members],
    )
