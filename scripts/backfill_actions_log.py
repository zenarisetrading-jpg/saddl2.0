#!/usr/bin/env python3
"""
Backfill actions_log from Amazon bulk upload files.

Usage:
    cd /Users/zayaanyousuf/Documents/Amazon\ PPC/saddle/saddle
    python3 desktop/scripts/backfill_actions_log.py \
        --client_id s2c_uae_test \
        --date 2026-01-21 \
        --negatives  ~/path/to/negatives.csv \
        --bids       ~/path/to/bids.csv \
        --harvest    ~/path/to/harvest.csv

Each argument is optional — you can supply any combination of the three files.
The script reads the standard Amazon Sponsored Ads bulk upload format.
"""

from __future__ import annotations

import argparse
import os
import sys
import uuid
from datetime import date
from pathlib import Path
from typing import List, Dict, Optional

import pandas as pd
import psycopg2


# ─── DB helpers ──────────────────────────────────────────────────────────────

def _get_conn():
    url = os.getenv("DATABASE_URL")
    if not url:
        env_path = Path(__file__).resolve().parents[1] / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                line = line.strip()
                if line.startswith("DATABASE_URL="):
                    url = line.split("=", 1)[1].strip("'\"")
                    break
    if not url:
        raise RuntimeError("DATABASE_URL not found in environment or desktop/.env")
    return psycopg2.connect(url)


INSERT_SQL = """
INSERT INTO actions_log (
    action_date, client_id, batch_id, entity_name, action_type,
    old_value, new_value, reason,
    campaign_name, ad_group_name, target_text, match_type,
    winner_source_campaign, new_campaign_name,
    before_match_type, after_match_type,
    intelligence_flags
)
VALUES (
    %s, %s, %s, %s, %s,
    %s, %s, %s,
    %s, %s, %s, %s,
    %s, %s,
    %s, %s,
    %s
)
ON CONFLICT DO NOTHING
"""

def _write_rows(conn, rows: List[Dict]) -> int:
    written = 0
    with conn.cursor() as cur:
        for r in rows:
            cur.execute(INSERT_SQL, (
                r.get("action_date"),
                r.get("client_id"),
                r.get("batch_id"),
                r.get("entity_name", ""),
                r.get("action_type", ""),
                r.get("old_value", ""),
                r.get("new_value", ""),
                r.get("reason", ""),
                r.get("campaign_name", ""),
                r.get("ad_group_name", ""),
                r.get("target_text", ""),
                r.get("match_type", ""),
                r.get("winner_source_campaign", None),
                r.get("new_campaign_name", None),
                r.get("before_match_type", None),
                r.get("after_match_type", None),
                r.get("intelligence_flags", None),
            ))
            written += 1
    conn.commit()
    return written


# ─── Parsers ─────────────────────────────────────────────────────────────────

def _load(path: str) -> pd.DataFrame:
    p = Path(path).expanduser()
    if not p.exists():
        raise FileNotFoundError(f"File not found: {p}")
    if p.suffix.lower() in (".xlsx", ".xls"):
        return pd.read_excel(p, dtype=str).fillna("")
    return pd.read_csv(p, dtype=str, encoding="utf-8-sig").fillna("")


def _col(df: pd.DataFrame, *candidates: str) -> pd.Series:
    """Return first matching column, case-insensitively."""
    lc = {c.lower(): c for c in df.columns}
    for cand in candidates:
        if cand.lower() in lc:
            return df[lc[cand.lower()]]
    return pd.Series([""] * len(df))


def parse_negatives(df: pd.DataFrame, client_id: str, action_date: date, batch_id: str) -> List[Dict]:
    rows = []
    for _, row in df.iterrows():
        entity = str(row.get("Entity", "")).lower()
        operation = str(row.get("Operation", "")).lower()
        if operation != "create":
            continue
        if "negative" not in entity:
            continue

        # Keyword text vs targeting expression (product targets)
        kw_text = (row.get("Keyword Text") or row.get("Keyword") or "").strip()
        tgt_expr = (row.get("Targeting Expression") or row.get("Targeting") or "").strip()
        target_text = kw_text or tgt_expr

        is_pt = "product" in entity
        match_type = (row.get("Match Type") or ("TARGETING_EXPRESSION" if is_pt else "NEGATIVE_EXACT")).strip()

        rows.append({
            "action_date":      action_date,
            "client_id":        client_id,
            "batch_id":         batch_id,
            "entity_name":      "ASIN" if is_pt else "Keyword",
            "action_type":      "NEGATIVE",
            "old_value":        "ENABLED",
            "new_value":        "PAUSED",
            "reason":           "Low efficiency / Waste — manual bulk backfill",
            "campaign_name":    (row.get("Campaign Name") or row.get("Campaign") or "").strip(),
            "ad_group_name":    (row.get("Ad Group Name") or row.get("Ad Group") or row.get("Group Name") or "").strip(),
            "target_text":      target_text,
            "match_type":       match_type,
        })
    return rows


