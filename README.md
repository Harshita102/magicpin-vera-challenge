# Vera Merchant AI Assistant — Submission

## Approach
A deterministic, trigger-aware composer built around the challenge's four contexts: **Category + Merchant + Trigger + optional Customer**. The bot retrieves only the context relevant to each event, then dispatches to a trigger-family handler (research, compliance, performance, milestone, seasonal, competitor, customer recall/refill/appointment, etc.).

The message strategy prioritizes: (1) concrete facts from the payload, (2) category-appropriate operator voice, (3) merchant/customer-specific state, (4) a clear “why now”, and (5) one low-friction next step. It deliberately avoids invented offers, citations, slots, competitors, or performance claims.

Multi-turn handling detects repeated WhatsApp-style canned auto-replies, exits after a limited routing attempt, detects explicit action intent (“yes”, “go ahead”, “join”, etc.) and moves directly to action instead of re-qualifying, and respects negative/STOP signals.

## Tradeoffs
I chose deterministic composition over a mandatory external LLM dependency so the bot is fast, reproducible, context-grounded, and resilient to API latency/rate limits. The tradeoff is less linguistic variety than a strong LLM; trigger-specific templates and context retrieval are used to compensate.

## Additional context that would help
For customer-facing triggers, real appointment/service details and explicit consent scopes would allow even more precise messages. For merchant-facing actions, an authoritative source of executable actions (e.g. whether Vera can actually publish a GBP post, create an offer, or register an event) would improve the action handoff.
