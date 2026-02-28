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

You’ll see the message **state** (`queued` → `dispatching` → `delivered` or `failed`/`dlq`) and a **deliveries** list (per channel).

- **Without Twilio/Mailjet**: delivery will fail (channels “not configured”), and after retries the message may go to **dlq**. The flow (submit → route → try channels → retry → DLQ) is still visible.
- **With Twilio/Mailjet** in `.env`: real SMS/email are sent and state can reach **delivered**.

---

## 4. List messages

- **GET /messages** – list recent messages.
- **GET /messages?state=delivered** – filter by state (`queued`, `dispatching`, `delivered`, `failed`, `dlq`).

---

## 5. Rules and preferences

- **GET /rules** – list routing rules (e.g. “Critical alerts: SMS + Email”, “Promotions: Email only”).
- **POST /rules** – create a new rule (conditions, channels, fallback, max_retries).
- **POST /preferences** – set user channel preferences (e.g. disable SMS, set quiet hours).

Example: create a preference so `user-123` only gets email:

```json
POST /preferences
{
  "user_id": "user-123",
  "channel": "email",
  "enabled": true
}
```

Then submit a message with `recipient_id: "user-123"` and see routing respect it.

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
