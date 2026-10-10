"""
AI Triage Service
Transforms unstructured clinical notes into structured medical urgency scores and specialties.
"""
import json
import os
import httpx
from dotenv import load_dotenv

from app.models.patient import Patient

load_dotenv()

# Specialties the hospitals in routing_engine.py offer. Triage must return one of these
# exactly, or routing can't match it to a hospital.
SPECIALTIES = ["Cardiology", "Neurology", "Oncology", "Orthopedics", "General Surgery",
               "General Medicine", "Emergency Medicine", "Maternity"]

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
        # Haiku: fastest and cheapest, plenty for pulling urgency/specialty out of notes.
        # Override with ANTHROPIC_MODEL in .env (e.g. claude-sonnet-5-5) if you want a bigger model.
        self.model = os.getenv("ANTHROPIC_MODEL", "claude-haiku-5-5")

        if not self.api_key:
            # For demo purposes, use a mock mode if no API key is set
            print("ANTHROPIC_API_KEY not found. Running in mock mode.")
            self.mock_mode = True
        else:
            self.mock_mode = False
            print(f"AI triage on: {self.model}")
            self.headers = {
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }

    async def analyze_clinical_notes(self, patient: Patient) -> Patient:
        """
        Analyze the patient's clinical notes and populate the structured fields.

        Returns the same patient object with populated:
        - urgency_score
        - primary_specialty_required
        - key_symptoms
        - acute_risks
        - current_medications

        Falls back to keyword matching if there's no API key or the API call fails.
        """
        if self.mock_mode:
            return self._mock_analysis(patient)

        # Construct the prompt for Claude
        system_prompt = """You are a medical triage AI assistant for Nova Scotia's RUSH (Referral Upkeep System for Healthcare) system.

        Your task is to analyze unstructured clinical notes from a rural doctor and extract:
        1. Medical urgency score (1-10 scale, where 10 is life-threatening emergency)
        2. Primary medical specialty required: exactly one of """ + ", ".join(SPECIALTIES) + """
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
                        "max_tokens": 1500,  # room for any thinking the model does before the JSON
                        "system": system_prompt,
                        "messages": [{"role": "user", "content": user_prompt}]
                    }
                )

                if response.status_code != 200:
                    print(f"Claude API error: {response.status_code} - {response.text}")
                    return self._mock_analysis(patient)

                # The reply can contain a thinking block before the answer; only text blocks hold the JSON
                blocks = response.json().get("content", [])
                content = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
                triage_data = self._parse_json(content)

                urgency = self._clean_urgency(triage_data.get("urgency_score"))
                specialty = self._clean_specialty(triage_data.get("primary_specialty_required"))
                if urgency is None or specialty is None:
                    print(f"Claude reply missing a usable urgency/specialty, using keywords instead: {content[:300]!r}")
                    return self._mock_analysis(patient)

                patient.urgency_score = urgency
                patient.primary_specialty_required = specialty
                patient.key_symptoms = self._clean_list(triage_data.get("key_symptoms"))
                patient.acute_risks = self._clean_list(triage_data.get("acute_risks"))
                patient.current_medications = self._clean_list(triage_data.get("current_medications"))

                return patient

        except Exception as e:
            print(f"Error during AI triage: {e}")
            return self._mock_analysis(patient)

    @staticmethod
    def _parse_json(text: str) -> dict:
        """Pull the JSON object out of the reply, even if it's wrapped in ```json fences or extra words."""
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end < start:
            raise ValueError(f"no JSON object in reply: {text[:200]!r}")
        data = json.loads(text[start:end + 1])
        if not isinstance(data, dict):
            raise ValueError("reply JSON is not an object")
        return data

    @staticmethod
    def _clean_urgency(value) -> "int | None":
        try:
            return min(10, max(1, round(float(value))))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _clean_specialty(value) -> "str | None":
        """Map the model's answer onto SPECIALTIES ("cardiology", "Cardiology - electrophysiology" -> "Cardiology")."""
        if not isinstance(value, str):
            return None
        v = value.strip().lower()
        for sp in SPECIALTIES:
            if v == sp.lower():
                return sp
        for sp in SPECIALTIES:
            if sp.lower() in v:
                return sp
        return None

    @staticmethod
    def _clean_list(value) -> list:
        return [str(x) for x in value if x] if isinstance(value, list) else []

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
