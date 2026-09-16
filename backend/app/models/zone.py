"""Zone ORM model."""

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.crop import Crop
    from app.models.farm import Farm
    from app.models.image_metadata import ImageMetadata
    from app.models.risk_assessment import RiskAssessment
    from app.models.sensor_reading import SensorReading


class Zone(Base):
    """A zone within a farm; holds at most one active crop record."""

    __tablename__ = "zones"

    id: Mapped[int] = mapped_column(primary_key=True)
    farm_id: Mapped[int] = mapped_column(
        ForeignKey("farms.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    farm: Mapped["Farm"] = relationship(back_populates="zones")
    crop: Mapped[Optional["Crop"]] = relationship(
        back_populates="zone", uselist=False, cascade="all, delete-orphan"
    )
    sensor_readings: Mapped[List["SensorReading"]] = relationship(
        back_populates="zone", cascade="all, delete-orphan"
    )
    images: Mapped[List["ImageMetadata"]] = relationship(
        back_populates="zone", cascade="all, delete-orphan"
    )
    risk_assessments: Mapped[List["RiskAssessment"]] = relationship(
        back_populates="zone", cascade="all, delete-orphan"
    )
