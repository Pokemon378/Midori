"""Farm ORM model."""

from datetime import datetime
from typing import TYPE_CHECKING, List

from sqlalchemy import DateTime, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.zone import Zone


class Farm(Base):
    """A farm containing one or more zones."""

    __tablename__ = "farms"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    location: Mapped[str] = mapped_column(String(200), nullable=False)
    area_acres: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    zones: Mapped[List["Zone"]] = relationship(
        back_populates="farm", cascade="all, delete-orphan"
    )
