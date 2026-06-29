# What is the Context Repository?

> Repo: `https://github.fkinternal.com/Flipkart/assets-project-contexts`
> Cloned locally into this project at `.context-repo/` for reference.

This document explains what the `assets-project-contexts` repository is, why it
exists, and how we use it for the **BIN-FSN Stockout Diagnosis** project.

---

## 1. The One-Line Summary

It is **NOT application code.** It is a **documentation + AI-context repository**
for Flipkart's **Assets WMS** (Warehouse Management System) platform.

Think of it as the "brain dump" of the entire warehouse software ecosystem:
domain knowledge, service responsibilities, how services talk to each other,
business rules, database schemas, and end-to-end process flows — written in a
structured way so that **both humans and AI agents** can understand the WMS
world without reading the actual production source code.

---

## 2. Why Does It Exist?

A warehouse runs on ~10 interconnected microservices. Understanding "what happens
when a picker can't find an item" normally requires reading thousands of lines of
Java across many repos. This context repo solves that by capturing:

- **Domain principles** — the rules and vocabulary of the warehouse world.
- **Service responsibilities** — who owns what, and what is explicitly out of scope.
- **Integration map** — which service calls which, and what events flow where.
- **Cross-service flows** — the full story of order fulfillment, cancellation,
  inbound receiving, returns, etc.
- **AI tooling** — Cursor rules, skills, and commands so an AI agent can generate
  designs (HLDs) that respect the real architecture.

For us, it is the source of truth for the **"WMS world"** that our stockout
diagnosis tool plugs into.

---

## 3. What's Inside (Structure)

```
assets-project-contexts/
│
├── README.md                 # Entry point and quick-start guide
├── constitution.md           # Domain principles, glossary, architecture, decisions
├── SERVICE_REGISTRY.md       # Canonical index of all 10 services + event topics
├── FLOW_CATALOG.md           # End-to-end cross-service flows (with diagrams)
├── AGENTS.md                 # Coding/behavior guidelines for AI agents
│
├── .cursor/                  # AI rules, skills (HLD generator, WMS domain expert)
├── adrs/                     # Architecture Decision Records
│
└── <one folder per service>/ # Deep-dive docs for each WMS service
    ├── DOMAIN_OVERVIEW.md     #   Bounded context, domain model, processes, events
    ├── ARCHITECTURE.md        #   Tech stack, layers, DB, caching, events
    ├── API_REFERENCE.md       #   REST endpoints with request/response schemas
    ├── BUSINESS_RULES.md      #   Validation rules, state machines, calculations
    └── DATABASE_SCHEMA.md     #   Tables, columns, indexes, relationships
```

### The 4 Files to Read First

| Order | File | Answers |
|-------|------|---------|
| 1 | `constitution.md` | Domain principles, glossary, decision framework |
| 2 | `SERVICE_REGISTRY.md` | Which service owns what? Who calls whom? What events exist? |
| 3 | `FLOW_CATALOG.md` | How does fulfillment / cancellation / inbound work end-to-end? |
| 4 | `<service>/DOMAIN_OVERVIEW.md` | Deep-dive into a specific service |

---

## 4. The WMS Services (the "World")

The platform is an outbound + inbound pipeline around a core inventory system:

```
Order Systems ──▶ Reservation ──▶ Planning ──▶ Picking ──▶ Pack/Dispatch ──▶ Carrier
(FKI/FBF/EXT)        │              │            │              │
                     ▼              ▼            ▼              ▼
                          Inventory Service (System of Record)
                                      ▲
                                      │
                              Inbound Consignment

Cross-cutting: MDM (master data) · PaperTrail (documents) · Replication (sync)
```

| Service | What it owns (in one line) |
|---------|----------------------------|
| **Reservation** | Reserve / hold / cancel inventory for an order |
| **Planning** | Group orders into ship groups and generate picking plans |
| **Picking** | Picklists, the picker scanning items — **raises INF / IRT tickets** |
| **Pack Dispatch (Service + Controller)** | QC, packing, dispatch to carrier |
| **Inventory** | System of record — items, **ATP**, locks, storage locations (BINs) |
| **Inbound Consignment** | Receiving goods, quality check, **GRN creation** |
| **Inv-Audit** | **Stock takes** and **variances** (the correction mechanism) |
| **MDM** | Master data — products, sellers, warehouses, locations |
| **PaperTrail** | Documents, labels, barcodes, PDFs |
| **Replication** | Auto receiving for inter-warehouse transfers (IWIT) |

---

## 5. Why It Matters for BIN-FSN Stockout Diagnosis

Our problem statement only correlates **FSN × BIN** to decide PHANTOM vs GENUINE
STOCKOUT. The context repo lets us **extend that into a true root-cause engine**
because it tells us exactly how the surrounding warehouse mechanics work:

| Signal we add | What the context repo gives us |
|---------------|-------------------------------|
| **Picker overlap** | Picking Service: the picker (`picklist_assigned_to`) raises INF — so failures clustered on one picker = process issue, not phantom |
| **Shared inbound batch** | Inventory `grnId` + Inbound `GrnEvent` — FSNs failing that share a GRN = mis-receive at inbound, not depletion |
| **IRT → Stocktake feedback loop** | Inv-Audit Service: a PHANTOM verdict triggers a stocktake which produces a **negative variance**, letting us confirm the loss and close the loop |
| **ATP cross-check** | Inventory Service: GENUINE STOCKOUT can be verified against `ATP = 0` (true depletion) vs cache-drift |

In short: the **PS gives us the "what,"** and the **context repo gives us the
"why" and the "what to do next"** — turning a simple 2-way classifier into an
end-to-end, action-oriented diagnosis system.

---

## 6. Key Terms (Quick Glossary)

| Term | Meaning |
|------|---------|
| **FSN** | Flipkart Serial Number — the product/catalog identifier |
| **BIN** | A labeled physical slot in the dark store (e.g., `F1-05-5D`) |
| **INF** | Item Not Found — picker can't locate an item at its BIN |
| **IRT** | Inventory Resolution Ticket — raised to resolve the discrepancy |
| **ATP** | Available To Promise — whether inventory can be allocated |
| **GRN** | Goods Receipt Note — the inbound receipt that created the inventory |
| **WID / WSN** | Warehouse Item / Serial identifiers for a physical unit |
| **Stocktake** | Physical re-count of a BIN to reconcile system vs reality |
| **Variance** | The correction applied after a stocktake (negative = loss) |
| **Phantom Inventory** | System thinks stock exists but it's physically gone/misplaced |
| **Genuine Stockout** | Inventory truly depleted across the facility |

---

## 7. How We Use It in This Project

1. **As read-only reference** — we never modify the context repo; we read its docs
   to ground our design decisions in real WMS behavior.
2. **To justify the e2e extension** — every extra signal we add maps to a real
   service/concept documented here (no invented mechanics).
3. **For the LLM assistant** — the same domain knowledge can feed the assistant so
   its answers stay consistent with how the warehouse actually works.
