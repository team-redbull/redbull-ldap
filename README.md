# RedBull LDAP Checker

An internal authentication **decision endpoint**. A service POSTs a username,
password and group; the API binds the credentials against LDAP, checks group
membership via the AD API, and answers whether the user may be let in.

## Layout

| File | Responsibility |
| --- | --- |
| [app/main.py](app/main.py) | FastAPI app, routes, exception -> HTTP mapping |
| [app/config.py](app/config.py) | Settings, loaded and validated from the environment |
| [app/schemas.py](app/schemas.py) | Request/response models |
| [app/errors.py](app/errors.py) | Domain errors and the `error_code` enum |
| [app/ldap_auth.py](app/ldap_auth.py) | Credential verification (LDAP bind) |
| [app/group_check.py](app/group_check.py) | Group membership (AD API client) |

The two checks live in their own modules because they fail in different ways
and will be swapped out independently. `main.py` only sequences them.

## Running

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env      # then fill it in
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Interactive docs at `/docs`, liveness at `/health`.

## The contract

```
POST /auth
{"username": "jdoe", "password": "...", "group": "api-users"}
```

| Status | Body | Meaning |
| --- | --- | --- |
| 200 | `{"authenticated": true}` | Allow |
| 200 | `{"authenticated": false, "error_code": "invalid_credentials", "error": "..."}` | Deny - bad username or password |
| 200 | `{"authenticated": false, "error_code": "not_in_group", "error": "..."}` | Deny - valid user, wrong group |
| 502 | `{"error_code": "upstream_unavailable", "error": "..."}` | **No decision** - LDAP or the AD API is down |
| 422 | FastAPI validation error | Malformed request body |

**200 means a decision was reached; 502 means it was not.** This is the most
important thing to get right in a caller.

Branch on `error_code`, not on the human-readable `error` string - the codes
are stable, the messages are not.

### Calling it correctly

```python
r = requests.post(f"{AUTH_URL}/auth", json={...}, timeout=15)
r.raise_for_status()          # 502 -> retry or fail closed, do NOT treat as a deny
if not r.json()["authenticated"]:
    ...                       # denied; r.json()["error_code"] says why
```

The 502 body deliberately has **no** `authenticated` field, so a caller that
skips `raise_for_status()` gets a `KeyError` instead of silently locking every
user out while LDAP is rebooting.

## Notes for operators

- **Prefer `ldaps://` where the directory supports it.** A plain `ldap://`
  simple bind puts the password on the wire in cleartext, so if you must use
  it, keep the hop to the domain controller on a trusted network.
- **Terminate TLS in front of this service too**, for the same reason - it
  receives plaintext passwords in the request body.
- **This API has no authentication of its own.** Anything that can reach it can
  test credentials against your directory. Keep it on the internal network, and
  put rate limiting in front of it: `/auth` is a password-guessing oracle, and
  repeated wrong guesses will lock out real AD accounts.
- Don't log request bodies at the proxy. The app itself never logs passwords
  (`SecretStr` keeps them out of reprs and validation errors).

## Tests

```bash
.venv/bin/python -m pytest
```

No LDAP server or AD API is needed - both upstreams are mocked. The suite
pins the response contract above, plus the failure modes that matter:
outages are not denials, an empty password never reaches LDAP, and internal
details never reach the response body.
