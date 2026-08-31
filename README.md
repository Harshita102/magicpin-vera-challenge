# Vera Merchant AI Assistant — Submission

A deterministic, context-aware AI assistant backend built for the Vera Challenge.

## Live API

**Base URL:**  
https://magicpin-vera-challenge-v1yt.onrender.com

**Swagger / OpenAPI Docs:**  
https://magicpin-vera-challenge-v1yt.onrender.com/docs

## API Endpoints

- `GET /v1/healthz` — Health check
- `GET /v1/metadata` — Project metadata
- `POST /v1/context` — Push category, merchant, and customer context
- `POST /v1/tick` — Process available triggers
- `POST /v1/reply` — Generate a deterministic reply

## Approach

A deterministic, trigger-aware composer built around the challenge's four contexts:

**Category + Merchant + Trigger + optional Customer**

The bot retrieves only the context relevant to each event and dispatches it to a trigger-family handler such as research, compliance, performance, milestone, seasonal, competitor, customer recall, refill, and appointment.

The message strategy prioritizes:

1. Concrete facts from the payload
2. Category-appropriate operator voice
3. Merchant/customer-specific state
4. A clear "why now"
5. One low-friction next step

The implementation deliberately avoids invented offers, citations, slots, competitors, or performance claims.

### Multi-turn Handling

The assistant detects repeated WhatsApp-style canned auto-replies, exits after a limited routing attempt, detects explicit action intent such as "yes", "go ahead", and "join", and moves directly to action instead of repeatedly re-qualifying the user.

It also respects negative and STOP signals.

## Tradeoffs

I chose deterministic composition over a mandatory external LLM dependency so the bot is fast, reproducible, context-grounded, and resilient to API latency and rate limits.

The main tradeoff is less linguistic variety than a strong LLM. Trigger-specific templates and context retrieval are used to compensate while keeping the system predictable and reliable.

## Additional Context That Would Help

For customer-facing triggers, real appointment or service details and explicit consent scopes would allow even more precise messages.

For merchant-facing actions, an authoritative source of executable actions — such as whether Vera can actually publish a GBP post, create an offer, or register an event — would improve the action handoff.

## API Verification

All required API endpoints were deployed and tested successfully using the Swagger/OpenAPI interface.

### Health Check

`GET /v1/healthz` → **200 OK**

### Metadata

`GET /v1/metadata` → **200 OK**

### Context

`POST /v1/context` → **200 OK**

### Tick

`POST /v1/tick` → **200 OK**

### Reply

`POST /v1/reply` → **200 OK**

## Screenshots

Screenshots of the successful deployment and API tests are included in this repository as verification evidence.

The screenshots demonstrate successful responses for:

- Health check
- Metadata
- Context submission
- Trigger processing
- Reply generation

## Deployment

The application is deployed on Render and is publicly accessible through the live API base URL:

https://magicpin-vera-challenge-v1yt.onrender.com

## Project Structure

```text
magicpin-vera-challenge/
├── bot.py
├── requirements.txt
├── submission.json
├── README.md
├── Vera Merchant.AI Assistant.png
├── Healthz.png
├── MetaData.png
├── Context-execute.png
├── context-200-ok.png
├── healthz-200-ok.png
├── metadata-200-ok.png
├── reply-200-ok.png
├── reply-execute.png
├── tick-200-ok.png
└── tick-execute.png
