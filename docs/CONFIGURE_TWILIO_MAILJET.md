# Configure Twilio (SMS) and Mailjet (Email)

To send real SMS and email, add credentials and pass them into the app and worker. **Email** is sent via **Mailjet** only.

---

## 1. Create a `.env` file

Docker Compose is configured to load `.env` for the app and worker. If the file is missing, `docker compose up` will fail.

From the project root:

```bash
cp .env.example .env
```

Edit `.env` and add the variables below. Save the file and restart:

```bash
docker compose up -d --force-recreate app worker
```

---

## 2. Twilio (SMS)

### Get credentials

1. Sign up at [twilio.com](https://www.twilio.com/try-twilio) (free trial gives credit).
2. In the [Twilio Console](https://console.twilio.com/):
   - **Account SID** and **Auth Token** are on the dashboard.
   - **Phone number**: go to **Phone Numbers → Manage → Buy a number** (trial can use one number).
3. Note the number in E.164 form (e.g. `+15551234567`).

### Add to `.env`

```env
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_FROM_NUMBER=+15551234567
```

Replace with your real values. **Do not commit `.env`** (it should be in `.gitignore`).

---

## 3. Mailjet (Email)

### Get credentials

1. Sign up at [mailjet.com](https://www.mailjet.com/) (free tier available).
2. In [Mailjet Account](https://app.mailjet.com/account/api_key): copy **API Key** and **Secret Key**.
3. Use a verified sender (from your domain or a single sender you verified in Mailjet).

### Add to `.env`

```env
MAILJET_API_KEY=your_api_key
MAILJET_API_SECRET=your_api_secret
MAILJET_FROM_EMAIL=your-sender@example.com
MAILJET_FROM_NAME=Message Router
```

**Do not commit `.env`**.

---

## 4. Load `.env` in Docker

The app and worker read these from the environment. With Docker Compose you have two options.

### Option A: Use `env_file` (recommended)

Ensure `.env` exists (e.g. `cp .env.example .env` and edit). The Compose file is set to load it. Restart so containers pick up the file:

```bash
docker compose up -d --force-recreate app worker
```

### Option B: Pass variables when starting

```bash
export TWILIO_ACCOUNT_SID=ACxxx
export TWILIO_AUTH_TOKEN=xxx
export TWILIO_FROM_NUMBER=+15551234567
export MAILJET_API_KEY=xxx
export MAILJET_API_SECRET=xxx
export MAILJET_FROM_EMAIL=noreply@example.com
docker compose up -d
```

---

## 5. Verify

1. **POST /messages** with:
   - `recipient_phone`: your real phone (E.164) for SMS.
   - `recipient_email`: your real email for email.
2. **GET /messages/{id}** and check `state` and `deliveries`; you should see `delivered` when providers are configured and the message is sent.

---

## Summary of env vars

| Variable | Required for | Description |
|----------|----------------|-------------|
| `TWILIO_ACCOUNT_SID` | SMS | Twilio account SID |
| `TWILIO_AUTH_TOKEN` | SMS | Twilio auth token |
| `TWILIO_FROM_NUMBER` | SMS | Twilio number (E.164, e.g. +15551234567) |
| `MAILJET_API_KEY` | Email | Mailjet API key |
| `MAILJET_API_SECRET` | Email | Mailjet secret key |
| `MAILJET_FROM_EMAIL` | Email | Sender email |
| `MAILJET_FROM_NAME` | Email | Sender display name |

If a provider is not configured, that channel will report "not configured" and the message may use other channels or go to DLQ after retries.
