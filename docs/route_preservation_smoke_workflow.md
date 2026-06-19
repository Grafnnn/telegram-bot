# Route-Level Preservation Smoke Workflow

This runbook turns the Issue #45 route-level preservation smoke into a recurring
manual gate for future user-photo generation and preservation changes.

It is intentionally narrow: it verifies backend route orchestration with a
deterministic in-process fake provider. It must not call OpenAI or any network
provider.

## When To Run

Run this workflow before or after any PR that changes:

- `backend/app/api/routes/generations.py`;
- `backend/app/services/mask_service.py`;
- `backend/app/services/preservation_service.py`;
- user-photo provider orchestration;
- user-photo generation result persistence;
- selected-fabric reference resolution for user-photo try-on;
- route-level generation status or `result_image_url` behavior.

Do not use this workflow as proof of visual quality or production readiness. It
only proves that the route fails closed for protected-region drift and
size-mismatched provider output.

## GitHub Actions Automation

The repository also includes a manual `workflow_dispatch` workflow:

```text
.github/workflows/route-preservation-smoke.yml
```

Use it for test-only automation when you want the same route-level smoke
coverage without touching staging. The workflow:

- runs only when manually dispatched;
- uses a disposable PostgreSQL service database;
- uses placeholder test env values only;
- creates a synthetic published fabric fixture in the test database;
- exercises `scripts/smoke_user_photo_preservation_route.py` through the
  backend route/service orchestration;
- uses the deterministic in-process fake provider;
- must not use Render, staging secrets, real OpenAI/provider calls, or real user
  photos.

This workflow is a regression check for code changes. It is not a substitute for
the staging runbook when a release specifically needs staging target, deploy,
and log confirmation.

## Safety Rules

Allowed:

- local/dev runs;
- staging-only runs after an explicit operator GO;
- deterministic fake provider output;
- synthetic user-photo and mask payloads created by the smoke script;
- normal app-level mutations during staging runs, such as generation records and
  synthetic upload files.

Forbidden:

- production runs;
- real OpenAI/provider calls;
- prompt-only/no-mask fallback;
- real or sensitive user photos;
- Render env changes;
- imports;
- SQL or direct DB writes;
- secret, token, base64, raw image byte, raw local path, or provider traceback
  logging.

The smoke command refuses `APP_ENV=prod` and `APP_ENV=production`. It also
requires explicit opt-in through `ALLOW_ROUTE_PRESERVATION_SMOKE=true`.

## Local/Dev Command

Use local/dev only when a local test database and fixture fabric are available.

```bash
ALLOW_ROUTE_PRESERVATION_SMOKE=true \
USER_PHOTO_MASK_MODE=provided \
USER_PHOTO_REQUIRE_MASK_FOR_STRICT_EDIT=true \
python3 scripts/smoke_user_photo_preservation_route.py \
  --fabric-id <published-ai-ready-local-fabric-id> \
  --case all \
  --json-output /tmp/route-preservation-smoke.json \
  --pretty
```

Local prerequisites:

- backend dependencies installed;
- database migrated;
- `BOT_INTERNAL_TOKEN` configured with any non-placeholder local value;
- `UPLOAD_DIR` points to a writable local path;
- the selected fabric is published;
- the selected fabric has a real `texture` or `main` reference file on disk.

## Staging Command

Run this only after confirming the staging backend is deployed from the expected
commit and the operator has approved app-level staging mutations.

```bash
ALLOW_ROUTE_PRESERVATION_SMOKE=true \
USER_PHOTO_MASK_MODE=provided \
USER_PHOTO_REQUIRE_MASK_FOR_STRICT_EDIT=true \
python3 scripts/smoke_user_photo_preservation_route.py \
  --fabric-id <published-ai-ready-staging-fabric-id> \
  --case all \
  --json-output /tmp/route-preservation-smoke.json \
  --pretty
```

Staging preflight:

- backend service is the intended staging service;
- backend live commit matches the expected commit;
- `/api/health` returns HTTP 200 and `{"status":"ok"}`;
- `BOT_INTERNAL_TOKEN` exists, but its value is not printed or copied;
- selected fabric id is staging-only and published;
- selected fabric reference file exists on the staging upload disk;
- no production service, domain, database, or environment will be touched.

Expected staging app-level mutations:

- generation records;
- synthetic user-photo uploads;
- synthetic mask uploads;
- one fake successful generated upload for the `good` case.

These are normal route-level mutations. They are not imports, SQL, direct DB
writes, or real provider calls.

## Expected Result

The command should exit `0` and produce a JSON report with:

```json
{
  "passes": true,
  "provider": "deterministic_fake_in_process",
  "openai_invoked": false,
  "network_provider_invoked": false
}
```

Case-level expectations:

```text
good              -> HTTP 201, completed, result_image_url present, provider_calls=1
protected_drift   -> HTTP 201, failed,    result_image_url absent,  provider_calls=1
size_mismatch     -> HTTP 201, failed,    result_image_url absent,  provider_calls=1
```

The `protected_drift` and `size_mismatch` cases should report
`error_message_category=preservation_guardrail`.

## Failure Conditions

Treat the gate as failed if any of these occur:

- command exits non-zero;
- `openai_invoked` is not `false`;
- `network_provider_invoked` is not `false`;
- any case has `provider_calls != 1`;
- `good` is not `completed`;
- `good` has no `result_image_url`;
- `protected_drift` is not `failed`;
- `protected_drift` has `result_image_url`;
- `size_mismatch` is not `failed`;
- `size_mismatch` has `result_image_url`;
- logs show secrets, tokens, base64 payloads, raw image bytes, raw local paths, or
  provider tracebacks;
- staging run touches production, imports, SQL, or direct DB writes.

## Log Review Checklist

After a staging run, review recent backend logs and confirm:

- startup/deploy is healthy;
- `/api/health` remains HTTP 200;
- preservation guardrail failures are logged with sanitized metrics only;
- no tracebacks;
- no 5xx burst;
- no OpenAI/provider call;
- no prompt-only/no-mask fallback;
- no secret names with values;
- no base64/data URI/raw image bytes;
- no raw upload or filesystem paths in user-facing output.

## Report Template

```text
A. Target:
B. Expected commit:
C. Backend live commit:
D. Health:
E. Fabric id:
F. Smoke command:
G. Top-level passes:
H. openai_invoked:
I. network_provider_invoked:
J. good case:
K. protected_drift case:
L. size_mismatch case:
M. Logs clean:
N. App-level mutations:
O. Prod touched:
P. Imports/SQL/direct DB writes:
Q. Secrets/base64/raw bytes/raw paths exposed:
R. Decision:
S. Follow-up:
```

## Decision

Keep staging execution manual until there is a separate decision to add staging
automation. Do not automate staging runs in a way that can silently create
app-level data or require secret values in logs.
