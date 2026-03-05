"""
Optimizer Logging
Handles logging of optimization events to the database.
"""

import pandas as pd
import uuid
import streamlit as st
from app_core.db_manager import get_db_manager

def log_optimization_events(results: dict, client_id: str, report_date: str):
    """
    Standardizes and logs optimization actions (bids, negatives, harvests).
    
    If user has already accepted actions this session (optimizer_actions_accepted=True),
    writes directly to DB and shows undo toast.
    Otherwise, stores in session state for confirmation when leaving optimizer tab.
    """
    
    batch_id = str(uuid.uuid4())[:8]
    actions_to_log = []

    # 1. Process Negative Keywords
    for _, row in results.get('neg_kw', pd.DataFrame()).iterrows():
        actions_to_log.append({
            'entity_name': 'Keyword',
            'action_type': 'NEGATIVE',
            'old_value': 'ENABLED',
            'new_value': 'PAUSED',
            'reason': row.get('Reason', 'Low efficiency / Waste'),
            'campaign_name': row.get('Campaign Name', ''),
            'ad_group_name': row.get('Ad Group Name', ''),
            'target_text': row.get('Term', ''),
            'match_type': row.get('Match Type', 'NEGATIVE')
        })

    # 2. Process Negative Product Targets (ASINs)
    for _, row in results.get('neg_pt', pd.DataFrame()).iterrows():
        actions_to_log.append({
            'entity_name': 'ASIN',
            'action_type': 'NEGATIVE',
            'old_value': 'ENABLED',
            'new_value': 'PAUSED',
            'reason': row.get('Reason', 'Low efficiency / Waste'),
            'campaign_name': row.get('Campaign Name', ''),
            'ad_group_name': row.get('Ad Group Name', ''),
            'target_text': row.get('Term', ''),
            'match_type': 'TARGETING_EXPRESSION'
        })

    # 3. Process Bid Optimizations (Combined)
    bid_dfs = [
        results.get('bids_exact', pd.DataFrame()),
        results.get('bids_pt', pd.DataFrame()),
        results.get('bids_agg', pd.DataFrame()),
        results.get('bids_auto', pd.DataFrame())
    ]
    for b_df in bid_dfs:
        if b_df.empty: continue
        for _, row in b_df.iterrows():
            actions_to_log.append({
                'entity_name': 'Target',
                'action_type': 'BID_CHANGE',
                'old_value': str(row.get('Current Bid', '')),
                'new_value': str(row.get('New Bid', '')),
                'reason': row.get('Reason', 'Portfolio Optimization'),
                'campaign_name': row.get('Campaign Name', ''),
                'ad_group_name': row.get('Ad Group Name', ''),
                'target_text': row.get('Targeting', ''),
                'match_type': row.get('Match Type', ''),
                'intelligence_flags': row.get('Intelligence_Flags', '')
            })

    # 4. Process Harvests - WITH WINNER SOURCE TRACKING
    for _, row in results.get('harvest', pd.DataFrame()).iterrows():
        # Determine winner source campaign and new campaign name
        winner_campaign = row.get('Campaign Name', '')
        search_term = row.get('Customer Search Term', '')
        
        # Generate new campaign name (you can customize this logic)
        new_campaign = f"Harvest_Exact_{winner_campaign}" if winner_campaign else "Harvest_Exact_Campaign"
        
        actions_to_log.append({
            'entity_name': 'Keyword',
            'action_type': 'HARVEST',
            'old_value': 'DISCOVERY',
            'new_value': 'PROMOTED',
            'reason': f"Conv: {row.get('Orders', 0)} orders",
            'campaign_name': winner_campaign,  # Source campaign
            'ad_group_name': row.get('Ad Group Name', ''),
            'target_text': search_term,
            'match_type': 'EXACT',
            # NEW FIELDS FOR IMPACT ANALYSIS:
            'winner_source_campaign': winner_campaign,  # Which campaign won
            'new_campaign_name': new_campaign,  # Where it's being moved
            'before_match_type': row.get('Match Type', 'broad'),  # Original match type
            'after_match_type': 'exact'  # Harvested to exact
        })


    # === DEDUPLICATE ACTIONS ===
    # Remove duplicates that would violate the unique constraint:
    # (client_id, action_date, target_text, action_type, campaign_name)
    # Keep the last occurrence (most recent values for the same target)
    seen_keys = {}
    for i, action in enumerate(actions_to_log):
        key = (
            action.get('target_text', '').lower().strip(),
            action.get('action_type', ''),
            action.get('campaign_name', '').strip()
        )
        seen_keys[key] = i  # Overwrite with latest index
    
    # Build deduplicated list (keeping only the last occurrence of each key)
    unique_indices = set(seen_keys.values())
    actions_to_log = [a for i, a in enumerate(actions_to_log) if i in unique_indices]

    if not actions_to_log:
        return 0
    
    # PENDING ACTIONS WORKFLOW: Store actions in session state for immediate flush via flush_pending_actions_to_db()
    st.session_state['pending_actions'] = {
        'actions': actions_to_log,
        'client_id': client_id,
        'batch_id': batch_id,
        'report_date': report_date
    }
    st.session_state['last_queued_batch_id'] = batch_id

    return len(actions_to_log)



def flush_pending_actions_to_db(test_mode: bool = False) -> int:
    """
    Commit all pending optimizer actions from session_state to the actions_log table.
    
    Returns the number of rows written, or 0 if nothing to save.
    Raises on DB connection failure so the caller can show an error message.
    """
    pending = st.session_state.get('pending_actions')
    if not pending or not pending.get('actions'):
        return 0

    actions = pending['actions']
    client_id = pending['client_id']
    batch_id = pending['batch_id']
    report_date = pending['report_date']

    db = get_db_manager(test_mode)
    if not db:
        raise RuntimeError("Database manager unavailable")

    written = db.log_action_batch(actions, client_id, batch_id, report_date)
    st.session_state['last_saved_batch_id'] = batch_id
    st.session_state['last_saved_count'] = int(written)

    # Clear the queue so double-saves don't happen
    st.session_state.pop('pending_actions', None)
    return written
