# Policy-Driven Message Router – Project Details

A comprehensive guide to the project: packages, folder structure, entry points, and a detailed explanation of every Python file and function.

---

## 1. Project Overview

The **Policy-Driven Message Router** is a Python service that routes outbound messages (email, SMS) based on configurable rules and user preferences. When a client submits a message, the system:

1. Persists it and enqueues it for async processing
2. A Celery worker picks it up and evaluates routing rules
3. Filters channels by user preferences (quiet hours, enabled channels, message types)
4. Sends via Mailjet (email) or Twilio (SMS)
5. Handles retries and fallback channels, moving failed messages to a dead-letter queue (DLQ) after max retries

---

## 2. Packages and Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| **fastapi** | ≥0.109.0 | Web framework for REST API. Chosen for automatic OpenAPI docs, validation, and async support. |
| **uvicorn** | ≥0.27.0 | ASGI server to run FastAPI. Standard choice for production Python async apps. |
| **pydantic** | ≥2.0 | Data validation and serialization. Used for request/response schemas and config. |
| **pydantic-settings** | ≥2.0 | Load settings from environment variables and `.env`. Keeps secrets out of code. |
| **celery[redis]** | ≥5.3.0 | Distributed task queue. Handles async message dispatch, retries, and visibility. |
| **redis** | ≥5.0.0 | Message broker for Celery. Lightweight, widely used, good for task queues. |
| **sqlalchemy** | ≥2.0.0 | ORM for database access. Supports PostgreSQL and SQLite (for tests). |
| **psycopg2-binary** | ≥2.9.0 | PostgreSQL driver for SQLAlchemy. Required for production DB. |
| **pytest** | ≥7.4.0 | Test framework. Industry standard for Python testing. |
| **pytest-asyncio** | ≥0.23.0 | Async test support for pytest. (Used if async endpoints are added.) |
| **httpx** | ≥0.26.0 | HTTP client for Mailjet API calls. Modern, sync/async capable. |
| **twilio** | ≥8.0.0 | Twilio SDK for SMS. Official client for sending SMS. |
| **jinja2** | ≥3.1.0 | Template engine for message body rendering. Supports `{{ variable }}` syntax. |

**Why these choices?**

- **FastAPI + Pydantic**: Type-safe API with automatic validation and OpenAPI docs.
- **Celery + Redis**: Proven async task processing with retries and monitoring.
- **SQLAlchemy**: Flexible ORM that works with PostgreSQL (prod) and SQLite (tests).
- **Jinja2**: Familiar templating for dynamic message content.
- **httpx for Mailjet**: No official Mailjet Python SDK in requirements; REST API is called directly via httpx.

---

## 3. Folder Structure

```
policy-driven-message-router/
├── src/                          # Application source code
│   ├── __init__.py
│   ├── main.py                   # FastAPI entry point
│   ├── config.py                 # Environment-based configuration
│   ├── db.py                     # Database engine and session
│   ├── celery_app.py             # Celery application
│   ├── tasks.py                  # Celery tasks (dispatch_message)
│   ├── state.py                  # Message lifecycle state machine
│   ├── templates.py              # Jinja2 template rendering
│   ├── seed_rules.py             # Seed default routing rules
│   ├── api/                      # REST API endpoints
│   │   ├── __init__.py
│   │   ├── messages.py           # POST/GET /messages
│   │   ├── rules.py              # CRUD /rules
│   │   └── preferences.py        # POST/GET /preferences
│   ├── channels/                 # Delivery channel implementations
│   │   ├── __init__.py           # Registry + channel registration
│   │   ├── base.py               # ChannelBase interface, ChannelRegistry
│   │   ├── mailjet_channel.py    # Email via Mailjet
│   │   └── sms_channel.py        # SMS via Twilio
│   ├── models/                   # Data models and schemas
│   │   ├── __init__.py
│   │   ├── orm_models.py         # SQLAlchemy ORM models
│   │   └── schemas.py            # Pydantic request/response schemas
│   └── rules/                    # Routing logic
│       ├── __init__.py
│       ├── engine.py             # RulesEngine: match rules, filter by prefs
│       └── router.py             # Router: combine rules + contact info
├── tests/                        # Test suite
│   ├── conftest.py               # Pytest fixtures
│   ├── test_api.py
│   ├── test_preferences.py
│   ├── test_retry_behavior.py
│   ├── test_rules_engine.py
│   ├── test_state.py
│   └── test_templates.py
├── docs/                         # Documentation
│   ├── CONFIGURE_TWILIO_MAILJET.md
│   ├── DATA_MODEL.md
│   ├── TESTING.md
│   └── PROJECT_DETAILS.md         # This file
├── docker-compose.yml
├── requirements.txt
└── README.md
```

