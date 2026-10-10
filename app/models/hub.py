from typing import Optional, List
from pydantic import BaseModel, Field
from geopy.distance import geodesic

class Specialist(BaseModel):
    """A specialist doctor at a healthcare hub."""
    id: str
    name: str
    specialty: str  # e.g., "Cardiology", "Neurology"
    available_slots: int = Field(default=5, ge=0)
    current_wait_days: int = Field(default=7, ge=0)


class HealthcareHub(BaseModel):
    """A hospital that can accept referrals. All capacity numbers are simulated."""
    hub_id: str = Field(..., description="Unique hub identifier")
    name: str
    postal_code: str  # For distance calculation
    specialties: List[str] = Field(..., description="List of specialties available at this hub")

    # Current capacity metrics (simulated - in real app this would come from an API)
    total_beds: int
    occupied_beds: int
    referral_queue_length: int = Field(default=0, ge=0)

    # Lat/Long coordinates (approximate, based on postal code)
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    # Specialists at this hub
    specialists: List[Specialist] = Field(default_factory=list)


    class Config:
        json_schema_extra = {
            "example": {
                "hub_id": "HAL_QEII",
                "name": "QEII Health Sciences Centre",
                "postal_code": "B3H 2Y9",  # Halifax
                "specialties": ["Cardiology", "Neurology", "Oncology", "Orthopedics"],
                "total_beds": 1000,
                "occupied_beds": 850,
                "referral_queue_length": 42,
                "latitude": 44.6488,
                "longitude": -63.5752,
                "specialists": [
                    {"id": "SP_001", "name": "Dr. Smith", "specialty": "Cardiology", "available_slots": 3, "current_wait_days": 5},
                    {"id": "SP_002", "name": "Dr. Jones", "specialty": "Cardiology", "available_slots": 0, "current_wait_days": 14}
                ]
            }
        }

    @property
    def bed_occupancy_rate(self) -> float:
        """Calculate current bed occupancy as a percentage."""
        if self.total_beds == 0:
            return 0.0
        return (self.occupied_beds / self.total_beds) * 100

    @property
    def capacity_score(self) -> float:
        """
        Calculate a normalized capacity score (0-1) where:
        - 1.0 = lots of capacity (low occupancy, short queue)
        - 0.0 = full (high occupancy, long queue)
        """
        # Simple heuristic: average of bed availability and queue length
        bed_availability = 1.0 - (self.bed_occupancy_rate / 100)
        queue_availability = max(0, 1.0 - (self.referral_queue_length / 100))  # Normalize to 100

        # Weight bed availability more heavily for urgent cases
        return (bed_availability * 0.7) + (queue_availability * 0.3)

    def get_available_specialists(self, specialty: str) -> List[Specialist]:
        """Return specialists of the given specialty who have available slots."""
        return [
            s for s in self.specialists
            if s.specialty.lower() == specialty.lower() and s.available_slots > 0
        ]

    def distance_to_zip(self, target_zip: str) -> float:
        """
        Distance in km from this hub to a clinic postal code.
        Only the postal codes below are known; anything else is assumed to be 100 km away.
        """
        # Simplified mapping of Nova Scotia postal codes to coordinates
        zip_to_coords = {
            "B1P 5E7": (46.1368, -60.1942),  # Sydney
            "B3H 2Y9": (44.6488, -63.5752),  # Halifax
            "B2N 1L5": (45.3655, -63.2924),  # Truro
            "B1S 1A1": (45.9427, -60.0203),  # Port Hawkesbury
            "B4N 1V5": (44.9849, -64.1293),  # Kentville
            "B0W 2M0": (44.3386, -64.3835),  # Bridgewater
            "B0N 1X0": (43.5000, -65.8000),  # Yarmouth
            "B0V 1N0": (45.6000, -64.8000),  # Amherst
            "B2H 1A1": (45.6000, -62.7000),  # New Glasgow
            "B2N 0A1": (45.6000, -62.1000),  # Antigonish
            "B1M 1A1": (46.0000, -60.5000),  # Glace Bay
            "B0J 1S0": (44.3000, -64.7000),  # Lunenburg
            "E2L 4L2": (45.3040, -66.0870),  # Saint John NB (approximate)
        }

        target_coords = zip_to_coords.get(target_zip)
        hub_coords = zip_to_coords.get(self.postal_code)

        if not target_coords or not hub_coords:
            # Default distance if coordinates not found
            return 100.0

        return geodesic(hub_coords, target_coords).km
