"""
RUSH: Referral Upkeep System for Healthcare - Backend API
B2B AI SaaS for Nova Scotia Healthcare
"""
from fastapi import FastAPI, HTTPException, status, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uuid
from datetime import datetime

from app.models.patient import Patient
from app.models.referral import Referral, ReferralStatus
from app.models.hub import HealthcareHub
from app.services.triage_service import TriageService
from app.services.routing_engine import RoutingEngine

# Global service instances
triage_service = TriageService()
routing_engine = RoutingEngine()

# In-memory storage for demo (in production, use a database)
referral_store = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown."""
    # Startup
    print("RUSH backend starting...")
    yield
    # Shutdown
    print("RUSH backend shutting down...")

app = FastAPI(
    title="RUSH: Referral Upkeep System for Healthcare",
    description="AI-powered referral routing for Nova Scotia healthcare",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "service": "RUSH",
        "description": "AI-powered healthcare referral routing for Nova Scotia",
        "status": "operational",
        "timestamp": datetime.now().isoformat(),
        "endpoints": {
            "health": "/health",
            "triage": "POST /triage",
            "refer": "POST /refer",
            "hubs": "GET /hubs",
            "referral_status": "GET /referral/{referral_id}"
        }
    }

@app.get("/health")
async def health_check():
    """Health check with system status."""
    hub_count = len(routing_engine.get_all_hubs())
    active_referrals = len([r for r in referral_store.values() if r.status != ReferralStatus.COMPLETED])

    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "system": {
            "hubs_registered": hub_count,
            "active_referrals": active_referrals,
            "ai_triage_available": not triage_service.mock_mode,
            "routing_engine": "operational"
        }
    }

@app.post("/triage", response_model=Patient)
async def triage_patient(patient: Patient):
    """
    Analyze clinical notes and extract urgency/specialty using AI.

    This endpoint:
    1. Accepts patient clinical notes
    2. Uses Claude AI to extract medical urgency (1-10) and required specialty
    3. Returns enriched patient data
    """
    try:
        # Ensure patient has an ID
        if not patient.patient_id:
            patient.patient_id = f"PAT_{uuid.uuid4().hex[:8].upper()}"

        # Perform AI triage
        enriched_patient = await triage_service.analyze_clinical_notes(patient)

        return enriched_patient

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI triage failed: {str(e)}"
        )

@app.post("/refer", response_model=Referral)
async def create_referral(patient: Patient, background_tasks: BackgroundTasks):
    """
    Create a new referral and find the optimal healthcare hub.

    This endpoint orchestrates the full workflow:
    1. AI Triage (if not already done)
    2. Constraint-based routing to optimal hub
    3. Specialist assignment
    4. Referral creation with all metadata
    """
    try:
        # Step 1: Generate referral ID
        referral_id = f"REF_{uuid.uuid4().hex[:8].upper()}"

        # Step 2: Perform triage if needed
        if not patient.urgency_score or not patient.primary_specialty_required:
            patient = await triage_service.analyze_clinical_notes(patient)

        # Step 3: Find optimal hub using routing engine
        hub, specialist, routing_score, routing_notes = routing_engine.find_optimal_hub(patient)

        if not hub:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No suitable healthcare hub found for patient's needs"
            )

        # Step 4: Calculate wait days
        urgency = patient.urgency_score or 5
        wait_days = routing_engine._estimate_wait_days(hub, specialist, urgency)

        # Step 5: Create referral record
        referral = Referral(
            referral_id=referral_id,
            patient_id=patient.patient_id,
            referring_clinic_zip=patient.home_clinic_zip,
            urgency_score=patient.urgency_score,
            required_specialty=patient.primary_specialty_required,
            target_hub_id=hub.hub_id,
            target_hub_name=hub.name,
            assigned_specialist_id=specialist.id if specialist else None,
            distance_km=hub.distance_to_zip(patient.home_clinic_zip),
            estimated_wait_days=wait_days,
            routing_score=routing_score,
            routing_notes=routing_notes,
            status=ReferralStatus.ROUTED
        )

        # Step 6: Store referral
        referral_store[referral_id] = referral

        # Step 7: In production, we'd trigger notifications here
        # background_tasks.add_task(notify_hub, referral)
        # background_tasks.add_task(notify_clinic, referral)

        return referral

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Referral creation failed: {str(e)}"
        )

@app.get("/referral/{referral_id}", response_model=Referral)
async def get_referral_status(referral_id: str):
    """Get the status and details of a specific referral."""
    referral = referral_store.get(referral_id)

    if not referral:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Referral {referral_id} not found"
        )

    return referral

@app.get("/hubs", response_model=list[HealthcareHub])
async def list_hubs():
    """Get list of all healthcare hubs in Nova Scotia with current capacity."""
    return routing_engine.get_all_hubs()

@app.get("/hubs/{hub_id}", response_model=HealthcareHub)
async def get_hub_details(hub_id: str):
    """Get detailed information about a specific healthcare hub."""
    hub = routing_engine.get_hub_by_id(hub_id)

    if not hub:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Hub {hub_id} not found"
        )

    return hub

@app.post("/simulate/update-capacity")
async def simulate_capacity_update(hub_id: str, occupied_beds: int, queue_length: int):
    """
    Simulate capacity updates for demo purposes.
    In production, this would come from real hospital systems.
    """
    success = routing_engine.update_hub_capacity(hub_id, occupied_beds, queue_length)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Hub {hub_id} not found"
        )

    return {
        "message": "Capacity updated successfully",
        "hub_id": hub_id,
        "new_occupied_beds": occupied_beds,
        "new_queue_length": queue_length
    }

@app.get("/dashboard")
async def get_system_dashboard():
    """Get system-wide dashboard data."""
    hubs = routing_engine.get_all_hubs()

    # Calculate system metrics
    total_beds = sum(h.total_beds for h in hubs)
    occupied_beds = sum(h.occupied_beds for h in hubs)
    total_queue = sum(h.referral_queue_length for h in hubs)

    # Count referrals by status
    status_counts = {}
    for referral in referral_store.values():
        status_counts[referral.status] = status_counts.get(referral.status, 0) + 1

    return {
        "timestamp": datetime.now().isoformat(),
        "system_metrics": {
            "total_hubs": len(hubs),
            "total_beds": total_beds,
            "occupied_beds": occupied_beds,
            "bed_occupancy_rate": f"{(occupied_beds / total_beds * 100):.1f}%" if total_beds > 0 else "0%",
            "total_referrals_in_queue": total_queue,
            "total_referrals_processed": len(referral_store),
        },
        "referral_status": status_counts,
        "ai_system": {
            "triage_mode": "mock" if triage_service.mock_mode else "claude",
            "routing_algorithm": "constraint-based with urgency weighting"
        }
    }