---

## 4. Entry Points and Call Flow

### 4.1 HTTP API (FastAPI)

**Entry point:** `src/main.py` → `app` (FastAPI instance)

**How it starts:** `uvicorn src.main:app --host 0.0.0.0 --port 8000`

**Flow:**

1. **Startup:** `lifespan` context manager runs:
   - `Base.metadata.create_all(bind=engine)` → creates DB tables
   - `seed()` → seeds default routing rules if none exist

2. **Router registration:** `app.include_router()` for:
   - `messages_router` → `/messages`
   - `rules_router` → `/rules`
   - `preferences_router` → `/preferences`

3. **Request handling:** FastAPI routes requests to the appropriate router module (e.g. `src.api.messages`).

### 4.2 Celery Worker

**Entry point:** `src.celery_app.py` → `app` (Celery instance)

**How it starts:** `celery -A src.celery_app worker -Q dispatch,celery -l info`

**Flow:**

1. Celery loads `src.celery_app` and discovers tasks in `src.tasks`.
2. `dispatch_message` is routed to the `dispatch` queue.
3. When a message is submitted via `POST /messages`, the API calls `dispatch_message.apply_async(args=[msg.id])`, which enqueues the task.
4. The worker picks up the task and executes `dispatch_message(message_id)` in `src/tasks.py`.

### 4.3 Call Flow Diagram

```
POST /messages
    → src.api.messages.submit_message()
        → src.db.get_db() (session)
        → src.models.orm_models.Message (create)
        → src.state.set_message_state()
        → src.tasks.dispatch_message.apply_async()

[Worker picks up task]
    → src.tasks.dispatch_message()
        → src.rules.engine.RulesEngine.decide_channels()
        → src.rules.router.Router.route()
        → src.tasks._create_delivery()
        → src.tasks._send_one()
            → src.channels.registry.get_available()
            → src.templates.get_body_content()
            → channel.send() (Mailjet or Twilio)
            → src.state.set_delivery_state()
```

---

## 5. File-by-File and Function-by-Function Explanation

### 5.1 `src/main.py`

**Purpose:** FastAPI application entry point. Registers routers and runs startup logic.

| Item | Purpose |
|------|---------|
| `lifespan(app)` | Async context manager. On startup: create DB tables, seed rules. On shutdown: (placeholder for cleanup). |
| `app` | FastAPI instance with title, description, version, lifespan. |
| `app.include_router(...)` | Mounts API routers for messages, rules, preferences. |
| `health()` | Endpoint `GET /health` for liveness checks. Returns `{"status": "ok"}`. |

---

### 5.2 `src/config.py`

**Purpose:** Centralized configuration from environment variables. Avoids hardcoding secrets.

| Item | Purpose |
|------|---------|
| `Settings` | Pydantic `BaseSettings` class. Loads from `.env` and env vars. `extra="ignore"` ignores unknown vars. |
| `database_url` | PostgreSQL connection string. Default for local dev. |
| `redis_url`, `celery_broker_url` | Redis URLs for Celery broker and result backend. |
| `twilio_*`, `mailjet_*` | Provider credentials. Optional; if missing, channels report "not configured". |
| `settings` | Singleton instance. Imported as `from src.config import settings`. |

---

### 5.3 `src/db.py`

**Purpose:** Database engine and session management. Provides `get_db` for FastAPI dependency injection.

| Item | Purpose |
|------|---------|
| `engine` | SQLAlchemy engine. Uses `StaticPool` and `check_same_thread=False` for SQLite (tests). |
| `SessionLocal` | Session factory bound to engine. `autocommit=False`, `autoflush=False`. |
| `get_db()` | Generator that yields a DB session. Used by FastAPI `Depends(get_db)`. Ensures session is closed after request. |

---

### 5.4 `src/models/orm_models.py`

**Purpose:** SQLAlchemy ORM models. Maps Python classes to database tables.

| Item | Purpose |
|------|---------|
| `Base` | Declarative base for all ORM models. |
| `MessageLifecycleState` | Enum: `pending`, `queued`, `dispatching`, `delivered`, `failed`, `dlq`. |
| `MessageType` | Enum: `critical_alert`, `promotion`, `transactional`, `notification`. |
| `Priority` | Enum: `low`, `normal`, `high`, `critical`. |
| `ChannelType` | Enum: `email`, `sms`. |
| `generate_uuid()` | Default for `external_id`. Returns UUID string for API clients. |
| `Message` | Table `messages`. Stores message metadata, type, priority, recipient, body template/context, state. `metadata_` maps to DB column `metadata` (reserved name). |
| `MessageDelivery` | Table `message_deliveries`. One row per channel attempt. Tracks channel, state, retry_count, provider_id, last_error. |
| `RoutingRule` | Table `routing_rules`. Conditions (JSON), channels, fallback_channels, max_retries. |
| `UserPreference` | Table `user_preferences`. Per-user, per-channel: enabled, quiet_hours, message_types_allowed. |

