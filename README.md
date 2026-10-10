# RUSH: Referral Upkeep System for Healthcare

A demo web app for rural Nova Scotia clinics: paste a doctor's notes and the clinic's postal code, and RUSH scores how urgent the case is, picks a hospital that has the right specialty and room, and creates the referral.

**All hospital data is simulated** (beds, waiting lists, specialists). Don't use this for real clinical decisions.

## Run it

```bash
git clone https://github.com/PalaashBatra/RUSH.git
cd RUSH
python3 run.py
```

Needs Python 3.9–3.13. The first run creates `venv/` and installs `requirements.txt` (about a minute); later runs start in seconds. It opens the page in your browser:

| | URL |
|---|---|
| Page | http://localhost:5500 (also at http://localhost:8000) |
| API | http://localhost:8000 |
| API docs | http://localhost:8000/docs |

Ctrl+C stops everything. Options: `--no-browser`, `--reload` (restart the API when `app/` changes), `--api-port`, `--ui-port`, `--host 0.0.0.0` (expose on your network). If a port is taken, the next free one is used.

On Debian/Ubuntu, if venv creation fails, install `python3-venv`.

### AI triage (optional)

Create a file named `.env` in the project folder:

```
ANTHROPIC_API_KEY=sk-ant-...
```

Triage then uses Claude Haiku (`claude-haiku-5-5`). To use a different model, add `ANTHROPIC_MODEL=<model id>` to `.env`.

Without a key, or if a call fails, triage falls back to simple keyword matching and the page tells you to double-check the urgency.

## Using the website

The black bar at the top always says the one thing to do next.

1. **Paste the doctor's notes and the clinic postal code, then hit Find hospital.** No notes? Click an example (or press F1/F2/F3).
2. **Check the suggested hospital, then hit Send referral.** If the bar says "check first", the urgency came from keyword matching, so make sure it's right.
   - **Send somewhere else** lists every hospital so you can pick another. The receipt then records that you chose it and what RUSH suggested.
   - **Show the map and how every hospital scored** shows the route and the full score table.
3. **Done.** Copy or print the receipt, then hit **Next patient**.

`Ctrl + Enter` always presses the big blue button.

At the bottom, **Hospital capacity (live)** shows how full each hospital is (refreshed every 5 seconds). **Demo: make a hospital busy** fills a random hospital up so you can watch the suggestion change; **Put hospitals back** undoes it.

If the API isn't running, the page switches to **practice mode**: the same 10 hospitals and the same routing run in the browser, triage is keyword-only, and nothing is sent to a server.

## How it picks a hospital

1. **Triage** reads the notes and returns an urgency score (1–10), the specialty needed, and any symptoms, risks and medications it spots.
2. **Routing** only considers hospitals that offer that specialty, and scores each one on three things:
   - **Specialist free:** how many specialists in that specialty have open slots (3 or more counts as full marks).
   - **Room:** 70% free beds, 30% short waiting list.
   - **Distance:** from the clinic's postal code, where 0 km is best and 400 km or more scores zero.
3. **The weights depend on urgency:**

   | Urgency | Specialist free | Room | Distance |
   |---|---|---|---|
   | Emergency (8–10) | 70% | 20% | 10% |
   | See soon (4–7) | 20% | 50% | 30% |
   | Routine (1–3) | 10% | 30% | 60% |

4. **The referral.** The highest score wins. If a specialist there has a free slot they're assigned to the patient; otherwise the patient joins that hospital's waiting list. The expected wait is that specialist's wait (or a third of the waiting list, minimum 7 days), cut to a quarter for urgency 9–10 and to half for 7–8.

The **Send somewhere else** list is sorted the same way the urgency tiers prioritize: emergencies by who can see them soonest, see-soon cases by most room, and routine cases by shortest drive.

**Distances only work for these postal codes:** B1P 5E7 (Sydney), B3H 2Y9 (Halifax), B2N 1L5 (Truro), B1S 1A1, B4N 1V5 (Kentville), B0W 2M0 (Bridgewater), B0N 1X0 (Yarmouth), B0V 1N0 (Amherst), B2H 1A1 (New Glasgow), B2N 0A1 (Antigonish), B1M 1A1 (Glace Bay), B0J 1S0 (Lunenburg) and E2L 4L2 (Saint John). Any other code is treated as 100 km from every hospital.

## Hospitals (simulated)

| ID | Name | Specialties |
|---|---|---|
| HAL_QEII | QEII Health Sciences Centre | Cardiology, Neurology, Oncology, Orthopedics, General Surgery |
| TRU_COLCH | Colchester East Hants Health Centre | Cardiology, Orthopedics, General Medicine |
| CB_REG | Cape Breton Regional Hospital | Cardiology, General Surgery, Emergency Medicine |
| VALLEY_REG | Valley Regional Hospital | General Medicine, Orthopedics, Maternity |
| SW_REG | South Shore Regional Hospital | General Medicine, Emergency Medicine |
| YAR_REG | Yarmouth Regional Memorial | General Medicine, Emergency Medicine, Orthopedics |
| AMH_REG | Amherst Hospital | General Medicine, Emergency Medicine |
| GLW_REG | North Nova Scotia Health Centre | General Medicine, Cardiology |
| ANT_REG | Antigonish Memorial | General Medicine, Orthopedics |
| SJ_REG | Saint John Regional Hospital (NB) | Neurology, Cardiology, General Surgery, Emergency Medicine |

## API

| Method | Endpoint | What it does |
|---|---|---|
| GET | `/` | The page |
| GET | `/health` | Status, and whether AI triage is available |
| POST | `/triage` | `{clinical_notes, home_clinic_zip}` → urgency, specialty, symptoms, risks, medications |
| POST | `/refer` | Same body (triaged or not) → referral to the best hospital. `?hub_id=CB_REG` sends it there instead; the referral keeps `manual_override` and `suggested_hub_*`. |
| GET | `/hubs` | All hospitals with current capacity and specialists |
| POST | `/simulate/update-capacity` | `?hub_id=&occupied_beds=&queue_length=` sets a hospital's load (demo button) |

Example:

```bash
curl -X POST localhost:8000/refer -H 'content-type: application/json' \
  -d '{"clinical_notes": "55yo male, crushing chest pain, ST elevation, troponin elevated", "home_clinic_zip": "B1P 5E7"}'
```

## Limits

- Hospital capacity and specialists are made up and live in memory; the demo button changes them until the server restarts.
- Referrals aren't saved anywhere. You get the referral back from `/refer`, and that's it.
- There's no login, no notifications to hospitals, and no connection to real hospital systems.

## Project structure

```
app/
  main.py                    API endpoints, serves the page
  models/
    patient.py               triage input/output
    hub.py                   hospital, specialists, capacity score, distance
    referral.py              referral returned by /refer
  services/
    triage_service.py        Claude call + keyword fallback
    routing_engine.py        hospital data and scoring
index.html                   the whole UI (single file, no build step)
run.py                       one-command launcher: venv + API + UI
requirements.txt
SH.png                       logo
```

Built for the Nova Scotia B2B AI SaaS Hackathon.
