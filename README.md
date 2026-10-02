# EnlikHelper

EnlikHelper is an industrial maintenance agent that turns sensor
readings into traceable maintenance actions. It combines deterministic Python
and SQL calculations with an OpenAI-powered agent running in an NVIDIA
NemoClaw sandbox.

The agent can inspect equipment state, explain threshold violations, create a
maintenance-ticket draft, avoid duplicate tickets, approve a draft only after
an explicit user request, and retrieve relevant procedures from indexed PDF
manuals with page citations.

## Why this is an agent

The language model does not calculate measurements or edit the database
directly. It selects a registered tool from the user's request. The Python
tools validate the action, calculate the result, and persist it in SQLite.

Current tools:

- `snapshot <equipment_id>` — read the verified equipment state;
- `create-ticket-draft <equipment_id>` — create an idempotent draft from the
  latest alert;
- `list-tickets` — list maintenance tickets;
- `approve-ticket <ticket_id>` — approve a draft after explicit confirmation.
- `index-manual <equipment_id> <file.pdf>` — extract and index a PDF manual;
- `search-manual <equipment_id> <query>` — retrieve relevant manual fragments
  with filename and page citations;
- `list-manuals [equipment_id]` — list indexed manuals.
- `set-profile <equipment_id> --manufacturer ... --model ... --serial ...` —
  attach the known equipment identity to the measurements and manuals.

## Architecture

```text
CSV sensor readings
        |
        v
Python validation and calculations
        |
        v
SQLite: equipment, thresholds, readings, tickets, manual chunks
        |
        +--------------------+
        |                    |
        v                    v
FastAPI dashboard      NVIDIA NemoClaw sandbox
                             |
                             v
                       OpenAI agent model
                             |
                             v
                    Registered Python tools
```

OpenAI handles intent recognition, tool selection, user-facing explanations,
and embeddings for semantic search over equipment manuals. NVIDIA NemoClaw
provides the isolated, always-on agent runtime. NVIDIA NeMo Guardrails checks
generated analytical reports before they are shown in the dashboard.

## Safety and traceability

- Equipment status is calculated in SQL from stored readings and configured
  thresholds.
- Ticket evidence stores the exact thresholds, summary, and alert used to
  create the ticket.
- Repeating the same action does not create duplicate tickets.
- A status check never creates or approves a ticket.
- Approval changes only the local ticket status and does not send anything to
  an external maintenance system.
- AI output is an operational aid, not an equipment diagnosis.
- Manual guidance is grounded in retrieved PDF fragments and includes the
  filename and page number.
- A manual is treated as general guidance until the equipment manufacturer and
  model are recorded in its profile.

## Local setup

Requires Python 3.12 or later.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Add an OpenAI API key to `.env` to use AI reports and manual search. Never
commit the `.env` file.

Import the sample data and configure the second motor:

```bash
python main.py import data/motor_readings.csv
python main.py import data/motor_02_readings.csv
python main.py thresholds MOTOR-02 --temperature 60 --vibration 5
```

Start the dashboard:

```bash
python -m uvicorn web_app:app --reload
```

Open <http://127.0.0.1:8000>.

## Agent tool examples

```bash
python agent_tools.py snapshot MOTOR-01
python agent_tools.py create-ticket-draft MOTOR-01
python agent_tools.py list-tickets
python agent_tools.py approve-ticket 1
python agent_tools.py index-manual MOTOR-01 manual.pdf
python agent_tools.py search-manual MOTOR-01 "Что проверить при вибрации?"
python agent_tools.py list-manuals MOTOR-01
python agent_tools.py set-profile MOTOR-01 --manufacturer ABB --model "M2B" --serial "SERIAL-001"
```

## Verification

Run the deterministic agent workflow tests:

```bash
python -m unittest test_agent_tools.py
```

Check the API:

```bash
curl http://127.0.0.1:8000/api/health
curl http://127.0.0.1:8000/api/report
```

## Current scope

The prototype works with uploaded CSV and PDF files and one local database. It
does not yet connect to live sensors, a CMMS, or an ERP. PDF files must contain
extractable text; scanned manuals require OCR before indexing.
