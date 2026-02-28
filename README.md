# Policy-Driven Message Router

A **policy-based message routing system** that decides how, when, and where messages are delivered using dynamic rules and real-time conditions. Supports **Email** (Mailjet) and **SMS** (Twilio) with a pluggable channel interface, async worker-based dispatch, retry policies, and a dead-letter queue (DLQ).

**Quick start (Docker):** `docker compose up -d` → API at [http://localhost:8000](http://localhost:8000), docs at [http://localhost:8000/docs](http://localhost:8000/docs). Create `.env` from `.env.example` so the app and worker can start.

---

## Features

- **Routing engine**: Routes by message type, user preferences, time of day, and priority.
- **Channel abstraction**: Email (Mailjet) and SMS (Twilio); add new channels via interface + registration.
- **Rules engine**: Example rules:
  - Critical alerts → SMS + Email
  - Promotions → Email only
  - Fallback to Email if SMS fails
- **Async processing**: Celery workers + Redis message queue.
- **Failure handling**: Per-rule retry policies and DLQ for failed messages.
- **Tracking**: Message lifecycle state machine and query APIs.

---

## Architecture

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

Text diagram:

```
  FastAPI (POST/GET /messages, /rules, /preferences)
       → Routing Engine (RulesEngine + Router)
       → PostgreSQL (Message, MessageDelivery, RoutingRule, UserPreference)
       → Celery + Redis (dispatch_message task)
       → Channel Registry → Mailjet (Email) | Twilio (SMS)
```

### Design decisions and trade-offs

| Decision | Rationale | Trade-off |
|----------|-----------|-----------|
| **Rules in DB** | Rules can be changed at runtime via API; no code deploy for new policies. | Rule evaluation is DB-bound; for very high throughput, consider caching rules. |
| **Celery + Redis** | Simple, widely used async stack; good for retries and visibility. | Adds operational dependency on Redis; alternative would be in-process queue or SQS. |
| **One delivery record per channel** | Clear audit trail and per-channel retry state. | More rows per message when using multiple channels. |
| **User preferences filter channels** | Respects user choice and quiet hours. | If all channels are disabled by prefs, message is not sent (no override in this version). |
| **Fallback channels in rule** | “Fallback to Email if SMS fails” is explicit in rule config. | Implemented at dispatch time (try primary, then fallback) rather than in rule DSL. |

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

See [docs/CONFIGURE_TWILIO_MAILJET.md](docs/CONFIGURE_TWILIO_MAILJET.md) for how to get Twilio and Mailjet credentials.

### 3. Database and rules

Tables and default routing rules are created automatically on first API startup. To seed rules again (e.g. after clearing the DB), run:

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
| POST | `/messages` | Submit a message (body: message_type, priority, body_template, body_context, recipient_id, recipient_email/phone). Returns `id` (external_id) and status. |
| GET | `/messages/{external_id}` | Get message status and delivery list. |
| GET | `/messages` | List messages (optional `?state=`). |
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

---

## Data model (schema)

See [docs/DATA_MODEL.md](docs/DATA_MODEL.md) for table and field descriptions.

---

## Message lifecycle (state machine)

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
- API (submit, status, rules, preferences)

---

## Optional: OpenTelemetry

The project is structured so you can add OpenTelemetry tracing and metrics around:

- `POST /messages` and `GET /messages/:id`
- `dispatch_message` task
- Channel `send()` calls

No instrumentation is included by default; add your preferred OTel SDK and wrap the above.

---

## License

MIT.
