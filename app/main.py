"""
RUSH: Referral Upkeep System for Healthcare - backend API.
Serves the dashboard (index.html) and the triage / routing endpoints it calls.
"""
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.models.hub import HealthcareHub
from app.models.patient import Patient
from app.models.referral import Referral
from app.services.routing_engine import RoutingEngine
from app.services.triage_service import TriageService

ROOT = Path(__file__).resolve().parent.parent  # project folder (index.html, SH.png)

triage_service = TriageService()
routing_engine = RoutingEngine()

app = FastAPI(
    title="RUSH: Referral Upkeep System for Healthcare",
    description="Triage and hospital routing for rural Nova Scotia referrals (demo, simulated hospital data)",
    version="1.0.0",
)

# run.py serves the UI on a different port than the API, so the browser needs CORS
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/", include_in_schema=False)
async def ui():
    """The dashboard."""
    return FileResponse(ROOT / "index.html", headers={"Cache-Control": "no-store"})


@app.get("/SH.png", include_in_schema=False)
async def logo():
    return FileResponse(ROOT / "SH.png")


@app.get("/health")
async def health_check():
    """Liveness check. The UI reads ai_triage_available; run.py reads routing_engine."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "system": {
            "hubs_registered": len(routing_engine.get_all_hubs()),
            "ai_triage_available": not triage_service.mock_mode,
            "ai_model": None if triage_service.mock_mode else triage_service.model,
            "routing_engine": "operational",
        },
    }


@app.post("/triage", response_model=Patient)
async def triage_patient(patient: Patient):
    """Read the clinical notes and fill in urgency (1-10), specialty, symptoms, risks and medications."""
    try:
        return await triage_service.analyze_clinical_notes(patient)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"AI triage failed: {e}")


@app.post("/refer", response_model=Referral)
async def create_referral(patient: Patient, hub_id: Optional[str] = None):
    """
    Route a patient to a hospital and return the referral.

    Triage runs first if the patient isn't already triaged. RUSH picks the best hub;
    pass ?hub_id=<HUB_ID> to send it somewhere else instead (RUSH's pick is kept on the
    referral as suggested_hub_*). Referrals are not stored.
    """
    try:
        if not patient.urgency_score or not patient.primary_specialty_required:
            patient = await triage_service.analyze_clinical_notes(patient)

        specialty = patient.primary_specialty_required
        urgency = patient.urgency_score

        try:
            suggested, specialist = routing_engine.find_optimal_hub(patient)
        except ValueError:
            if not hub_id:  # no override to fall back on
                raise
            suggested, specialist = None, None

        hub = suggested
        if hub_id and (suggested is None or hub_id != suggested.hub_id):
            hub = routing_engine.get_hub_by_id(hub_id)
            if not hub:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Hub {hub_id} not found")
            specialist = routing_engine._select_specialist(hub, specialty, urgency)

        return Referral(
            referral_id=f"REF_{uuid.uuid4().hex[:8].upper()}",
            referring_clinic_zip=patient.home_clinic_zip,
            target_hub_id=hub.hub_id,
            target_hub_name=hub.name,
            assigned_specialist_id=specialist.id if specialist else None,
            urgency_score=urgency,
            required_specialty=specialty,
            distance_km=hub.distance_to_zip(patient.home_clinic_zip),
            estimated_wait_days=routing_engine._estimate_wait_days(hub, specialist, urgency),
            manual_override=hub is not suggested,
            suggested_hub_id=suggested.hub_id if suggested else None,
            suggested_hub_name=suggested.name if suggested else None,
        )

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Referral creation failed: {e}")


@app.get("/hubs", response_model=list[HealthcareHub])
async def list_hubs():
    """All hospitals with their current (simulated) capacity and specialists."""
    return routing_engine.get_all_hubs()


@app.post("/simulate/update-capacity")
async def simulate_capacity_update(hub_id: str, occupied_beds: int, queue_length: int):
    """Demo control: set a hospital's occupied beds and waiting list (the 'make a hospital busy' button)."""
    if not routing_engine.update_hub_capacity(hub_id, occupied_beds, queue_length):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Hub {hub_id} not found")
    return {"hub_id": hub_id, "occupied_beds": occupied_beds, "queue_length": queue_length}
