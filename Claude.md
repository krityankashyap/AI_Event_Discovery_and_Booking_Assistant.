# CLAUDE.md: Event Discovery Agent (FastAPI + LangChain + Ticketmaster + HITL)

Conversational agent that finds real events via the Ticketmaster Discovery API, keeps context across turns, and pauses for human approval before handing the user a real Ticketmaster purchase URL. Graded on correctness of the mandatory flow, code quality, and error handling. Build it like a shippable product, not a demo.

## Stack (do not swap without asking)

- Python 3.12, `uv` for deps. Also export `requirements.txt` (graders expect it).
- Backend: FastAPI (async), Pydantic v2, `httpx.AsyncClient`, `pydantic-settings`.
- Agent: LangChain 1.x `create_agent` + LangGraph (`langchain>=1.3`, `langgraph>=1.2`). Checkpointer: `InMemorySaver`.
- LLM: provider abstraction, `LLM_PROVIDER=groq|openai`. Default Groq `openai/gpt-oss-120b` via `langchain-groq`.
- Frontend: React + Vite + TypeScript + Tailwind.
- Tests: pytest, pytest-asyncio, respx (mock Ticketmaster). Lint/format: ruff.

## Commands

```bash
uv sync                                                    # install
uv run uvicorn backend.main:app --reload --port 8000       # backend
uv run pytest -q                                           # tests
uv run ruff check . && uv run ruff format --check .        # lint
uv export --no-hashes --format requirements-txt > requirements.txt
cd frontend && npm install && npm run dev                  # frontend (port 5173)
cd frontend && npm run build && npm run lint
```

Always run from repo root. Use package imports (`from backend.services.ticketmaster import ...`). Never `sys.path.insert`.

## Structure (follows the assignment; keep these names)

```
backend/
  main.py              # app factory, CORS, lifespan (httpx client, agent), exception handlers
  config.py            # Settings (pydantic-settings), reads .env
  agent.py             # build_agent(): model + tools + middleware + checkpointer
  api/routes.py        # /chat /approve /reject /health /sessions/{id} /events/{id}
  tools/event_tools.py # search_events, get_event_details, request_booking
  tools/venue_tools.py # search_venues, get_venue_details
  services/ticketmaster.py  # ONLY place that talks HTTP to Ticketmaster
  services/sessions.py # session registry, per-session asyncio.Lock, TTL cleanup
  models/schemas.py    # API request/response + normalized Event/Venue models
  prompts/system_prompt.py  # build_system_prompt(now) -> str
  errors.py            # domain exceptions -> HTTP status mapping
tests/
frontend/src/{components,services,App.tsx,main.tsx}
```

## Architecture rules

**Layering.** routes -> agent runtime -> tools -> `TicketmasterService`. Tools never build URLs or call httpx directly. Routes never call Ticketmaster except `GET /events/{id}`.

**Ticketmaster service.**
- Base `https://app.ticketmaster.com/discovery/v2`. Endpoints: `/events.json`, `/events/{id}.json`, `/venues.json`, `/venues/{id}.json`. API key as `apikey` query param, from settings only.
- Datetimes: `YYYY-MM-DDTHH:mm:ssZ` (UTC, no millis). Validate `end >= start`.
- Useful params: `keyword`, `city`, `countryCode`, `classificationName` (music, sports, comedy, soccer...), `startDateTime`, `endDateTime`, `size` (cap 20), `sort=date,asc`.
- Limits: 5 req/s, 5000/day. Shared `AsyncClient` (timeout 10s), retry 2x with backoff on 429/5xx/timeouts only, small TTL cache (60s) on identical queries.
- Normalize raw JSON into `Event` model: `id, name, url, local_date, local_time, status, venue_name, city, country, segment, genre, price_min, price_max, currency, image_url`. `priceRanges` is often missing: keep `None`, never invent prices.
- Map failures to domain errors: `TicketmasterUnavailable` (5xx/timeout/network), `TicketmasterRateLimited` (429), `TicketmasterAuthError` (401/403), `EventNotFound` (404).

**Tools** (custom `@tool`, hand-written; no prebuilt Ticketmaster toolkits).
- Clear docstrings: the LLM reads them. Typed args with Pydantic `args_schema` where useful.
- Use `response_format="content_and_artifact"`: content = compact numbered text for the LLM (`1. [id=...] Name | date time | venue, city | price or "price not listed"`), artifact = list of normalized `Event` dicts. The API reads artifacts from this turn's `ToolMessage`s to render cards. The UI must never depend on the LLM re-typing data.
- Tools catch domain errors and return a short, user-safe message (e.g. "No events found for ..."), so the agent can explain and recover. Never return exception objects or tracebacks.
- `request_booking(event_id)`: the ONLY tool gated by HITL. On execution it re-fetches the event and returns its `url` as the artifact. The booking URL must come from the API response, never from the model.

**Agent.**
- `create_agent(model, tools, system_prompt, middleware, checkpointer)`; `thread_id = session_id`.
- Middleware order: `ModelCallLimitMiddleware(run_limit=8, exit_behavior="end")`, audit/logging middleware, `HumanInTheLoopMiddleware(interrupt_on={"request_booking": {"allowed_decisions": ["approve", "reject"], "description": ...}})`. Every other tool: not interrupted.
- System prompt is built per request with the current date, weekday, and timezone so "this weekend", "next Friday", "in October" resolve correctly. Rules in the prompt: always call tools for event data; resolve "the second one"/"number 1"/"cheapest" against the most recent results list; if prices are missing, say so; call `request_booking` only when the user clearly chooses an event; never output a purchase URL unless it came from `request_booking`.

