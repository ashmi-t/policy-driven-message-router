# Data Model / Database Schema

## Overview

The system uses **PostgreSQL** (or SQLite for tests) with the following main entities:

- **Message**: A single outbound message to be routed and delivered.
- **MessageDelivery**: One delivery attempt on one channel (Email or SMS) for a message.
- **RoutingRule**: A policy that maps conditions to channels and retry behavior.
- **UserPreference**: Per-user, per-channel preferences (enabled, quiet hours, message types).

---

## Tables

### `messages`

| Column           | Type         | Description |
|-----------------|--------------|-------------|
| id              | INTEGER PK   | Internal ID. |
| external_id     | VARCHAR(36)  | UUID for API (e.g. GET /messages/{external_id}). |
| message_type    | VARCHAR(32)  | One of: `critical_alert`, `promotion`, `transactional`, `notification`. |
| priority        | VARCHAR(16)  | One of: `low`, `normal`, `high`, `critical`. |
| subject         | VARCHAR(512) | Optional subject (e.g. for email). |
| body_template    | VARCHAR(128) | Template string or key (Jinja2). |
| body_context    | JSON         | Variables for template rendering. |
| recipient_id    | VARCHAR(128) | User identifier for preference lookup. |
| recipient_email | VARCHAR(256) | Email address (optional). |
| recipient_phone | VARCHAR(32)  | E.164 phone (optional). |
| state           | VARCHAR(32)  | Lifecycle: `pending`, `queued`, `dispatching`, `delivered`, `failed`, `dlq`. |
| metadata        | JSON         | Extra context for routing. |
| created_at      | TIMESTAMP    | Creation time. |
| updated_at      | TIMESTAMP    | Last update. |

**Indexes**: `external_id` (unique).

---

### `message_deliveries`

| Column      | Type        | Description |
|-------------|-------------|-------------|
| id          | INTEGER PK  | Internal ID. |
| message_id  | INTEGER FK  | References `messages.id`. |
| channel     | VARCHAR(32) | `email` or `sms`. |
| state       | VARCHAR(32) | Same lifecycle as message (pending → dispatching → delivered/failed). |
| retry_count | INTEGER     | Number of retries so far. |
| max_retries | INTEGER     | Max retries (from rule). |
| last_error  | TEXT        | Last failure reason. |
| provider_id | VARCHAR(256)| External ID from Mailjet/Twilio. |
| created_at  | TIMESTAMP   | Creation time. |
| updated_at  | TIMESTAMP   | Last update. |

**Relations**: One message has many deliveries (one per channel attempt).

---

### `routing_rules`

| Column             | Type         | Description |
|--------------------|--------------|-------------|
| id                 | INTEGER PK   | Internal ID. |
| name               | VARCHAR(128) | Human-readable name. |
| priority_order     | INTEGER      | Lower = evaluated first. |
| active             | BOOLEAN      | If false, rule is skipped. |
| conditions         | JSON         | Conditions (see below). |
| channels           | JSON         | List of channel names, e.g. `["email", "sms"]`. |
| fallback_channels  | JSON         | Channels to try if primary fail, e.g. `["email"]`. |
| max_retries        | INTEGER      | Retries before moving to DLQ. |
| created_at         | TIMESTAMP    | Creation time. |
| updated_at         | TIMESTAMP    | Last update. |

**Conditions** (JSON) may include:

- `message_types`: list of allowed message types.
- `priorities`: list of allowed priorities.
- `time_window_start` / `time_window_end`: optional "HH:MM" for allowed window.

---

### `user_preferences`

| Column                 | Type         | Description |
|------------------------|--------------|-------------|
| id                     | INTEGER PK   | Internal ID. |
| user_id                | VARCHAR(128) | User identifier (indexed). |
| channel                | VARCHAR(32)  | `email` or `sms`. |
| enabled                | BOOLEAN      | If false, this channel is not used for this user. |
| quiet_hours_start       | VARCHAR(5)   | "HH:MM" start of quiet period. |
| quiet_hours_end         | VARCHAR(5)   | "HH:MM" end of quiet period. |
| message_types_allowed  | JSON         | List of message types allowed on this channel; empty = all. |
| created_at             | TIMESTAMP    | Creation time. |
| updated_at             | TIMESTAMP    | Last update. |

---

## Entity relationship (conceptual)

```
Message 1───* MessageDelivery
   │
   └── state machine: pending → queued → dispatching → delivered | failed | dlq

RoutingRule: conditions → channels, fallback_channels, max_retries
UserPreference: user_id + channel → enabled, quiet_hours, message_types_allowed
```

Routing uses **RoutingRule** to choose channels and **UserPreference** to filter which of those channels are allowed for the recipient.
