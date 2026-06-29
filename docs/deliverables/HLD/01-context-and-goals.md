# HLD 01 · Context & Goals

## Purpose

Reduce BIN-FSN stockout diagnosis from 3-5 days to minutes by auto-classifying INF
events into PHANTOM vs GENUINE STOCKOUT with cited, actionable recommendations.

## In scope

- Read-only over `hl_customer_outbound.pendency_mv`.
- Local Dockerized StarRocks + NebulaGraph.
- React UI (table + assistant + feedback), FastAPI backend, LLM agent.
- Closed-loop capture in `recommendation_log`.

## Out of scope (PS guardrails)

- New StarRocks MVs · Slack/email/push · automated stocktake execution · ML
  forecasting · LLM fine-tuning.

## Success metrics

| Metric | Target |
|--------|--------|
| Verdict accuracy vs analyst | >= 70% |
| E2E latency | < 10s |
| Citation coverage | 100% of claims |
| Pilot | 1 dark store, >= 1 week |
