"""
Routing Engine
The core algorithm that matches patients to optimal healthcare hubs based on:
1. Medical urgency
2. Distance
3. Hub capacity
4. Specialist availability
"""
from typing import List, Optional, Tuple, Dict
from datetime import datetime

from app.models.patient import Patient
from app.models.hub import HealthcareHub, Specialist
from app.models.referral import Referral


class RoutingEngine:
    """
    Constraint-based routing engine for patient referrals.

    The algorithm prioritizes factors differently based on urgency:
    - HIGH urgency (8-10): Specialist availability > distance
    - MEDIUM urgency (4-7): Capacity score > distance
    - LOW urgency (1-3): Distance > capacity score
    """

    def __init__(self):
        # Initialize with mock Nova Scotia hubs data
        self.available_hubs = self._load_mock_hubs()

    def _load_mock_hubs(self) -> Dict[str, HealthcareHub]:
        """Load mock healthcare hubs for Nova Scotia."""
        from app.models.hub import HealthcareHub, Specialist

        # Realistic Nova Scotia healthcare hubs
        hubs = {
            "HAL_QEII": HealthcareHub(
                hub_id="HAL_QEII",
                name="QEII Health Sciences Centre",
                postal_code="B3H 2Y9",
                specialties=["Cardiology", "Neurology", "Oncology", "Orthopedics", "General Surgery"],
                total_beds=1000,
                occupied_beds=850,
                referral_queue_length=42,
                latitude=44.6488,
                longitude=-63.5752,
                specialists=[
                    Specialist(id="SP_001", name="Dr. Smith", specialty="Cardiology", available_slots=3, current_wait_days=5),
                    Specialist(id="SP_002", name="Dr. Jones", specialty="Cardiology", available_slots=0, current_wait_days=14),
                    Specialist(id="SP_003", name="Dr. Wilson", specialty="Neurology", available_slots=2, current_wait_days=7),
                ]
            ),
            "TRU_COLCH": HealthcareHub(
                hub_id="TRU_COLCH",
                name="Colchester East Hants Health Centre",
                postal_code="B2N 1L5",
                specialties=["Cardiology", "Orthopedics", "General Medicine"],
                total_beds=300,
                occupied_beds=220,
                referral_queue_length=18,
                latitude=45.3655,
                longitude=-63.2924,
                specialists=[
                    Specialist(id="SP_004", name="Dr. Brown", specialty="Cardiology", available_slots=1, current_wait_days=10),
                    Specialist(id="SP_005", name="Dr. Taylor", specialty="Orthopedics", available_slots=2, current_wait_days=8),
                ]
            ),
            "CB_REG": HealthcareHub(
                hub_id="CB_REG",
                name="Cape Breton Regional Hospital",
                postal_code="B1P 5E7",
                specialties=["Cardiology", "General Surgery", "Emergency Medicine"],
                total_beds=400,
                occupied_beds=320,
                referral_queue_length=25,
                latitude=46.1368,
                longitude=-60.1942,
                specialists=[
                    Specialist(id="SP_006", name="Dr. MacDonald", specialty="Cardiology", available_slots=0, current_wait_days=21),
                    Specialist(id="SP_007", name="Dr. Campbell", specialty="General Surgery", available_slots=1, current_wait_days=12),
                ]
            ),
            "VALLEY_REG": HealthcareHub(
                hub_id="VALLEY_REG",
                name="Valley Regional Hospital",
                postal_code="B4N 1V5",
                specialties=["General Medicine", "Orthopedics", "Maternity"],
                total_beds=200,
                occupied_beds=150,
                referral_queue_length=15,
                latitude=44.9849,
                longitude=-64.1293,
                specialists=[
                    Specialist(id="SP_008", name="Dr. Miller", specialty="Orthopedics", available_slots=3, current_wait_days=6),
                ]
            ),
            "SW_REG": HealthcareHub(
                hub_id="SW_REG",
                name="South Shore Regional Hospital",
                postal_code="B0W 2M0",
                specialties=["General Medicine", "Emergency Medicine"],
                total_beds=180,
                occupied_beds=140,
                referral_queue_length=12,
                latitude=44.3386,
                longitude=-64.3835,
                specialists=[
                    Specialist(id="SP_009", name="Dr. White", specialty="General Medicine", available_slots=2, current_wait_days=4),
                ]
            ),
            "YAR_REG": HealthcareHub(
                hub_id="YAR_REG",
                name="Yarmouth Regional Memorial",
                postal_code="B0N 1X0",
                specialties=["General Medicine", "Emergency Medicine", "Orthopedics"],
                total_beds=150,
                occupied_beds=110,
                referral_queue_length=10,
                latitude=43.5000,
                longitude=-65.8000,
                specialists=[
                    Specialist(id="SP_010", name="Dr. Moore", specialty="General Medicine", available_slots=2, current_wait_days=3),
                ]
            ),
            "AMH_REG": HealthcareHub(
                hub_id="AMH_REG",
                name="Amherst Hospital",
                postal_code="B0V 1N0",
                specialties=["General Medicine", "Emergency Medicine"],
                total_beds=120,
                occupied_beds=80,
                referral_queue_length=8,
                latitude=45.6000,
                longitude=-64.8000,
                specialists=[
                    Specialist(id="SP_011", name="Dr. Green", specialty="Emergency Medicine", available_slots=1, current_wait_days=2),
                ]
            ),
            "GLW_REG": HealthcareHub(
                hub_id="GLW_REG",
                name="North Nova Scotia Health Centre",
                postal_code="B2H 1A1",
                specialties=["General Medicine", "Cardiology"],
                total_beds=220,
                occupied_beds=170,
                referral_queue_length=20,
                latitude=45.6000,
                longitude=-62.7000,
                specialists=[
                    Specialist(id="SP_012", name="Dr. Lee", specialty="Cardiology", available_slots=1, current_wait_days=12),
                ]
            ),
            "ANT_REG": HealthcareHub(
                hub_id="ANT_REG",
                name="Antigonish Memorial",
                postal_code="B2N 0A1",
                specialties=["General Medicine", "Orthopedics"],
                total_beds=130,
                occupied_beds=90,
                referral_queue_length=12,
                latitude=45.6000,
                longitude=-62.1000,
                specialists=[
                    Specialist(id="SP_013", name="Dr. King", specialty="Orthopedics", available_slots=2, current_wait_days=7),
                ]
            ),
        }
        return hubs

    def find_optimal_hub(self, patient: Patient) -> Tuple[Optional[HealthcareHub], Optional[Specialist], float, str]:
        """
        Find the optimal healthcare hub for a patient based on urgency and constraints.

        Returns:
            Tuple of (hub, specialist, routing_score, routing_notes)
            routing_score is 0-1 where 1.0 is the best possible match.
        """
        if not patient.urgency_score or not patient.primary_specialty_required:
            raise ValueError("Patient must have urgency_score and primary_specialty_required for routing")

        urgency = patient.urgency_score
        required_specialty = patient.primary_specialty_required

        # Step 1: Filter hubs that offer the required specialty
        eligible_hubs = []
        for hub in self.available_hubs.values():
            if required_specialty in hub.specialties:
                eligible_hubs.append(hub)

        if not eligible_hubs:
            raise ValueError(f"No hubs found offering specialty: {required_specialty}")

        # Step 2: Calculate scores for each eligible hub
        hub_scores = []
        for hub in eligible_hubs:
            score, notes = self._calculate_hub_score(hub, patient, urgency, required_specialty)
            hub_scores.append((hub, score, notes))

        # Step 3: Sort by score (highest first)
        hub_scores.sort(key=lambda x: x[1], reverse=True)

        # Step 4: Select best hub and find available specialist
        best_hub, best_score, best_notes = hub_scores[0]
        best_specialist = self._select_specialist(best_hub, required_specialty, urgency)

        # Calculate estimated wait days
        wait_days = self._estimate_wait_days(best_hub, best_specialist, urgency)

        return best_hub, best_specialist, best_score, best_notes

    def _calculate_hub_score(self, hub: HealthcareHub, patient: Patient,
                           urgency: int, specialty: str) -> Tuple[float, str]:
        """
        Calculate a routing score (0-1) for this hub for this patient.

        The weighting changes based on urgency:
        - High urgency (8-10): Specialist availability weighted 70%, distance 10%, capacity 20%
        - Medium urgency (4-7): Capacity weighted 50%, distance 30%, specialist 20%
        - Low urgency (1-3): Distance weighted 60%, capacity 30%, specialist 10%
        """
        # Get base metrics
        if patient.latitude is not None and patient.longitude is not None:
            distance = hub.distance_to_coords(patient.latitude, patient.longitude)
        else:
            distance = hub.distance_to_zip(patient.home_clinic_zip)

        capacity_score = hub.capacity_score
        specialist_availability = len(hub.get_available_specialists(specialty))

        # Normalize distance (0-1, where 1 is closest)
        # Max distance in NS is ~400km, normalize to that
        max_distance_ns = 400.0
        distance_score = max(0, 1.0 - (distance / max_distance_ns))

        # Normalize specialist availability (0-1)
        # More available specialists = better score
        specialist_score = min(1.0, specialist_availability / 3.0)

        # Apply urgency-based weighting
        if urgency >= 8:  # High urgency
            weights = {"specialist": 0.7, "capacity": 0.2, "distance": 0.1}
            explanation = "High urgency - prioritized specialist availability"
        elif urgency >= 4:  # Medium urgency
            weights = {"capacity": 0.5, "distance": 0.3, "specialist": 0.2}
            explanation = "Medium urgency - balanced capacity and distance"
        else:  # Low urgency
            weights = {"distance": 0.6, "capacity": 0.3, "specialist": 0.1}
            explanation = "Low urgency - prioritized proximity to patient"

        # Calculate weighted score
        weighted_score = (
            (specialist_score * weights["specialist"]) +
            (capacity_score * weights["capacity"]) +
            (distance_score * weights["distance"])
        )

        # Generate routing notes
        notes = f"{explanation}. Hub: {hub.name}, Distance: {distance:.1f}km, "
        notes += f"Capacity: {hub.capacity_score:.2f}, Available {specialty} specialists: {specialist_availability}"

        return weighted_score, notes

    def _select_specialist(self, hub: HealthcareHub, specialty: str, urgency: int) -> Optional[Specialist]:
        """Select the best available specialist at the hub."""
        available = hub.get_available_specialists(specialty)

        if not available:
            return None

        # For high urgency, prioritize specialists with shorter wait times
        if urgency >= 7:
            available.sort(key=lambda s: s.current_wait_days)

        return available[0]

    def _estimate_wait_days(self, hub: HealthcareHub, specialist: Optional[Specialist], urgency: int) -> int:
        """Estimate wait days until appointment."""
        if specialist:
            base_wait = specialist.current_wait_days
        else:
            # If no specialist available, use hub's general wait time
            base_wait = max(7, hub.referral_queue_length // 3)

        # Adjust based on urgency
        if urgency >= 9:
            return max(1, base_wait // 4)  # Emergency cases get priority
        elif urgency >= 7:
            return max(2, base_wait // 2)  # Urgent cases get expedited
        else:
            return base_wait

    def get_all_hubs(self) -> List[HealthcareHub]:
        """Return list of all available hubs."""
        return list(self.available_hubs.values())

    def get_hub_by_id(self, hub_id: str) -> Optional[HealthcareHub]:
        """Get a specific hub by ID."""
        return self.available_hubs.get(hub_id)

    def update_hub_capacity(self, hub_id: str, occupied_beds: int, queue_length: int) -> bool:
        """Update a hub's capacity metrics (simulated for demo)."""
        if hub_id in self.available_hubs:
            hub = self.available_hubs[hub_id]
            hub.occupied_beds = occupied_beds
            hub.referral_queue_length = queue_length
            return True
        return False