---

### 5.5 `src/models/schemas.py`

**Purpose:** Pydantic request/response schemas. Validates API input and shapes output.

| Item | Purpose |
|------|---------|
| `MessageType`, `Priority` | Enums for API validation. Matches ORM enums. |
| `MessageCreate` | Request body for `POST /messages`. Validates message_type, priority, body_template, body_context, recipient_id, recipient_email/phone. |
| `MessageStatusResponse` | Response for GET message. Includes id, external_id, state, deliveries, failure_reason. |
| `RoutingRuleCreate` | Request body for POST/PATCH rules. |

---

### 5.6 `src/models/__init__.py`

**Purpose:** Re-exports models and schemas for clean imports: `from src.models import Message, MessageCreate`.

---

### 5.7 `src/api/messages.py`

**Purpose:** Message submit and query endpoints.

| Function | Purpose |
|----------|---------|
| `submit_message(body, db)` | `POST /messages`. Validates at least one of recipient_email/phone. Creates Message, sets state to QUEUED, enqueues `dispatch_message`, returns external_id. |
| `get_message_status(external_id, db)` | `GET /messages/{external_id}`. Returns message status and deliveries. 404 if not found. |
| `list_messages(limit, state, db)` | `GET /messages`. Lists messages with optional state filter. |

---

### 5.8 `src/api/rules.py`

**Purpose:** CRUD for routing rules.

| Function | Purpose |
|----------|---------|
| `create_rule(body, db)` | `POST /rules`. Creates new RoutingRule. |
| `list_rules(db)` | `GET /rules`. Returns all rules ordered by priority_order. |
| `get_rule(rule_id, db)` | `GET /rules/{rule_id}`. Returns single rule. 404 if not found. |
| `update_rule(rule_id, body, db)` | `PATCH /rules/{rule_id}`. Updates all fields. |
| `delete_rule(rule_id, db)` | `DELETE /rules/{rule_id}`. Returns 204. |

---

### 5.9 `src/api/preferences.py`

**Purpose:** User channel preferences.

| Function | Purpose |
|----------|---------|
| `create_preference(body, db)` | `POST /preferences`. Creates or updates (upsert by user_id + channel). |
| `list_preferences(user_id, db)` | `GET /preferences/{user_id}`. Returns all preferences for user. |

---

### 5.10 `src/rules/engine.py`

**Purpose:** Rules engine. Evaluates which rule matches and filters channels by user preferences.

| Function | Purpose |
|----------|---------|
| `_parse_time(s)` | Converts "HH:MM" to minutes since midnight. Used for quiet hours and time windows. |
| `_current_minutes()` | Current UTC time as minutes since midnight. |
| `_in_quiet_hours(start, end)` | Returns True if current time is inside quiet hours. Handles wraparound (e.g. 22:00–08:00). |
| `_rule_conditions_match(conditions, context)` | Checks if rule conditions match. Supports message_types, priorities, time_window_start/end. |
| `_filter_by_user_preferences(db, user_id, channels, message_type)` | Filters channels by UserPreference: enabled, quiet hours, message_types_allowed. |
| `RulesEngine.get_matching_rule(...)` | Returns first matching active rule by priority_order. |
| `RulesEngine.decide_channels(...)` | Returns (primary_channels, fallback_channels, max_retries) after applying user preferences. |

---

### 5.11 `src/rules/router.py`

**Purpose:** Router. Combines rules engine output with recipient contact info.

| Item | Purpose |
|------|---------|
| `RoutingContext` | Dataclass: user_id, message_type, priority, recipient_email, recipient_phone, extra. |
| `RoutingDecision` | Dataclass: channels, fallback_channels, max_retries. |
| `Router.route(context)` | Calls RulesEngine.decide_channels, then filters channels by available contact (email for email channel, phone for SMS). Returns RoutingDecision. |

---

### 5.12 `src/channels/base.py`

**Purpose:** Abstract channel interface and registry for pluggable delivery channels.

| Item | Purpose |
|------|---------|
| `ChannelResult` | Dataclass: success, provider_id, error. Return value from send. |
| `Payload` | Dataclass: recipient, subject, body, template_context. |
| `ChannelBase` | Abstract base. Implement `name`, `send(payload)`, optionally `is_available()`. |
| `ChannelRegistry` | Registry of channels by name. `register(channel)`, `get(name)`, `get_available(name)` (returns only if configured). |

