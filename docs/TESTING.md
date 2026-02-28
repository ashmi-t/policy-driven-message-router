# How to Test the Message Router

With the app running (e.g. `docker compose up -d`) and docs at **http://localhost:8000/docs**, follow these steps.

---

## 1. Seed rules (if needed)

Default routing rules are **seeded automatically on app startup**. If you just started the stack, skip to step 2.

To seed again manually (e.g. after clearing the DB):

```bash
docker compose run --rm app python -m src.seed_rules
```

---

## 2. Submit a message

In **http://localhost:8000/docs**:

1. Open **POST /messages** → **Try it out**.
2. Use this body (or edit as you like):

```json
{
  "message_type": "promotion",
  "priority": "normal",
  "body_template": "Hello {{ name }}, here is your offer!",
  "body_context": {"name": "Alice"},
  "recipient_id": "user-123",
  "recipient_email": "your-email@example.com",
  "recipient_phone": "+15551234567"
}
```

3. Click **Execute**. You should get **200** and a response like:

```json
{
  "id": "some-uuid",
  "status": "queued",
  "message_id": 1
}
```

Copy the `id` (external_id) for the next step.

---

## 3. Check message status

1. Open **GET /messages/{external_id}**.
2. Paste the `id` from step 2 into **external_id**.
3. Click **Execute**.

You'll see the message **state** (`queued` → `dispatching` → `delivered` or `failed`/`dlq`) and a **deliveries** list (per channel).

- **Without Twilio/Mailjet**: delivery will fail (channels "not configured"), and after retries the message may go to **dlq**. The flow (submit → route → try channels → retry → DLQ) is still visible.
- **With Twilio/Mailjet** in `.env`: real SMS/email are sent and state can reach **delivered**.

---

## 4. List messages

- **GET /messages** – list recent messages.
- **GET /messages?state=delivered** – filter by state (`queued`, `dispatching`, `delivered`, `failed`, `dlq`).

---

## 5. CRUD operations – example JSON

### Messages

**POST /messages** – submit a message (Create). See step 2 above for the full example. Key fields: `message_type`, `priority`, `body_template`, `body_context`, `recipient_id`, `recipient_email` or `recipient_phone`.

**GET /messages/{external_id}** – get one message (Read). Path param: `external_id` (UUID). Example response:

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "external_id": "550e8400-e29b-41d4-a716-446655440000",
  "state": "delivered",
  "message_type": "promotion",
  "priority": "normal",
  "created_at": "2025-02-28T12:00:00",
  "deliveries": [
    {"id": 1, "channel": "email", "state": "delivered", "retry_count": 0, "provider_id": "abc123", "last_error": null}
  ],
  "failure_reason": null
}
```

**GET /messages** – list messages. Query params: `?limit=50`, `?state=delivered`. Returns array of the same shape. States: `queued`, `dispatching`, `delivered`, `failed`, `dlq`.

---

### Rules

**POST /rules** – create a rule (Create)

```json
{
  "name": "High-priority alerts: SMS + Email",
  "priority_order": 0,
  "active": true,
  "conditions": {
    "message_types": ["critical_alert"],
    "priorities": ["critical", "high"]
  },
  "channels": ["sms", "email"],
  "fallback_channels": ["email"],
  "max_retries": 5
}
```

Example response: `{"id": 1, "name": "High-priority alerts: SMS + Email"}`

**GET /rules** – list all rules. Returns array of rule objects (see GET one).

**GET /rules/{rule_id}** – get one rule. Path param: `rule_id` (integer). Example response:

```json
{
  "id": 1,
  "name": "High-priority alerts: SMS + Email",
  "priority_order": 0,
  "active": true,
  "conditions": {"message_types": ["critical_alert"], "priorities": ["critical", "high"]},
  "channels": ["sms", "email"],
  "fallback_channels": ["email"],
  "max_retries": 5
}
```

**PATCH /rules/{rule_id}** – update a rule (Update)

```json
{
  "name": "Updated rule name",
  "priority_order": 5,
  "active": true,
  "conditions": {"message_types": ["notification"]},
  "channels": ["email"],
  "fallback_channels": ["sms"],
  "max_retries": 3
}
```

Example response: `{"id": 1, "name": "Updated rule name"}`

**DELETE /rules/{rule_id}** – delete a rule. Path param: `rule_id`. No body, returns 204.

---

### Preferences

**POST /preferences** – create or update preference (Create/Update)

```json
{
  "user_id": "user-123",
  "channel": "email",
  "enabled": true,
  "quiet_hours_start": "22:00",
  "quiet_hours_end": "08:00",
  "message_types_allowed": ["promotion", "transactional"]
}
```

- `channel`: `email` | `sms`
- `quiet_hours_start` / `quiet_hours_end`: `"HH:MM"` format
- `message_types_allowed`: empty list = allow all types for this channel

Example response: `{"id": 1, "user_id": "user-123", "channel": "email"}`

**GET /preferences/{user_id}** – list preferences for a user. Path param: `user_id`. Example response:

```json
[
  {"id": 1, "user_id": "user-123", "channel": "email", "enabled": true, "quiet_hours_start": "22:00", "quiet_hours_end": "08:00", "message_types_allowed": ["promotion", "transactional"]}
]
```

Submit a message with `recipient_id: "user-123"` to see routing respect preferences.

---

## 6. Test different message types

| message_type     | Expected behavior (with default rules)      |
|------------------|---------------------------------------------|
| `critical_alert` | SMS + Email (if phone/email provided)       |
| `promotion`      | Email only                                  |
| `transactional` | Email, fallback SMS                         |
| `notification`  | Default rule: Email, fallback SMS           |

Use **POST /messages** with different `message_type` and **GET /messages/{id}** to confirm the right channels are used.

---

## 7. Optional: run tests (outside Docker)

```bash
export DATABASE_URL=sqlite:///:memory:?check_same_thread=0
pytest tests/ -v
```
