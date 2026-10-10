# RUSH: Referral Upkeep System for Healthcare

An AI-powered healthcare referral routing system for Nova Scotia. This B2B SaaS solution optimizes patient referrals from rural clinics to specialist hubs using constraint-based routing and medical AI triage.

## The Problem

Nova Scotia's healthcare system faces a critical fragmentation problem:

- Rural doctors often refer patients to Halifax by default, unaware of regional capacity
- High-urgency cases travel unnecessarily long distances
- Regional hubs remain underutilized while Halifax faces bottlenecks
- No real-time visibility into province-wide capacity

## The Solution

RUSH uses AI to:

1. **Analyze clinical notes** to determine medical urgency (1-10) and required specialty
2. **Monitor real-time capacity** across all Nova Scotia healthcare hubs
3. **Optimize routing** using constraint-based algorithms that prioritize differently based on urgency
4. **Provide province-wide visibility** into referral flow and system capacity

## Technical Architecture

### Backend Stack

- **FastAPI**: High-performance async API framework
- **Pydantic**: Data validation and serialization
- **Claude AI**: Medical note analysis and urgency scoring
- **Custom Routing Engine**: Constraint-based optimization algorithm

### Core Components

#### 1. AI Triage Service (`app/services/triage_service.py`)

- Transforms unstructured clinical notes into structured medical data
- Extracts urgency score (1-10) and required specialty
- Falls back to rule-based mock analysis if no API key available

#### 2. Routing Engine (`app/services/routing_engine.py`)

- **Constraint-based algorithm** with urgency-specific weighting:

  | Urgency | Priority Order |
  |---------|----------------|
  | High (8-10) | Specialist availability > Distance |
  | Medium (4-7) | Capacity score > Distance |
  | Low (1-3) | Distance > Capacity score |

- Simulated Nova Scotia healthcare hubs with realistic capacity data
- Real-time distance calculations (mock geolocation)

#### 3. Data Models

- **Patient**: Clinical notes, extracted urgency, required specialty
- **HealthcareHub**: Provincial hospitals with specialties, capacity metrics
- **Referral**: Complete referral workflow with audit trail

### Registered Healthcare Hubs

| Hub ID | Name | Specialties |
|--------|------|-------------|
| HAL_QEII | QEII Health Sciences Centre | Cardiology, Neurology, Oncology, Orthopedics, General Surgery |
| TRU_COLCH | Colchester East Hants Health Centre | Cardiology, Orthopedics, General Medicine |
| CB_REG | Cape Breton Regional Hospital | Cardiology, General Surgery, Emergency Medicine |
| VALLEY_REG | Valley Regional Hospital | General Medicine, Orthopedics, Maternity |
| SW_REG | South Shore Regional Hospital | General Medicine, Emergency Medicine |

## API Endpoints

### Core Workflow

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/triage` | Analyze clinical notes, return urgency and specialty |
| POST | `/refer` | Create referral with optimal hub routing (add `?hub_id=HUB_ID` to override the hub; the referral keeps `manual_override` and RUSH's `suggested_hub_*`) |
| GET | `/referral/{id}` | Check referral status and details |

### System Monitoring

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/hubs` | List all hubs with current capacity |
| GET | `/dashboard` | System-wide metrics and referral statistics |
| GET | `/health` | System health check |

### Demo Utilities

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/simulate/update-capacity` | Mock capacity updates for demos |

## Quick Start

### Prerequisites

- Python 3.9-3.13 (the pinned pydantic has no wheels for 3.14 yet)
- Anthropic API key (optional - keyword fallback without one)

### 1. Run it

```bash
git clone https://github.com/PalaashBatra/RUSH.git
cd RUSH
python3 run.py
```

That's the whole setup. The first run creates `venv/` and installs `requirements.txt` (about a minute); later runs start in about a second and only reinstall when `requirements.txt` changes. It then starts:

| | URL |
|---|---|
| Dashboard UI (`index.html`) | http://localhost:5500 |
| API | http://localhost:8000 |
| API docs (Swagger) | http://localhost:8000/docs |

and opens the dashboard in your browser. Ctrl+C stops everything.

Options: `--no-browser`, `--reload` (restart the API when `app/` changes), `--api-port`, `--ui-port`, `--host 0.0.0.0` (expose on your network; default is localhost only). If a port is taken, the next free one is used and the UI is pointed at it automatically.

On Debian/Ubuntu, if venv creation fails, install `python3-venv`. To type `python` instead of `python3`, install `python-is-python3`.

### 2. Real AI triage (optional)

```bash
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

