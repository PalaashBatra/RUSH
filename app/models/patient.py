from typing import Optional
from pydantic import BaseModel, Field


class Patient(BaseModel):
    """A patient being referred from a rural clinic."""
    clinical_notes: str = Field(..., description="Unstructured notes from the referring doctor")
    home_clinic_zip: str = Field(..., description="Postal code of the referring clinic")

    # Filled in by triage
    urgency_score: Optional[int] = Field(None, ge=1, le=10, description="Medical urgency (1=low, 10=high)")
    primary_specialty_required: Optional[str] = Field(None, description="Cardiology, Neurology, etc.")
    key_symptoms: list[str] = Field(default_factory=list)
    acute_risks: list[str] = Field(default_factory=list)
    current_medications: list[str] = Field(default_factory=list)

    class Config:
        json_schema_extra = {
            "example": {
                "clinical_notes": "55yo male, crushing chest pain, ST elevation V1-V4, troponin elevated.",
                "home_clinic_zip": "B1P 5E7",
            }
        }
