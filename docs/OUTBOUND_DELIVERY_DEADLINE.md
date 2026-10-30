# Outbound delivery: bounded total HTTP attempts and evidence boundaries

The public `/api/lead` success contract is unchanged. Accepted leads and
outbox rows are committed in one SQLite transaction; delivery is **at least
once**, not exactly once. The recipient must deduplicate on lead ID.

## Whole-attempt deadline

`DELIVERY_TIMEOUT` (default 8 s, permitted 0.1–120 s) is a **parent-enforced
wall-clock timeout for the isolated outbound child after process creation**.
Each network attempt (DNS, connection, TLS, HTTP response headers) runs inside
`server/delivery_transport.py`. The parent uses
`subprocess.Popen.communicate(timeout=...)`, followed by `kill()` and
`communicate()` to reap overdue children. The child sets Linux
`PR_SET_PDEATHSIG=SIGKILL`, and validates its parent PID to avoid orphaned
network calls if the main server process is killed. The payload and Telegram
URL credentials go through stdin, not argv or stdout. Child output is limited
to HTTP status or exception class. Redirects are disallowed to prevent
credential/HMAC forwarding; only HTTP(S) endpoints are valid.

Complete HTTP 2xx **headers** acknowledge delivery. A slow/trickled 2xx body
is not consumed. HTTP 4xx except 408/429 is permanent; timeouts, 408/429,
5xx and transport failures are retriable under the existing exponential
backoff and maximum attempts.

The timeout does **not** place a hard bound on arbitrary OS scheduler delays,
process creation, SQLite lock contention, or physical infrastructure outage.
When a timeout fires, a remote system might already have accepted the message:
subsequent delivery can be a duplicate (at-least-once). This is expected.

## Falsification contract

`tests/test_delivery_deadline.py` injects a response-header drip at 70ms
intervals, faster than the configured 400ms socket timeout. The old direct
`urlopen` path could hang beyond 400ms; the isolated child is killed and the
outbox attempt is recorded as transient. An adversarial 51-lead backlog
saturates all four delivery slots, checks bounded progress and **zero**
permanent/lost leads, and validates HMAC signatures for both the rejected
and post-restart delivered copies. Tests also cover missing/incorrect
child-parent liveness and invalid timeout settings.

These are **local synthetic** measures. Do not infer a production delivery
p95/p99, offsite RPO, or live external CRM acceptance. A deployment must
independently establish receiver deduplication, actual DNS/TLS/proxy behavior,
process resource budgets and explicit SLI/SLO.

## Fail-closed numeric operational configuration

On startup, invalid/non-finite HTTP input timeout or absolute header deadline,
delivery retry limit/backoff/poll interval, disk-free readiness threshold, or
connection slot wait **aborts the process** rather than disabling timeouts,
spinning on pending outbox, bypassing low-disk checks, or converting temporary
downstream failures into terminal lost deliveries. Existing normal defaults and
the documented six-hour exponential retry-backoff ceiling are unchanged.
`tests/test_delivery_deadline.py` includes negative fault-injection vectors for
`nan`, infinities, negative deadlines, zero polling and unbounded retry counts.
The HTTP security and full make gates run these cases on the source HEAD.


## Remote transport confidentiality (fail closed)

HMAC-SHA256 authenticates webhook request **bytes**, not their secrecy.
An HTTP URL on a remote host could disclose contact details and permit replay
by anyone observing plaintext traffic. Both the parent server and isolated
delivery child therefore reject remote `http://`, unsupported schemes, or
credentials embedded in URLs. Only `https://` is permitted for remote
Telegram/webhook endpoints. Local integration adapters may explicitly use
literal loopback IPv4/IPv6 or `localhost` with HTTP; this is not a claim
that loopback HTTP is safe when bridged to another host.

The check is a startup error for configured endpoints. The operator must
supply a certificate-validated TLS destination (or a local TLS terminator)
rather than disabling signature verification or silently omitting delivery.
This is a **source-level configuration policy**, not evidence that an actual
production destination currently uses plaintext or that production TLS has
been externally measured.


## Telegram Unicode transport: no form-encoding expansion

Telegram Bot API `sendMessage` supports HTTP POST with
`application/json` (https://core.telegram.org/bots/api#making-requests).
The sender encodes `chat_id` and the existing 4000-character message in
UTF-8 JSON with `ensure_ascii=False`, instead of percent-encoding every
byte of non-ASCII text as `application/x-www-form-urlencoded`.
This preserves validated emoji and Cyrillic fields while keeping the unchanged
16-KiB decoded child payload bound and 64-KiB stdin-envelope bound. The old
form-encoded path could exceed 16 KiB for a valid 5–6 KiB UTF-8 lead and
terminate a durable Telegram outbox job after futile retries. The regression
test sends maximal validated emoji fields over a real local HTTP request, reads
the actual Telegram-compatible JSON body from a local receiver, and asserts
one completed outbox delivery with no lost Unicode text. It does **not** claim
that Telegram's external service or credentials were tested. The CRM webhook
format and its HMAC-SHA256 bytes remain exactly unchanged.