---

### 5.13 `src/channels/mailjet_channel.py`

**Purpose:** Email delivery via Mailjet API v3.1.

| Item | Purpose |
|------|---------|
| `MailjetChannel.name` | Returns `"email"`. |
| `MailjetChannel.is_available()` | True if `mailjet_api_key` and `mailjet_api_secret` are set. |
| `MailjetChannel.send(payload)` | POSTs to Mailjet API. Returns ChannelResult with provider_id on success. |

---

### 5.14 `src/channels/sms_channel.py`

**Purpose:** SMS delivery via Twilio.

| Item | Purpose |
|------|---------|
| `SMSChannel.name` | Returns `"sms"`. |
| `SMSChannel.is_available()` | True if Twilio credentials and from_number are set. |
| `SMSChannel.send(payload)` | Uses Twilio Client to send SMS. Returns ChannelResult with provider_id (msg.sid) on success. |

---

### 5.15 `src/channels/__init__.py`

**Purpose:** Creates ChannelRegistry, registers MailjetChannel and SMSChannel, exports `registry`.

---

### 5.16 `src/state.py`

**Purpose:** Message lifecycle state machine. Enforces valid transitions.

| Item | Purpose |
|------|---------|
| `TRANSITIONS` | Dict mapping current state to list of allowed next states. |
| `can_transition(current, next_state)` | Returns True if transition is allowed. |
| `set_message_state(db, message, new_state)` | Validates and sets message state. Raises ValueError if invalid. |
| `set_delivery_state(db, delivery, new_state)` | Same for MessageDelivery. |

---

### 5.17 `src/templates.py`

**Purpose:** Jinja2 template rendering for message body.

| Function | Purpose |
|----------|---------|
| `render_body(template_key, context)` | Renders template_key (e.g. "Hello {{ name }}") with context. Returns plain text if invalid Jinja. |
| `get_body_content()` | Alias for render_body. Used by tasks for clarity. |

---

### 5.18 `src/celery_app.py`

**Purpose:** Celery application configuration.

| Item | Purpose |
|------|---------|
| `app` | Celery instance. Broker and backend from config. |
| `include=["src.tasks"]` | Registers tasks from tasks module. |
| `task_acks_late=True` | Ack after task completes. Safer for retries. |
| `task_routes` | Routes `dispatch_message` to `dispatch` queue. `process_dlq` is configured but not implemented (placeholder). |

---

### 5.19 `src/tasks.py`

**Purpose:** Celery tasks. Main logic for async message dispatch.

| Function | Purpose |
|----------|---------|
| `_get_routing_decision(db, message)` | Builds RulesEngine + Router, creates RoutingContext, returns (channels, fallback_channels, max_retries). |
| `_create_delivery(db, message_id, channel, max_retries)` | Creates MessageDelivery row. |
| `_send_one(db, message, delivery)` | Gets channel from registry, renders body, sends via channel.send(). Updates delivery state and last_error. Returns True if success. |
| `dispatch_message(self, message_id)` | Main task. Loads message, gets routing decision, creates deliveries for primary channels, sends each. If all fail, tries fallback channels. If still fails, retries (re-enqueue) or moves to DLQ after max_retries. |

---

### 5.20 `src/seed_rules.py`

**Purpose:** Seeds default routing rules on first run.

| Item | Purpose |
|------|---------|
| `DEFAULT_RULES` | List of 4 rule dicts: Critical alerts, Promotions, Transactional, Default. |
| `seed()` | If no rules exist, inserts DEFAULT_RULES. Called from main.py lifespan. |
| `if __name__ == "__main__"` | Allows running `python -m src.seed_rules` manually. |

---

### 5.21 Tests `tests/`

| File | Purpose |
|------|---------|
| `conftest.py` | Sets `DATABASE_URL` to SQLite in-memory. Fixtures: `db` (session), `client` (TestClient with overridden get_db). |
| `test_api.py` | Tests message submit, status, list. |
| `test_preferences.py` | Tests preference filtering in rules engine. |
| `test_retry_behavior.py` | Tests retry count increment and DLQ after max retries. |
| `test_rules_engine.py` | Tests rule matching, conditions, user preferences. |
| `test_state.py` | Tests state machine transitions. |
| `test_templates.py` | Tests Jinja2 rendering. |

---

## 6. Summary

- **Entry points:** `src/main.py` (API), `src.celery_app` (worker).
- **Flow:** API → DB → Celery → RulesEngine → Router → ChannelRegistry → Mailjet/Twilio.
- **Key design:** Policy in DB (rules, preferences), pluggable channels, per-channel delivery records, state machine for lifecycle.
