# LLD 09 · Security (cross-cutting)

- **Secrets**: `ANTHROPIC_API_KEY`, DB creds via env/`.env`; never committed.
- **DB access**: read-only everywhere except `recommendation_log`.
- **LLM queries**: validated/whitelisted before execution; no arbitrary writes.
- **API inputs**: validated at the boundary (pydantic models).
- **Least privilege**: DB users scoped to the minimum needed.

_Status: enforced from M5 onward._
