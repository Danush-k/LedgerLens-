"""Per-IP request limits on the endpoints worth abusing.

Two are exposed and expensive in different ways. `/auth/login` verifies a
bcrypt hash, which is deliberately slow, so an unthrottled login endpoint is
both a credential-guessing surface and a cheap way to pin the CPU.
`/trace` spends someone else's rate limit - each submission fans out into
hundreds of calls to public block explorers, so an unthrottled trace
endpoint lets one client exhaust the quota the whole deployment shares.

Limits are per client IP and deliberately generous: an investigator working
quickly should never see one.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

# Comfortably above human speed, far below what a guessing script needs.
LOGIN_LIMIT = "10/minute"
# A trace costs hundreds of upstream calls; bulk upload exists for volume.
TRACE_LIMIT = "20/minute"
