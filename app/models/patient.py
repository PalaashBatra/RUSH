from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class Patient(BaseModel):
    """A patient requiring referral from a rural clinic."""
    patient_id: str = Field(..., description="Unique patient identifier")
    clinical_notes: str = Field(..., description="Unstructured notes from the referring doctor")
    home_clinic_zip: str = Field(..., description="Postal code of the home clinic")

    # Extracted by AI during triage
    urgency_score: Optional[int] = Field(None, ge=1, le=10, description="Medical urgency (1=low, 10=high)")
    primary_specialty_required: Optional[str] = Field(None, description="Cardiology, Neurology, etc.")

    # Additional metadata from AI extraction
    key_symptoms: Optional[list[str]] = Field(default_factory=list)
    acute_risks: Optional[list[str]] = Field(default_factory=list)
    current_medications: Optional[list[str]] = Field(default_factory=list)
    # Clinic coordinates (resolved via geocoding)
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    created_at: datetime = Field(default_factory=datetime.now)

    class Config:
        json_schema_extra = {
            "example": {
                "patient_id": "PAT_NS_001",
                "clinical_notes": "55yo male with 2 weeks of crushing chest pain radiating to jaw. EKG shows ST elevation in V1-V4. Troponin elevated.",
                "home_clinic_zip": "B1P 5E7",  # Cape Breton area
                "urgency_score": 9,
                "primary_specialty_required": "Cardiology",
                "key_symptoms": ["chest pain", "ST elevation", "elevated troponin"],
                "acute_risks": ["STEMI", "myocardial infarction"],
                "current_medications": ["aspirin", "nitroglycerin"]
            }
        }