def parse_bids(df: pd.DataFrame, client_id: str, action_date: date, batch_id: str) -> List[Dict]:
    rows = []
    for _, row in df.iterrows():
        entity = str(row.get("Entity", "")).lower()
        operation = str(row.get("Operation", "")).lower()
        if operation != "update":
            continue
        if "keyword" not in entity and "product ta" not in entity:
            continue

        bid_str = (row.get("Bid") or row.get("New Bid") or "").strip()
        if not bid_str:
            continue

        kw_text = (row.get("Keyword Text") or row.get("Keyword") or "").strip()
        tgt_expr = (row.get("Targeting Expression") or row.get("Targeting") or "").strip()
        target_text = kw_text or tgt_expr

        match_type = (row.get("Match Type") or "").strip()

        rows.append({
            "action_date":      action_date,
            "client_id":        client_id,
            "batch_id":         batch_id,
            "entity_name":      "Target",
            "action_type":      "BID_CHANGE",
            "old_value":        "",           # bulk file doesn't have old bid
            "new_value":        bid_str,
            "reason":           "Bid optimisation — manual bulk backfill",
            "campaign_name":    (row.get("Campaign Name") or row.get("Campaign") or "").strip(),
            "ad_group_name":    (row.get("Ad Group Name") or row.get("Ad Group") or row.get("Group Name") or "").strip(),
            "target_text":      target_text,
            "match_type":       match_type,
        })
    return rows


def parse_harvest(df: pd.DataFrame, client_id: str, action_date: date, batch_id: str) -> List[Dict]:
    """
    Harvest bulk creates rows for: Campaign, Ad Group, Product Ad, Keyword, Product Targeting.
    We only log the Keyword / Product Targeting rows as HARVEST actions.
    """
    rows = []
    for _, row in df.iterrows():
        entity = str(row.get("Entity", "")).lower()
        operation = str(row.get("Operation", "")).lower()
        if operation != "create":
            continue
        if "keyword" not in entity and "product ta" not in entity:
            continue

        kw_text = (row.get("Keyword Text") or row.get("Keyword") or "").strip()
        tgt_expr = (row.get("Targeting Expression") or row.get("Targeting") or "").strip()
        target_text = kw_text or tgt_expr

        match_type = (row.get("Match Type") or "EXACT").strip()
        campaign_name = (row.get("Campaign Name") or row.get("Campaign") or "").strip()
        bid_str = (row.get("Bid") or row.get("New Bid") or "").strip()

        rows.append({
            "action_date":          action_date,
            "client_id":            client_id,
            "batch_id":             batch_id,
            "entity_name":          "Keyword",
            "action_type":          "HARVEST",
            "old_value":            "DISCOVERY",
            "new_value":            f"PROMOTED → bid={bid_str}" if bid_str else "PROMOTED",
            "reason":               "Harvest exact — manual bulk backfill",
            "campaign_name":        campaign_name,
            "ad_group_name":        (row.get("Ad Group Name") or row.get("Ad Group") or row.get("Group Name") or "").strip(),
            "target_text":          target_text,
            "match_type":           match_type,
            "before_match_type":    "broad",
            "after_match_type":     "exact",
            "winner_source_campaign": campaign_name,
        })
    return rows


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Backfill actions_log from Amazon bulk files")
    parser.add_argument("--client_id", required=True, help="e.g. s2c_uae_test")
    parser.add_argument("--date",      required=True, help="ISO date of the optimizer run, e.g. 2026-01-21")
    parser.add_argument("--negatives", help="Path to negatives bulk CSV/XLSX")
    parser.add_argument("--bids",      help="Path to bids/targets bulk CSV/XLSX")
    parser.add_argument("--harvest",   help="Path to harvest bulk CSV/XLSX")
    parser.add_argument("--dry_run",   action="store_true", help="Print row counts without writing to DB")
    args = parser.parse_args()

    if not any([args.negatives, args.bids, args.harvest]):
        print("ERROR: Provide at least one of --negatives, --bids, --harvest")
        sys.exit(1)

    action_date = date.fromisoformat(args.date)
    batch_id = str(uuid.uuid4())[:8]
    all_rows: List[Dict] = []

    if args.negatives:
        df = _load(args.negatives)
        rows = parse_negatives(df, args.client_id, action_date, batch_id)
        print(f"  Negatives parsed: {len(rows)} actions")
        all_rows.extend(rows)

    if args.bids:
        df = _load(args.bids)
        rows = parse_bids(df, args.client_id, action_date, batch_id)
        print(f"  Bids parsed:      {len(rows)} actions")
        all_rows.extend(rows)

    if args.harvest:
        df = _load(args.harvest)
        rows = parse_harvest(df, args.client_id, action_date, batch_id)
        print(f"  Harvest parsed:   {len(rows)} actions")
        all_rows.extend(rows)

    print(f"\nTotal actions to insert: {len(all_rows)} (batch_id={batch_id})")

    if args.dry_run:
        print("DRY RUN — nothing written.")
        # Print first 3 rows as a sanity check
        for r in all_rows[:3]:
            print(" ", r)
        return

    conn = _get_conn()
    try:
        written = _write_rows(conn, all_rows)
        print(f"✅ Successfully wrote {written} rows to actions_log for {args.date}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
