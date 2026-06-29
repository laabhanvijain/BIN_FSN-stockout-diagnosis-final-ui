# HLD 06 · Quality Attributes

| Attribute | Target | Approach |
|-----------|--------|----------|
| Latency | < 10s e2e | Cache verdicts, pre-warm graph, small ETL window |
| Accuracy | >= 70% vs analyst | Deterministic PS thresholds + ground-truth seed |
| Auditability | 100% cited claims | Tool-grounded LLM + evidence strings |
| Availability | >= 1 week pilot | Dockerized, stateless backend |
| Security | least privilege | Read-only DB access (except recommendation_log); whitelisted LLM queries; secrets via env |
