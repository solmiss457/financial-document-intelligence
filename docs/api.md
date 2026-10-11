# API Contract

FastAPI is called only by the Next.js server, never by browsers, and listens on 127.0.0.1 or a private network.

## Authentication

Every request except `/health` and `/ready` carries `Authorization: Bearer <token>`, where the token is a JWT the Next.js server signs after a Google (OIDC) sign-in:

| Claim | Value |
|---|---|
| `alg` (header) | `ES256` only |
| `iss` / `aud` | `fdi-web` / `fdi-api` |
| `iat`, `exp` | lifetime at most 300 s (30 s clock leeway) |
| `sub` | Google subject (`sub` from the Google ID token) |
| `idp_iss` | `https://accounts.google.com` (other issuers only if listed in `FDI_ALLOWED_IDP_ISSUERS`) |
| `email`, `email_verified` | from the Google ID token |

FastAPI holds only the public key (`storage/keys/web-signing-public.pem`, or `FDI_WEB_PUBLIC_KEY_PATH`). The token never carries organization IDs or roles; those come from the database. `fdi.auth.tokens.mint` is the reference implementation of the signing side.

Error conventions: 401 for a missing or invalid token; 404 for anything outside the caller's organizations, including other organizations' resources and unauthorized documents; 403 for members attempting administrator actions in their own organization; 409 for conflicts; 422 for invalid input; 503 for internal or database errors (no details).

## Endpoints

| Method and path | Who | Purpose |
|---|---|---|
| `GET /me` | any signed-in identity | Linked user, active memberships, pending invitations for the verified email |
| `POST /invitations/{id}/accept` | invitee with verified matching email | Creates the user on first acceptance and the membership |
| `GET /organizations/{org}/members` | admin | Members with email, role, active |
| `PATCH /organizations/{org}/members/{user}` | admin, not self | `{role?, active?}` |
| `GET /organizations/{org}/invitations` | admin | Recent invitations with status |
| `POST /organizations/{org}/invitations` | admin | `{email, role, expires_in_days (1-30)}` |
| `DELETE /organizations/{org}/invitations/{id}` | admin | Revoke a pending invitation |
| `GET /organizations/{org}/documents` | member | Readable documents with status, visibility, fiscal year end |
| `GET /organizations/{org}/documents/{doc}` | member | One readable document |
| `POST /organizations/{org}/documents` | admin | Multipart: `file` (PDF, ≤ 50 MB), `title`, `visibility`, `fiscal_year_end`; queues table-aware ingestion |
| `PATCH /organizations/{org}/documents/{doc}` | admin | `{title?, visibility?, fiscal_year_end?}` |
| `DELETE /organizations/{org}/documents/{doc}` | admin | Hides immediately (202); a worker job removes file, pages, chunks, grants |
| `GET/POST /organizations/{org}/documents/{doc}/grants` | admin | List or add `{user_id}` for restricted documents |
| `DELETE /organizations/{org}/documents/{doc}/grants/{user}` | admin | Remove a grant |
| `GET /organizations/{org}/documents/{doc}/pages/{n}/image?chunk_id=` | member who can read the document | PNG of the page with the cited region outlined; `Cache-Control: private, no-store` |
| `POST /organizations/{org}/questions` | member | `{question}`; G2 configuration; returns state, answer, citations (with pages and boxes), facts, calculation, meta |

Answer states: `answered`, `needs_clarification`, `insufficient_evidence`, `processing_error`.

## Operator Setup

```sh
.venv/bin/python backend/scripts/init_local_env.py        # DB credentials and the ES256 key pair
.venv/bin/python -m backend.scripts.migrate
.venv/bin/python -m backend.scripts.bootstrap_organization --name "Acme Research" --admin-email you@gmail.com
```

The first administrator accepts the printed invitation by signing in with that Google account (P4).
