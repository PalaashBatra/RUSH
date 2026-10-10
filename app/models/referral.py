from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class Referral(BaseModel):
    """A referral sent from a rural clinic to a hospital."""
    referral_id: str
    referring_clinic_zip: str

    target_hub_id: str
    target_hub_name: str
    assigned_specialist_id: Optional[str] = None  # None = patient joins the hospital's waiting list

    urgency_score: int = Field(..., ge=1, le=10)
    required_specialty: str
    distance_km: float
    estimated_wait_days: int

    # Set when the clinician sends it somewhere other than RUSH's suggestion
    manual_override: bool = False
    suggested_hub_id: Optional[str] = None
    suggested_hub_name: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.now)
