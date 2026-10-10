"""
AI Triage Service
Transforms unstructured clinical notes into structured medical urgency scores and specialties.
"""
import json
import os
from typing import Dict, Any, Optional
import httpx
from dotenv import load_dotenv
from geopy.geocoders import Nominatim
from geopy.exc import GeopyError

from app.models.patient import Patient

load_dotenv()

class TriageService:
    """
    Service that uses Claude AI to analyze clinical notes and extract:
    1. Medical urgency score (1-10)
    2. Required specialty
    3. Key symptoms, risks, and medications
    """

    def __init__(self):
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        self.base_url = "https://api.anthropic.com/v1/messages"
        self.model = "claude-sonnet-5-5"
        self.geolocator = Nominatim(user_agent="rush-healthcare-triage")

        if not self.api_key:
            # For demo purposes, use a mock mode if no API key is set
            print("ANTHROPIC_API_KEY not found. Running in mock mode.")
            self.mock_mode = True
        else:
            self.mock_mode = False
            self.headers = {
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }

    async def analyze_clinical_notes(self, patient: Patient) -> Patient:
        """
        Analyze the patient's clinical notes and populate the structured fields.
        Also resolves the clinic's postal code to actual coordinates.

        Returns the same patient object with populated:
        - urgency_score
        - primary_specialty_required
        - key_symptoms
        - acute_risks
        - current_medications
        - latitude/longitude
        """
        # Resolve coordinates first
        try:
            location = self.geolocator.geocode(f"{patient.home_clinic_zip}, Nova Scotia, Canada")
            if location:
                patient.latitude = location.latitude
                patient.longitude = location.longitude
        except GeopyError as e:
            print(f"Geocoding error: {e}")

        if self.mock_mode:
            return self._mock_analysis(patient)

        # Construct the prompt for Claude
        system_prompt = """You are a medical triage AI assistant for Nova Scotia's RUSH (Referral Upkeep System for Healthcare) system.

        Your task is to analyze unstructured clinical notes from a rural doctor and extract:
        1. Medical urgency score (1-10 scale, where 10 is life-threatening emergency)
        2. Primary medical specialty required (e.g., "Cardiology", "Neurology", "Orthopedics")
        3. List of key symptoms mentioned
        4. List of acute risks identified
        5. List of current medications mentioned

        Be conservative with urgency scoring:
        - 9-10: Life-threatening emergency (STEMI, stroke, severe trauma)
        - 7-8: Urgent but not immediately life-threatening (unstable angina, appendicitis)
        - 4-6: Semi-urgent (persistent symptoms requiring timely specialist)
        - 1-3: Routine referral (chronic condition management)

        Return ONLY a valid JSON object with this exact structure:
        {
            "urgency_score": 7,
            "primary_specialty_required": "Cardiology",
            "key_symptoms": ["chest pain", "shortness of breath"],
            "acute_risks": ["unstable angina", "possible MI"],
            "current_medications": ["aspirin", "metoprolol"]
        }

        Do not include any explanations or additional text."""

        user_prompt = f"""Clinical Notes: {patient.clinical_notes}

        Patient Location: {patient.home_clinic_zip} (Nova Scotia postal code)"""

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.base_url,
                    headers=self.headers,
                    json={
                        "model": self.model,
                        "max_tokens": 500,
                        "system": system_prompt,
                        "messages": [{"role": "user", "content": user_prompt}]
                    }
                )

                if response.status_code != 200:
                    print(f"Claude API error: {response.status_code} - {response.text}")
                    return self._mock_analysis(patient)

                response_data = response.json()
                content = response_data.get("content", [{}])[0].get("text", "{}")

                # Parse the JSON response
                triage_data = json.loads(content)

                # Update the patient object with AI-extracted data
                patient.urgency_score = triage_data.get("urgency_score")
                patient.primary_specialty_required = triage_data.get("primary_specialty_required")
                patient.key_symptoms = triage_data.get("key_symptoms", [])
                patient.acute_risks = triage_data.get("acute_risks", [])
                patient.current_medications = triage_data.get("current_medications", [])

                return patient

        except Exception as e:
            print(f"Error during AI triage: {e}")
            return self._mock_analysis(patient)

    def _mock_analysis(self, patient: Patient) -> Patient:
        """
        Mock analysis for demo purposes when no API key is available.
        """
        # Simple rule-based mock analysis
        notes_lower = patient.clinical_notes.lower()

        # Determine urgency based on keywords
        if any(word in notes_lower for word in ["stemi", "stroke", "severe", "emergency", "critical"]):
            urgency = 9
        elif any(word in notes_lower for word in ["chest pain", "unstable", "urgent", "acute"]):
            urgency = 7
        elif any(word in notes_lower for word in ["persistent", "chronic", "routine"]):
            urgency = 4
        else:
            urgency = 3

        # Determine specialty based on keywords
        if any(word in notes_lower for word in ["chest", "heart", "cardiac", "ekg", "troponin"]):
            specialty = "Cardiology"
        elif any(word in notes_lower for word in ["headache", "stroke", "neuro", "seizure"]):
            specialty = "Neurology"
        elif any(word in notes_lower for word in ["fracture", "bone", "ortho", "joint"]):
            specialty = "Orthopedics"
        elif any(word in notes_lower for word in ["cancer", "onco", "tumor"]):
            specialty = "Oncology"
        else:
            specialty = "General Medicine"

        # Mock extracted data
        patient.urgency_score = urgency
        patient.primary_specialty_required = specialty
        patient.key_symptoms = ["mocked_symptom_1", "mocked_symptom_2"]
        patient.acute_risks = ["mock_risk"]
        patient.current_medications = ["mock_medication"]

        print(f"Mock triage complete: Urgency={urgency}, Specialty={specialty}")
        return patient

    def get_urgency_description(self, score: int) -> str:
        """Convert numeric urgency score to human-readable description."""
        if score >= 9:
            return "Life-threatening emergency"
        elif score >= 7:
            return "Urgent - requires attention within 24-48 hours"
        elif score >= 4:
            return "Semi-urgent - timely specialist needed"
        else:
            return "Routine - can wait for next available appointment"