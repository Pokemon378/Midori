"""SensorReading ORM model (software-generated observations for the MVP)."""

from datetime import datetime
from typing import TYPE_CHECKING, List

from sqlalchemy import DateTime, Float, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.zone import Zone


class SensorReading(Base):
    """One environmental/pest observation for a zone.

    Values are software-generated observations (Digital Farm Simulator in a
    later step), not physical hardware sensor values.
    """

    __tablename__ = "sensor_readings"

    id: Mapped[int] = mapped_column(primary_key=True)
    zone_id: Mapped[int] = mapped_column(
        ForeignKey("zones.id", ondelete="CASCADE"), nullable=False, index=True
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    temperature: Mapped[float] = mapped_column(Float, nullable=False)  # Celsius
    humidity: Mapped[float] = mapped_column(Float, nullable=False)  # % (0-100)
    rainfall: Mapped[float] = mapped_column(Float, nullable=False)  # mm, >= 0
    leaf_wetness: Mapped[float] = mapped_column(Float, nullable=False)  # 0-100
    soil_moisture: Mapped[float] = mapped_column(Float, nullable=False)  # 0-100
    pest_activity: Mapped[float] = mapped_column(Float, nullable=False)  # 0-100 index
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    zone: Mapped["Zone"] = relationship(back_populates="sensor_readings")
