# Voice AI Patient Registration System

A phone-based patient intake agent. Callers speak naturally to a voice AI (built on
Vapi), which collects standard US patient demographics, confirms the record back to
them, and saves it through a FastAPI + SQLite backend. A companion REST API and a
tiny dashboard let you query what's been registered.

```
Phone Call ↔ Vapi (STT/TTS/telephony + GPT-4o) ↔ FastAPI webhook ↔ SQLite ↔ REST API ↔ Dashboard
```

## What's in this repo

```
app/
  main.py            FastAPI app: wires routers, creates tables, mounts dashboard
  models.py           SQLAlchemy Patient model
  schemas.py           Pydantic validation (the real server-side validation layer)
  crud.py              DB read/write functions
  responses.py         {"data": ..., "error": ...} envelope helper
  logging_config.py    stdout logging setup
  routers/
    patients.py        REST API: GET/POST/PUT/DELETE /patients
    vapi.py             Webhooks Vapi calls: tool-calls + end-of-call-report
vapi/
  system_prompt.md     The full, documented system prompt for the voice agent
  assistant_config.json Vapi assistant definition (model, voice, tools, webhooks)
scripts/
  setup_vapi.py         Optional: create the assistant via the Vapi API instead of the dashboard
static/index.html       Bonus: a read-only patient dashboard
tests/test_patients_api.py  10 integration tests against the REST API
seed_data.py             Creates 2 demo patients
```

## Tech stack, and why

| Layer | Choice | Why |
|---|---|---|
| Telephony + voice | **Vapi** | Abstracts STT/TTS/telephony entirely — you configure a system prompt, function tools, and a webhook URL, and get a real dialable number in minutes. This is what the assessment itself recommends as "the fastest path to a working system." |
| LLM | **GPT-4o** (via Vapi) | Vapi's most battle-tested model choice for tool-calling reliability during live calls; swappable to Claude/Gemini with a one-line config change. |
| Backend | **Python + FastAPI** | Async-friendly, Pydantic validation is built in, automatic OpenAPI docs at `/docs` for free. |
| Database | **SQLite** | Explicitly sanctioned by the brief as the right shortcut for this scope. Zero setup, file-based, survives restarts. The code is pure SQLAlchemy ORM with no SQLite-specific SQL, so swapping `DATABASE_URL` to Postgres is a one-line change (see `app/database.py`). |
| Hosting | **Railway** (recommended) or **ngrok** for local dev | Free tier, git-push deploys, persistent disk for the SQLite file. |

## How the voice agent actually talks to the database

Vapi doesn't call your REST API directly from the LLM — it calls a **webhook** you
own with a `tool-calls` message whenever the assistant invokes a function. This app
implements that webhook at `POST /vapi/tool-calls` (see `app/routers/vapi.py`),
which:

1. Reads the tool name (`lookup_patient_by_phone`, `register_patient`, or
   `update_patient`) and its arguments straight from Vapi's `toolCallList` payload.
2. Runs the *same* Pydantic validation and CRUD functions the REST API uses — there
   is exactly one validation layer and one database layer in this codebase, shared by
   both entry points.
3. Returns a plain-string result (`SUCCESS ...`, `VALIDATION_ERROR: <field>: <reason>`,
   or `FOUND_EXISTING ...`) that the LLM reads and turns into natural speech, per
   Vapi's [Custom Tools contract](https://docs.vapi.ai/tools/custom-tools).

A second webhook, `POST /vapi/call-events`, receives Vapi's `end-of-call-report`
event and logs the final call summary to stdout (the observability requirement),
attaching it to the patient record it produced (the transcript-linking bonus).

## Setup — from scratch

You said you're starting with no accounts, so here's the full path.

### 1. Get the code running locally

```bash
git clone <your-repo-url>
cd patient-voice-agent
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                 # defaults work as-is for local dev
python seed_data.py                                   # creates 2 demo patients
uvicorn app.main:app --reload
```

Visit `http://localhost:8000/docs` for interactive API docs, and
`http://localhost:8000/dashboard` for the patient list.

Run the tests: `pytest -v` (10 tests, all against a throwaway SQLite file).

### 2. Deploy it somewhere public (Vapi needs a real HTTPS URL to call)

