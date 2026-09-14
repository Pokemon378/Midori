"""Crop ORM model."""

from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Date, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.zone import Zone


class Crop(Base):
    """Crop information assigned to a zone (one active crop per zone)."""

    __tablename__ = "crops"
    __table_args__ = ({"comment": "One active crop record per zone for the MVP"},)

    id: Mapped[int] = mapped_column(primary_key=True)
    zone_id: Mapped[int] = mapped_column(
        ForeignKey("zones.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    crop_name: Mapped[str] = mapped_column(String(120), nullable=False)
    crop_stage: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    sowing_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    zone: Mapped["Zone"] = relationship(back_populates="crop")
