# Policy-Driven Message Router

A **policy-based message routing system** that decides how, when, and where messages are delivered using dynamic rules and real-time conditions. Supports **Email** (Mailjet) and **SMS** (Twilio) with a pluggable channel interface, async worker-based dispatch, retry policies, and a dead-letter queue (DLQ).

**Quick start:** `docker compose up -d` → API at [http://localhost:8000](http://localhost:8000), docs at [http://localhost:8000/docs](http://localhost:8000/docs). Create `.env` from `.env.example` so the app and worker can start.

---

## Features

- **Routing engine** – Routes by message type, user preferences, time of day, and priority
- **Channel abstraction** – Email (Mailjet) and SMS (Twilio); add new channels via interface + registry
- **Rules engine** – Configurable rules (e.g. critical alerts → SMS+Email, promotions → Email only)
- **Async processing** – Celery workers + Redis message queue
- **Failure handling** – Per-rule retry policies and DLQ for failed messages
- **Tracking** – Message lifecycle state machine and query APIs

---

## Design & Architecture

### Overview

The system separates **policy** (what to do) from **execution** (how to do it). Policies live in the database as routing rules and user preferences. When a message is submitted, the API enqueues it immediately and returns. A Celery worker picks it up, evaluates rules and preferences, creates delivery records per channel, and sends via the appropriate providers.

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐     ┌──────────────┐
│   Client    │────▶│  FastAPI     │────▶│  Celery Worker  │────▶│  Mailjet /   │
│  (POST)     │     │  (enqueue)   │     │  (route+send)   │     │  Twilio      │
└─────────────┘     └──────────────┘     └─────────────────┘     └──────────────┘
                            │                        │
                            ▼                        ▼
                    ┌──────────────┐         ┌──────────────┐
                    │  PostgreSQL  │         │    Redis     │
                    │  (messages,  │         │  (task queue)│
                    │   rules,     │         └──────────────┘
                    │   prefs)     │
                    └──────────────┘
```

### Architecture Diagram

```mermaid
flowchart TB
    subgraph API["FastAPI App"]
        POST["POST /messages"]
        GET["GET /messages/:id"]
        RULES["/rules, /preferences"]
    end
    subgraph ROUTING["Routing Engine"]
        RE["RulesEngine"]
        R["Router"]
    end
    subgraph STORAGE["Storage"]
        DB[(PostgreSQL)]
        MSG["Message + MessageDelivery + Rules"]
    end
    subgraph ASYNC["Async"]
        CELERY["Celery (Redis)"]
        TASK["dispatch_message"]
    end
    subgraph CHANNELS["Channels"]
        EMAIL["Mailjet (Email)"]
        SMS["Twilio (SMS)"]
    end
    API --> ROUTING
    ROUTING --> STORAGE
    STORAGE --> DB
    API --> CELERY
    CELERY --> TASK
    TASK --> ROUTING
    TASK --> CHANNELS
```

### Design Principles

| Principle | Implementation |
|-----------|----------------|
| **Policy in data** | Routing rules and user preferences live in the database. Change behavior via API without code deploys. |
| **Async-first** | Submit returns immediately; delivery happens in a worker. Clients get `external_id` for status polling. |
| **Pluggable channels** | `ChannelBase` interface + `ChannelRegistry`. Add Slack, push, etc. by implementing the interface and registering. |
| **Explicit fallback** | Rules define `channels` (primary) and `fallback_channels`. If primary fails, try fallback before retrying. |
| **Per-channel audit** | One `MessageDelivery` row per channel attempt. Clear history of what was tried and why it failed. |

---

## Implementation

### Request Flow

1. **POST /messages** – Client sends message with `message_type`, `priority`, `recipient_id`, `recipient_email`/`recipient_phone`, and template fields. API validates, persists to DB, sets state to `queued`, enqueues `dispatch_message` task, and returns `external_id` + status.

2. **Celery worker** – Picks up `dispatch_message(message_id)`. Loads message, calls `RulesEngine.decide_channels()` and `Router.route()` to get primary channels, fallback channels, and `max_retries`.

3. **Routing decision** – `RulesEngine` loads active rules ordered by `priority_order`, finds first matching rule (conditions on `message_type`, `priority`, optional time window), then filters channels by `UserPreference` (enabled, quiet hours, `message_types_allowed`). `Router` further filters by available contact info (email/phone).

4. **Delivery** – For each primary channel, creates a `MessageDelivery` record, looks up channel via `ChannelRegistry`, renders body with Jinja2, and calls `channel.send()`. On success, marks delivery `delivered`. On failure, tries fallback channels. If all fail, increments retry count and re-enqueues (or moves to DLQ after `max_retries`).

5. **State updates** – Message state: `queued` → `dispatching` → `delivered` | `failed` | `dlq`. Transitions are validated by `state.py` to prevent invalid moves.

### Key Components

| Component | Location | Responsibility |
|-----------|----------|----------------|
| **RulesEngine** | `src/rules/engine.py` | Match message context to rules; filter channels by user preferences (quiet hours, enabled, message types). |
| **Router** | `src/rules/router.py` | Combine rules output with recipient contact info; produce final channel list and fallback. |
| **ChannelRegistry** | `src/channels/base.py` | Resolve channel by name; `get_available()` returns only configured channels. |
| **ChannelBase** | `src/channels/base.py` | Interface: `name`, `send(payload)`, `is_available()`. Mailjet and Twilio implement this. |
| **State machine** | `src/state.py` | Valid transitions for message and delivery; `set_message_state`, `set_delivery_state`. |
| **dispatch_message** | `src/tasks.py` | Celery task: load message, route, create deliveries, send, handle fallback and retries. |

### Rules Evaluation

Rules are evaluated in `priority_order` (lower first). Conditions are JSON:

- `message_types`: list of allowed types (`critical_alert`, `promotion`, `transactional`, `notification`)
- `priorities`: list of allowed priorities (`low`, `normal`, `high`, `critical`)
- `time_window_start` / `time_window_end`: optional "HH:MM" for allowed send window

User preferences further filter:

- `enabled`: if false, channel is excluded
- `quiet_hours_start` / `quiet_hours_end`: no sends during this period (e.g. 22:00–08:00)
- `message_types_allowed`: if non-empty, only these types allowed on this channel

### Default Rules (seeded on startup)

| Rule | Conditions | Channels | Fallback | Retries |
|------|------------|----------|----------|---------|
| Critical alerts | `critical_alert`, high/critical priority | SMS, Email | Email | 5 |
| Promotions | `promotion` | Email | — | 2 |
| Transactional | `transactional` | Email | SMS | 3 |
| Default | (catch-all) | Email | SMS | 3 |

---

## Design Decisions & Trade-offs

| Decision | Rationale | Trade-off |
|----------|-----------|-----------|
| **Rules in DB** | Change policies at runtime via API; no deploy for new rules. | Rule evaluation is DB-bound; for very high throughput, consider caching. |
| **Celery + Redis** | Widely used async stack; good for retries and visibility. | Adds Redis dependency; alternative: in-process queue or SQS. |
| **One delivery per channel** | Clear audit trail and per-channel retry state. | More rows per message when using multiple channels. |
| **User prefs filter channels** | Respects user choice and quiet hours. | If all channels disabled, message is not sent (no override). |
| **Fallback in rule** | "Fallback to Email if SMS fails" is explicit in config. | Implemented at dispatch time (try primary, then fallback) rather than in rule DSL. |

---

## Setup

### Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- (Optional) Twilio and Mailjet accounts for live SMS/Email

### 1. Clone and install

```bash
git clone <repo>
cd policy-driven-message-router
python -m venv venv
source venv/bin/activate   # or venv\Scripts\activate on Windows
pip install -r requirements.txt
```

### 2. Environment

Copy `.env.example` to `.env` and set variables. For local runs, database and Redis URLs are needed; for real SMS/Email add Twilio and Mailjet credentials:

```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/message_router
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1

# Optional: for real delivery
TWILIO_ACCOUNT_SID=your_sid
TWILIO_AUTH_TOKEN=your_token
TWILIO_FROM_NUMBER=+1234567890
MAILJET_API_KEY=your_key
MAILJET_API_SECRET=your_secret
MAILJET_FROM_EMAIL=noreply@example.com
MAILJET_FROM_NAME=Message Router
```

See [docs/CONFIGURE_TWILIO_MAILJET.md](docs/CONFIGURE_TWILIO_MAILJET.md) for credential setup.

### 3. Database and rules

Tables and default routing rules are created automatically on first API startup. To seed rules again (e.g. after clearing the DB):

```bash
python -m src.seed_rules
```

### 4. Run with Docker Compose (recommended)

```bash
docker compose up -d
# API: http://localhost:8000
# Docs: http://localhost:8000/docs
```

### 5. Run locally (no Docker)

Terminal 1 – API:

```bash
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

Terminal 2 – Celery worker:

```bash
celery -A src.celery_app worker -Q dispatch,celery -l info
```

Ensure PostgreSQL and Redis are running and `DATABASE_URL` / `CELERY_BROKER_URL` point to them.

---

## API Overview

| Method | Path | Description |
|--------|------|-------------|
| POST | `/messages` | Submit a message. Body: `message_type`, `priority`, `body_template`, `body_context`, `recipient_id`, `recipient_email`/`recipient_phone`. Returns `id` (external_id) and status. |
| GET | `/messages/{external_id}` | Get message status and delivery list. |
| GET | `/messages` | List messages (optional `?state=`, `?limit=`). |
| GET/POST/PATCH/DELETE | `/rules` | CRUD for routing rules. |
| GET/POST | `/preferences` | User channel preferences (quiet hours, allowed message types). |

Example – submit message:

```bash
curl -X POST http://localhost:8000/messages \
  -H "Content-Type: application/json" \
  -d '{
    "message_type": "critical_alert",
    "priority": "critical",
    "body_template": "Alert: {{ text }}",
    "body_context": {"text": "Server down"},
    "recipient_id": "user1",
    "recipient_email": "user@example.com",
    "recipient_phone": "+15551234567"
  }'
```

See [docs/TESTING.md](docs/TESTING.md) for full CRUD examples with JSON.

---

## Data Model

See [docs/DATA_MODEL.md](docs/DATA_MODEL.md) for table and field descriptions. For a detailed project walkthrough (packages, folder structure, entry points, and file-by-file explanation), see [docs/PROJECT_DETAILS.md](docs/PROJECT_DETAILS.md).

---

## Message Lifecycle (State Machine)

- **pending** → **queued** (when submitted and enqueued)
- **queued** → **dispatching** (worker picked up)
- **dispatching** → **delivered** | **failed** | **dlq**
- **failed** → **queued** (retry) up to `max_retries`, then → **dlq**

---

## Tests

```bash
# In-memory SQLite (no Postgres/Redis needed)
export DATABASE_URL=sqlite:///:memory:?check_same_thread=0
pytest tests/ -v
```

See [docs/TESTING.md](docs/TESTING.md) for manual testing via the API. Automated tests cover:

- Preference filtering (channel enabled/disabled, message type, quiet hours)
- Rules engine (condition matching, channel and fallback selection)
- Template rendering (Jinja2)
- State machine transitions
- Retry and DLQ behavior
- API (submit, status, rules, preferences)

---

## Optional: OpenTelemetry

The project is structured so you can add OpenTelemetry tracing and metrics around:

- `POST /messages` and `GET /messages/:id`
- `dispatch_message` task
- Channel `send()` calls

No instrumentation is included by default; add your preferred OTel SDK and wrap the above.
