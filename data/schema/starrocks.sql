-- ============================================================
-- StarRocks DDL — BIN-FSN Stockout Diagnosis
-- ============================================================
-- Run once to create the demo database and tables.
-- In production, pendency_mv already exists and is read-only;
-- we create it here only to load demo data into it.
-- ============================================================

CREATE DATABASE IF NOT EXISTS hl_customer_outbound;
USE hl_customer_outbound;

-- ------------------------------------------------------------
-- pendency_mv  (source table — mirrors the real WMS view)
--
-- Columns match the real pendency_mv schema exactly, plus one
-- demo-only column (grn_id) used by the shared-inbound-batch
-- graph signal. In production, grn_id would be joined from
-- inventory tables; here we add it directly for simplicity.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pendency_mv (
    reservation_warehouse_id        VARCHAR(64)   NOT NULL  COMMENT 'Dark store / warehouse ID',
    picklist_source_location_label  VARCHAR(64)   NOT NULL  COMMENT 'Physical BIN label (e.g. F1-05-5D)',
    picklist_item_fsn               VARCHAR(64)   NOT NULL  COMMENT 'Flipkart Serial Number (product)',
    irt_ticket_id                   VARCHAR(64)             COMMENT 'Non-null = active INF event',
    irt_ticket_type                 VARCHAR(32)             COMMENT 'Infraction enum (e.g. INF)',
    picklist_assigned_to            VARCHAR(64)             COMMENT 'Picker employee ID',
    order_id                        VARCHAR(64)             COMMENT 'Impacted customer order',
    grn_id                          VARCHAR(64)             COMMENT 'Inbound GRN (demo column for shared-batch signal)',
    updated_at                      DATETIME      NOT NULL  COMMENT 'Event timestamp'
)
DUPLICATE KEY(reservation_warehouse_id, picklist_source_location_label, picklist_item_fsn)
DISTRIBUTED BY HASH(reservation_warehouse_id) BUCKETS 4
PROPERTIES ("replication_num" = "1");

-- ------------------------------------------------------------
-- recommendation_log  (owned by this system)
--
-- Tracks every suggestion through its lifecycle and stores
-- failures_before / failures_after for closed-loop verification.
-- Lifecycle: suggested -> acknowledged -> executed -> verified
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS recommendation_log (
    id              BIGINT        NOT NULL  COMMENT 'Primary key',
    warehouse_id    VARCHAR(64)   NOT NULL,
    bin             VARCHAR(64)   NOT NULL,
    fsn             VARCHAR(64)   NOT NULL,
    verdict         VARCHAR(32)   NOT NULL  COMMENT 'PHANTOM | GENUINE_STOCKOUT | DUAL | AMBIGUOUS',
    action          VARCHAR(64)   NOT NULL  COMMENT 'stocktake | replenish | stocktake + replenish | investigate',
    status          VARCHAR(32)   NOT NULL  COMMENT 'suggested | acknowledged | executed | verified',
    suggested_at    DATETIME      NOT NULL,
    resolved_at     DATETIME                COMMENT 'Set when status reaches verified',
    evidence_ref    VARCHAR(1024)           COMMENT 'Cited SQL/graph evidence string',
    failures_before INT           NOT NULL,
    failures_after  INT                     COMMENT 'Filled when action is executed/verified'
)
DUPLICATE KEY(id)
DISTRIBUTED BY HASH(id) BUCKETS 4
PROPERTIES ("replication_num" = "1");
