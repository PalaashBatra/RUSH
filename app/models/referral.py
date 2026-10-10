from datetime import datetime, timedelta
from typing import Optional
from pydantic import BaseModel, Field
from enum import Enum

class ReferralStatus(str, Enum):
    """Status of a patient referral through the system."""
    PENDING = "pending"  # Just created, awaiting triage
    TRIAGED = "triaged"  # AI has analyzed, urgency assigned
    ROUTED = "routed"    # Optimal hub selected
    ACCEPTED = "accepted"  # Hub has confirmed availability
    IN_TRANSIT = "in_transit"  # Patient en route to hub
    COMPLETED = "completed"  # Patient seen by specialist
    CANCELLED = "cancelled"

class Referral(BaseModel):
    """A referral request from a rural clinic to a specialist hub."""
    referral_id: str = Field(..., description="Unique referral identifier")
    patient_id: str = Field(..., description="ID of the patient being referred")

    # Source clinic information
    referring_clinic_zip: str = Field(..., description="Postal code of the rural clinic")
    referring_doctor: Optional[str] = None

    # Target hub information (assigned by routing engine)
    target_hub_id: Optional[str] = None
    target_hub_name: Optional[str] = None
    assigned_specialist_id: Optional[str] = None

    # Triage results from AI
    urgency_score: Optional[int] = Field(None, ge=1, le=10)
    required_specialty: Optional[str] = None

    # Routing metadata
    distance_km: Optional[float] = Field(None, description="Distance from clinic to hub")
    estimated_wait_days: Optional[int] = Field(None, description="Estimated days until specialist appointment")
    routing_score: Optional[float] = Field(None, description="Quality score of this routing decision (0-1)")

    # System state
    status: ReferralStatus = Field(default=ReferralStatus.PENDING)
    created_at: datetime = Field(default_factory=datetime.now)
    triaged_at: Optional[datetime] = None
    routed_at: Optional[datetime] = None
    estimated_arrival: Optional[datetime] = None

    # Logging and audit
    routing_notes: Optional[str] = None
    decline_reason: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "referral_id": "REF_NS_001",
                "patient_id": "PAT_NS_001",
                "referring_clinic_zip": "B1P 5E7",
                "referring_doctor": "Dr. MacDonald",
                "target_hub_id": "HAL_QEII",
                "target_hub_name": "QEII Health Sciences Centre",
                "assigned_specialist_id": "SP_001",
                "urgency_score": 9,
                "required_specialty": "Cardiology",
                "distance_km": 320.5,
                "estimated_wait_days": 5,
                "routing_score": 0.87,
                "status": "routed",
                "created_at": "2026-10-08T08:30:00Z",
                "triaged_at": "2026-10-08T08:32:15Z",
                "routed_at": "2026-10-08T08:35:45Z",
                "estimated_arrival": "2026-10-13T10:00:00Z",
                "routing_notes": "High urgency (9/10) → prioritized specialist availability over distance. QEII has immediate Cardiology slots despite distance."
            }
        }

    @property
    def is_urgent(self) -> bool:
        """Return True if this referral requires urgent attention."""
        return self.urgency_score is not None and self.urgency_score >= 7

    @property
    def estimated_appointment_date(self) -> Optional[datetime]:
        """Calculate the estimated appointment date based on wait days."""
        if not self.estimated_wait_days:
            return None
        return self.created_at + timedelta(days=self.estimated_wait_days)

    def complete_triage(self, urgency_score: int, specialty: str) -> None:
        """Update the referral with triage results."""
        self.urgency_score = urgency_score
        self.required_specialty = specialty
        self.status = ReferralStatus.TRIAGED
        self.triaged_at = datetime.now()

    def complete_routing(self, hub_id: str, hub_name: str, distance: float,
                        wait_days: int, routing_score: float, specialist_id: Optional[str] = None,
                        notes: Optional[str] = None) -> None:
        """Update the referral with routing results."""
        self.target_hub_id = hub_id
        self.target_hub_name = hub_name
        self.distance_km = distance
        self.estimated_wait_days = wait_days
        self.routing_score = routing_score
        self.assigned_specialist_id = specialist_id
        self.routing_notes = notes
        self.status = ReferralStatus.ROUTED
        self.routed_at = datetime.now()

        # Calculate estimated arrival if we have wait days
        if wait_days:
            self.estimated_arrival = datetime.now() + timedelta(days=wait_days)