**Fastest for a first test — ngrok (no deploy, runs on your machine):**
```bash
# terminal 1
uvicorn app.main:app --reload
# terminal 2
ngrok http 8000
```
Copy the `https://xxxx.ngrok-free.app` URL ngrok prints — that's your `PUBLIC_BASE_URL`.
Downside: it dies when you close the terminal, so it's fine for testing but not for
"the reviewer calls it two days later."

**For something that stays up — Railway:**
1. Sign up at [railway.app](https://railway.app) (free tier is enough for this).
2. New Project → Deploy from GitHub repo → pick this repo.
3. Add a **Volume** mounted at `/app/data` so the SQLite file survives redeploys —
   without this, Railway's filesystem resets on every deploy and you'll lose data.
4. Set environment variables from `.env.example` in Railway's dashboard (at minimum
   `VAPI_WEBHOOK_SECRET`; leave `DATABASE_URL` as the default unless you mounted the
   volume somewhere else).
5. Railway auto-detects the `uvicorn` start command from `requirements.txt`, or set
   it explicitly: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
6. Once deployed, Railway gives you a public URL like `https://your-app.up.railway.app`
   — that's your `PUBLIC_BASE_URL`.

### 3. Get an OpenAI key (the LLM behind the voice agent)

1. Sign up at [platform.openai.com](https://platform.openai.com), add a small amount
   of billing credit (a few dollars easily covers testing).
2. Create an API key under **API keys**. You'll paste this into Vapi, not into this
   repo — Vapi calls OpenAI on the assistant's behalf.

### 4. Set up Vapi (the phone number + voice agent)

1. Sign up at [dashboard.vapi.ai](https://dashboard.vapi.ai).
2. **Add your OpenAI key**: Settings → Provider Keys → OpenAI → paste the key from
   step 3. (Vapi also gives limited free trial credits if you'd rather test without
   your own key first.)
3. **Create the assistant**:
   - Dashboard → Assistants → Create Assistant → start from blank.
   - Model: OpenAI, `gpt-4o`, temperature ~0.4.
   - System prompt: paste the fenced prompt block from `vapi/system_prompt.md`.
   - Voice: any provider works; ElevenLabs "Rachel" is a natural-sounding default.
   - Transcriber: Deepgram `nova-2`, language `en-US`.
   - First message: `Hi, thanks for calling! I'm Ava, and I can help you register
     as a new patient or update your info. Is this your first time registering
     with us, or are you an existing patient?`
4. **Add the three function tools** (Dashboard → Tools → Create Tool → Function),
   using the parameter schemas in `vapi/assistant_config.json`:
   `lookup_patient_by_phone`, `register_patient`, `update_patient`. For each tool's
   **Server URL**, use `https://YOUR_PUBLIC_BASE_URL/vapi/tool-calls`. Attach all
   three tools to the assistant.
5. **(Recommended) Secure the webhook**: Settings → Integrations → Server
   Configuration → Add Custom Credential → Bearer Token, header name
   `X-Vapi-Secret`, value = whatever you set as `VAPI_WEBHOOK_SECRET` in your `.env`.
   Reference that credential on each tool and on the assistant's `server.url`
   (`https://YOUR_PUBLIC_BASE_URL/vapi/call-events`, for the end-of-call webhook).
   If you skip this, the webhook still works — auth is only enforced when
   `VAPI_WEBHOOK_SECRET` is set — but anyone who finds the URL could write fake
   patients.
6. **Get a phone number**: Dashboard → Phone Numbers → Create Phone Number → Free
   Vapi Number (instant, no Twilio account needed) → assign this assistant as its
   inbound assistant.
7. Call the number. Talk to it like a person, not a form.

*(Alternative to steps 3-4: `python scripts/setup_vapi.py` creates the assistant via
API from `vapi/assistant_config.json` in one shot — see that file's docstring.)*

### Environment variables

| Variable | Required | Purpose |
|---|---|---|
| `DATABASE_URL` | No (defaults to local SQLite) | Swap to a Postgres URL to change engines with no code changes. |
| `VAPI_WEBHOOK_SECRET` | Recommended | Shared secret Vapi sends back on every webhook call; unset = no auth (fine for local testing only). |
| `PUBLIC_BASE_URL` | No | Only used by `scripts/setup_vapi.py`; not read at runtime. |
| `VAPI_API_KEY` | Only for `scripts/setup_vapi.py` | Lets the script create the assistant for you instead of using the dashboard. |
| `OPENAI_API_KEY` | No (not used by this repo) | You'll paste this into Vapi's dashboard directly — this app never calls OpenAI itself. |

## API reference

All responses use the envelope `{"data": ..., "error": null}` (or `"error": "<message>"`
with `"data": null` on failure).

| Method | Endpoint | Notes |
|---|---|---|
| `GET` | `/patients` | Optional `?last_name=`, `?date_of_birth=`, `?phone_number=` filters |
| `GET` | `/patients/{id}` | 404 if not found or soft-deleted |
| `POST` | `/patients` | 201 + full record on success, 422 + field-level error message on validation failure |
| `PUT` | `/patients/{id}` | Partial update — only send fields you're changing |
| `DELETE` | `/patients/{id}` | Soft delete (`deleted_at` set); record no longer appears in GET/list |

Full interactive docs: `/docs` (Swagger) once the server is running.

## Edge cases handled

- **Invalid date of birth (future, malformed)** → server rejects with a specific
  `date_of_birth: ...` message; the agent's prompt tells it to re-ask only that
  field, not restart the call.
- **Malformed phone number** → normalized (strips punctuation, accepts an optional
  leading `1`); rejected if it's still not 10 digits.
- **Mid-call corrections** ("actually it's spelled D-A-V-I-S") → handled entirely in
  the prompt: the agent is instructed to patch the one field and briefly confirm,
  not restart. (This is prompt-engineering, not code — there's no way to unit-test
  it outside a real/simulated call. Vapi's own Voice Testing / Simulations tooling
  is the right next step for regression-testing conversational behavior.)
- **Caller wants to start over** → prompt explicitly instructs the agent to discard
  in-progress fields and restart the required-fields flow.
- **Database write fails** → the tool-calls webhook catches any exception, logs it
  server-side, and returns a natural-language failure string instead of crashing or
  going silent — the caller always gets *some* answer, never dead air.
- **Returning caller (duplicate phone number)** → `lookup_patient_by_phone` is
  called as soon as the phone number is captured; if found, the agent offers to
  update instead of re-registering (bonus requirement).
- **Soft delete** → `DELETE` never removes rows; it sets `deleted_at`, and all reads
  filter it out.
- **Vapi webhook contract quirks** — per Vapi's own troubleshooting docs, the
  webhook always returns HTTP 200 (a non-200 is silently ignored) and every result
  is flattened to a single line (embedded newlines break their parser).

## Known limitations & trade-offs

- **No call recording storage** — only the end-of-call summary/transcript text is
  logged and attached to the patient record, not raw audio. Vapi does store call
  recordings/transcripts on its own dashboard if you need the audio itself.
- **`_extract_patient_id` in the call-events handler is a regex heuristic** — it
  scans the end-of-call summary text for a `patient_id=<uuid>` pattern that the tool
  result put there. This works because the model tends to reference the ID from its
  own tool result in the summary, but it's not guaranteed. A production version
  would instead have Vapi pass the patient_id back explicitly via an
  [assistant variable](https://docs.vapi.ai/assistants/dynamic-variables) set at
  tool-call time, rather than parsing free text.
- **Single clinic, single assistant** — no multi-tenant support, no appointment
  scheduling (bonus, not built), no multi-language switching (bonus, not built —
  the prompt could be extended to detect "hablo español" and switch languages, and
  Vapi supports multilingual transcription, but I didn't wire it up in the time
  available).
- **CORS is wide open (`*`)** for the dashboard's convenience; tighten this to your
  actual dashboard origin before treating this as anything beyond a demo.
- **No rate limiting** on the REST API or webhook endpoints.
- **SQLite** means this won't survive a true multi-instance horizontal deploy
  (two app servers writing to two different local files) — fine for one Railway
  instance, not fine at real scale. Postgres is a one-line `DATABASE_URL` change
  when that matters.
- **This is explicitly not a HIPAA-compliant system** and stores no real patient
  data — per the assessment's own FAQ, that's out of scope here.

## Next steps (if I kept going)

- Wire up the multi-language bonus (detect "hablo español" → switch Vapi's
  transcriber/voice language and swap in a Spanish system prompt).
- Add the appointment-scheduling bonus tool (`schedule_appointment`) with mock
  available slots.
- Replace the patient_id regex-scrape with an explicit Vapi dynamic variable.
- Add HMAC request signing instead of a static bearer secret for the webhook.
- Add Alembic migrations instead of `create_all()` for schema changes post-launch.