**HITL over HTTP.**
- Invoke with `await agent.ainvoke(input, config, version="v2")`; result is `GraphOutput` with `.value` and `.interrupts`.
- If `.interrupts` is non-empty: respond `status="awaiting_approval"` with an `approval` payload built from `action_requests[0]` + event details (name, date, venue, price) for a rich approval card.
- `/approve`: `Command(resume={"decisions": [{"type": "approve"}]})`. `/reject`: `Command(resume={"decisions": [{"type": "reject", "message": "User declined the booking. Acknowledge and offer alternatives. Do not retry."}]})`. Key is `decisions` (plural), one decision per pending action request.
- Before resuming, check pending state with `agent.aget_state(config)`; no pending interrupt -> 409.
- One turn at a time per session: per-session `asyncio.Lock`; concurrent request -> 409.

**API contract.**
- `POST /chat {session_id?: str, message: str (1..1000 chars)}` -> `ChatResponse {session_id, status: "completed"|"awaiting_approval", message, events?: Event[], approval?: ApprovalRequest, booking_url?: str}`
- `POST /approve {session_id}` and `POST /reject {session_id, reason?}` -> `ChatResponse`
- `GET /health` (liveness + config sanity, no secrets), `GET /sessions/{id}`, `DELETE /sessions/{id}`, `GET /events/{id}`
- Status codes: 400/422 bad input, 404 unknown session/event, 409 no pending approval or turn in progress, 429 upstream rate limit, 502 Ticketmaster error, 503 LLM unavailable, 504 timeout. Body: `{"error": {"code": "...", "message": "user-safe text"}}`. Global handler logs the traceback server-side and returns a generic 500 message. Never leak raw exceptions.

**Frontend.**
- Chat thread, event cards (image, name, date/time, venue, price or "Price not listed", details button), approval card with Approve/Reject (disabled while in flight), booking button `target="_blank" rel="noopener noreferrer"`.
- `session_id` persisted in `localStorage`; "New chat" calls `DELETE /sessions/{id}`.
- Typed API client in `services/api.ts`, base URL from `VITE_API_BASE_URL`. Loading, empty, and error states everywhere; show `error.message`, never raw responses.
- Responsive, accessible (labels, focus states, keyboard submit).

## Config (.env, never committed)

```
TICKETMASTER_API_KEY=
LLM_PROVIDER=groq
GROQ_API_KEY=
OPENAI_API_KEY=
LLM_MODEL=openai/gpt-oss-120b
ALLOWED_ORIGINS=http://localhost:5173
DEFAULT_TIMEZONE=UTC
LOG_LEVEL=INFO
```

Commit `.env.example` with empty values. `.gitignore` must include `.env`, `.venv/`, `__pycache__/`, `node_modules/`, `dist/`, `*.log`. Fail fast at startup if required keys are missing.

## Known pitfalls (bugs found in our previous LangChain agent; do not repeat)

- HITL resume payload key is `decisions`, not `decision`.
- `interrupt_on` keys must exactly match tool names (a typo silently disables the gate).
- Every `wrap_tool_call` middleware must return the handler's result on every path. Returning `None` breaks the graph.
- A short-circuit `ToolMessage` must include `tool_call_id=request.tool_call["id"]`.
- Tools return strings/artifacts; never `return ValueError(...)`.
- Template/prompt variable names must match between caller and template.
- `return` inside a loop by accident (only first item processed). Check loops.
- Use `datetime.now(UTC)`, not `datetime.utcnow()`.
- Pydantic field names must match what the prompt tells the model to fill.

## Code standards

- Full type hints, small functions, no dead code, no commented-out code, no `print` (use `logging` with request id + session id).
- Async end to end. No blocking calls in request handlers.
- Secrets never logged, never returned, never sent to the frontend.
- Validate all input with Pydantic. Trim and length-limit user messages.
- Write tests alongside features: service normalization and error mapping (respx), tool outputs, API routes including 404/409/502 paths, and the HITL approve/reject flow with a stubbed agent.

## Definition of done (mandatory scenario must pass end to end)

1. "Find concerts happening in London this weekend" -> real results rendered as cards.
2. "Tell me more about the second event" -> details of the correct event.
3. "Which one is cheapest?" -> correct answer or honest "prices not listed".
4. "I want to book number 1" -> `awaiting_approval`, UI shows Approve/Reject.
5. Approve -> agent resumes -> real Ticketmaster URL from the API, shown as a button.
6. Reject path acknowledged; errors (no results, bad city, API down, LLM down) show friendly messages with correct HTTP codes.
7. README: setup, env vars, architecture diagram, API table, HITL sequence, screenshots, known limitations (in-memory sessions, single worker).

## Workflow

- Plan before coding for any change touching more than 2 files. Work in small, verifiable steps and run tests/lint after each.
- If an API detail is uncertain (LangChain signature, Ticketmaster field), check the installed package source or docs; do not guess.
- Conventional commits (`feat:`, `fix:`, `test:`, `docs:`). Never commit `.env`.