# Maintenance Copilot

Maintenance Copilot is an industrial monitoring prototype that turns sensor
readings into traceable maintenance actions. It combines deterministic Python
and SQL calculations with an OpenAI-powered agent running in an NVIDIA
NemoClaw sandbox.

The agent can inspect equipment state, explain threshold violations, create a
maintenance-ticket draft, avoid duplicate tickets, and approve a draft only
after an explicit user request.

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

## Architecture

```text
CSV sensor readings
        |
        v
Python validation and calculations
        |
        v
SQLite: equipment, thresholds, readings, tickets
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

OpenAI handles intent recognition, tool selection, and user-facing
explanations. NVIDIA NemoClaw provides the isolated agent runtime. NVIDIA NeMo
Guardrails checks generated analytical reports before they are shown in the
dashboard.

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

## Local setup

Requires Python 3.12 or later.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Add an OpenAI API key to `.env` if you want to use AI reports. Never commit the
`.env` file.

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

The prototype works with uploaded CSV files and one local database. It does not
yet connect to live sensors, a CMMS, or an ERP. Maintenance recommendations
remain generic until equipment manuals are indexed and returned with source
citations.