Without an API key, triage uses keyword matching and the UI flags every result as "check urgency by hand".

### 3. Using the website

The black bar at the top always tells you the one thing to do next. Follow it.

1. **Paste the doctor's notes and the clinic postal code, then hit Find hospital.** No notes? Click one of the example chips (or press F1/F2/F3).
2. **Read the big hospital name. If the bar says "check first", make sure the urgency is right. Then hit Send referral.** Want to see how it decided? Open "Show the map and how every hospital scored". Want it to go somewhere else? Hit **Send somewhere else** and tap a hospital; the card switches to "Your pick" and the receipt records what RUSH suggested.
3. **Done.** Copy or print the receipt, then hit **Next patient**.

`Ctrl + Enter` always presses the big green button. The "Hospital capacity (live)" drawer at the bottom shows how full each hospital is; its **Demo: make a hospital busy** button fills one up so you can watch the match change live.

## Example Use Cases

### High Urgency Cardiac Case (Cape Breton -> Halifax)

**Request:**

```json
POST /triage
{
  "patient_id": "PAT_NS_001",
  "clinical_notes": "55yo male with crushing chest pain, ST elevation V1-V4, troponin elevated",
  "home_clinic_zip": "B1P 5E7"
}
```

**Response:**

```json
{
  "urgency_score": 9,
  "primary_specialty_required": "Cardiology",
  "target_hub": "QEII Health Sciences Centre",
  "distance_km": 320.5,
  "estimated_wait_days": 2,
  "routing_logic": "High urgency - prioritized specialist availability over distance"
}
```

### Low Urgency Orthopedic Case (Truro -> Local Hub)

**Request:**

```json
POST /triage
{
  "clinical_notes": "35yo with chronic knee pain, MRI shows meniscus tear",
  "home_clinic_zip": "B2N 1L5"
}
```

**Response:**

```json
{
  "urgency_score": 3,
  "primary_specialty_required": "Orthopedics",
  "target_hub": "Colchester East Hants Health Centre",
  "distance_km": 5.2,
  "estimated_wait_days": 10,
  "routing_logic": "Low urgency - prioritized proximity to patient"
}
```

## For Hackathon Judges

### What Makes This Different from "Just an LLM"?

1. **Constraint-Based Optimization**: The AI does the medical analysis, but the backend does the smart routing using multiple variables (distance, capacity, urgency, specialist availability).

2. **Urgency-Weighted Algorithms**: The system changes its prioritization logic dynamically based on medical urgency score.

3. **Province-Wide Orchestration**: This is not a chatbot - it is a logistics engine that optimizes flow across an entire provincial healthcare system.

4. **Real Healthcare Impact**: Solves a visible, documented problem in Nova Scotia's rural healthcare delivery.

### Scalability and Production Readiness

- Async API design for high throughput
- Mock services easily replaceable with real hospital APIs
- Modular architecture allows adding real geolocation, EHR integration, etc.
- Audit trail for compliance and accountability

## Project Structure

```
RUSH/
├── app/
│   ├── main.py                    # FastAPI application and endpoints
│   ├── models/
│   │   ├── patient.py             # Patient data model
│   │   ├── hub.py                 # Healthcare hub model
│   │   └── referral.py            # Referral workflow model
│   └── services/
│       ├── triage_service.py      # AI triage integration
│       └── routing_engine.py      # Constraint-based routing
├── index.html                     # Dashboard UI (single file, no build step)
├── run.py                         # One-command launcher: venv setup + API + UI
├── requirements.txt               # Python dependencies
├── .env.example                   # Environment template
└── README.md                      # This file
```

## Future Enhancements

1. **Real Integration**: Connect to Nova Scotia Health Authority APIs
2. **ML Prediction**: Use historical data to predict capacity bottlenecks
3. **Mobile Notifications**: Real-time alerts for clinics and specialists
4. **Blockchain Audit**: Immutable audit trail for compliance
5. **Multi-Province Expansion**: Scale to other Atlantic provinces

## License

MIT - Built for the Nova Scotia B2B AI SaaS Hackathon

---

Built with Claude Code for rapid prototyping