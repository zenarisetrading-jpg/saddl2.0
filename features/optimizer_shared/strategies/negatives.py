"""
Optimizer Negative Strategy
Logic for identifying negative keyword and ASIN candidates to reduce wasted spend.
"""

import pandas as pd
import numpy as np
import streamlit as st
from typing import Tuple, Dict, Any, Optional, Set
from features.optimizer_shared.core import calculate_account_benchmarks
from features.bulk_export import strip_targeting_prefix
from app_core.data_hub import DataHub
from app_core.data_loader import is_asin
from dev_resources.tests.bulk_validation_spec import (
    OptimizationRecommendation,
    RecommendationType,
    validate_recommendation
)

def enrich_with_ids(df: pd.DataFrame, bulk: pd.DataFrame) -> pd.DataFrame:
    """
    Unified high-precision ID mapping helper.
    Matches by Campaign, Ad Group, and Targeting Text (Keyword/PT).
    Synchronizes OptimizationRecommendation objects.
    """
    if df.empty or bulk is None or bulk.empty:
        return df
        
    def normalize_for_mapping(series):
        """
        Normalize and strip prefixes for robust matching.
        e.g., 'asin="B0123"' -> 'b0123', 'category="123"' -> '123'
        """
        s = series.astype(str).str.strip().str.lower()
        # Remove common prefixes and quotes
        s = s.str.replace(r'^(asin|category|asin-expanded|keyword-group)=', '', regex=True)
        s = s.str.replace(r'^"', '', regex=True).str.replace(r'"$', '', regex=True)
        # Final alphanumeric cleanup
        return s.str.replace(r'[^a-z0-9]', '', regex=True)
    
    df = df.copy()
    bulk = bulk.copy()
    
    # DEBUG: Diagnostic logging for ID mapping failure
    print(f"DEBUG_ENRICH: Input DF shape: {df.shape}")
    print(f"DEBUG_ENRICH: Bulk Mapping shape: {bulk.shape if bulk is not None else 'None'}")
    
    if bulk is not None and not bulk.empty:
         print(f"DEBUG_ENRICH: Bulk Columns: {bulk.columns.tolist()}")
         print(f"DEBUG_ENRICH: Bulk Sample ID: {bulk['Campaign Id'].iloc[0] if 'Campaign Id' in bulk.columns else 'N/A'}")

    # Normalize for mapping
    df['_camp_norm'] = normalize_for_mapping(df['Campaign Name'])
    df['_ag_norm'] = normalize_for_mapping(df.get('Ad Group Name', pd.Series([''] * len(df))))
    
    # Initialize ID columns if missing to avoid KeyError during resolution
    for col in ['KeywordId', 'TargetingId']:
        if col not in df.columns:
            df[col] = np.nan
    
    # For general targeting (Search Term or Targeting column)
    target_col = 'Term' if 'Term' in df.columns else 'Targeting'
    df['_target_norm'] = normalize_for_mapping(df[target_col])
    
    # DEBUG: Bulk Columns pre-normalization
    if bulk is not None:
        # Normalize Bulk Columns to CamelCase (remove spaces)
        # This fixes 'Campaign Id' -> 'CampaignId' mismatch
        bulk.columns = [c.replace(' ', '') for c in bulk.columns]
        print(f"DEBUG_ENRICH: Bulk Columns Normalized: {bulk.columns.tolist()}")

    # Normalize for mapping
    df['_camp_norm'] = normalize_for_mapping(df['Campaign Name'])
    df['_ag_norm'] = normalize_for_mapping(df.get('Ad Group Name', pd.Series([''] * len(df))))
    
    # Initialize ID columns if missing to avoid KeyError during resolution
    for col in ['KeywordId', 'TargetingId', 'CampaignId', 'AdGroupId']:
        if col not in df.columns:
            df[col] = np.nan
    
    # For general targeting (Search Term or Targeting column)
    target_col = 'Term' if 'Term' in df.columns else 'Targeting'
    df['_target_norm'] = normalize_for_mapping(df[target_col])
    
    bulk['_camp_norm'] = normalize_for_mapping(bulk.get('CampaignName', pd.Series(['']*len(bulk))))
    bulk['_ag_norm'] = normalize_for_mapping(bulk.get('AdGroupName', pd.Series([''] * len(bulk))))

    # Check mapping availability
    print(f"DEBUG_ENRICH: Bulk rows with CampaignId: {bulk['CampaignId'].notna().sum() if 'CampaignId' in bulk.columns else 0}")
    # Precise Match 1: Keywords
    # CRITICAL: Include Match Type to distinguish phrase/exact versions of the same keyword
    kw_col = next((c for c in ['CustomerSearchTerm', 'KeywordText', 'keyword_text'] if c in bulk.columns), None)
    if kw_col:
        bulk['_kw_norm'] = normalize_for_mapping(bulk[kw_col])
        # Normalize Match Type for both df and bulk
        df['_match_norm'] = df['Match Type'].astype(str).str.lower().str.strip() if 'Match Type' in df.columns else ''
        bulk['_match_norm'] = bulk['MatchType'].astype(str).str.lower().str.strip() if 'MatchType' in bulk.columns else ''
        
        # STRICT LOOKUP: Include Match Type to prevent collision between phrase/exact/broad
        # Use groupby().first() to ensure 1-to-1 mapping and prevent row explosion
        kw_base = bulk[bulk['KeywordId'].notna() & (bulk['KeywordId'] != "") & (bulk['KeywordId'] != "nan")][
            ['_camp_norm', '_ag_norm', '_kw_norm', '_match_norm', 'KeywordId', 'CampaignId', 'AdGroupId']
        ]
        kw_lookup = kw_base.groupby(['_camp_norm', '_ag_norm', '_kw_norm', '_match_norm']).first().reset_index()
        
        # STRATEGY 1: Strict match (Campaign + AG + Keyword + Match Type)
        df = df.merge(
            kw_lookup.rename(columns={'_kw_norm': '_target_norm'}),
            on=['_camp_norm', '_ag_norm', '_target_norm', '_match_norm'],
            how='left',
            suffixes=('', '_bulk_kw')
        )
        
        # STRATEGY 2: Fallback for unmatched rows (ignore Match Type)
        # Only fill if KeywordId is still missing after strict match
        strict_matched = df.get('KeywordId_bulk_kw', pd.Series([np.nan]*len(df))).notna()
        if (~strict_matched).any():
            # Relaxed lookup: Campaign + AG + Keyword only (take first ID for each)
            kw_lookup_relaxed = kw_base.groupby(['_camp_norm', '_ag_norm', '_kw_norm'])[
                ['KeywordId', 'CampaignId', 'AdGroupId']
            ].first().reset_index()
            kw_lookup_relaxed = kw_lookup_relaxed.rename(columns={
                '_kw_norm': '_target_norm', 
                'KeywordId': 'KeywordId_relaxed', 
                'CampaignId': 'CampaignId_relaxed', 
                'AdGroupId': 'AdGroupId_relaxed'
            })
            df = df.merge(
                kw_lookup_relaxed,
                on=['_camp_norm', '_ag_norm', '_target_norm'],
                how='left',
                suffixes=('', '_relax')
            )
            # Only use relaxed match if strict match failed
            for col in ['KeywordId', 'CampaignId', 'AdGroupId']:
                relaxed_col = f'{col}_relaxed'
                bulk_kw_col = f'{col}_bulk_kw'
                if relaxed_col in df.columns:
                    if bulk_kw_col in df.columns:
                        df[bulk_kw_col] = df[bulk_kw_col].fillna(df[relaxed_col])
                    else:
                        df[bulk_kw_col] = df[relaxed_col]
                    df.drop(columns=[relaxed_col], inplace=True, errors='ignore')
        
    # Precise Match 2: Product Targeting
    # CamelCase column names
    pt_col = next((c for c in ['TargetingExpression', 'ProductTargetingExpression', 'targeting_expression'] if c in bulk.columns), None)
    if pt_col:
        bulk['_pt_norm'] = normalize_for_mapping(bulk[pt_col])
        pt_lookup = bulk[bulk['TargetingId'].notna() & (bulk['TargetingId'] != "") & (bulk['TargetingId'] != "nan")][['_camp_norm', '_ag_norm', '_pt_norm', 'TargetingId', 'CampaignId', 'AdGroupId']].drop_duplicates()
        
        df = df.merge(
            pt_lookup.rename(columns={'_pt_norm': '_target_norm'}),
            on=['_camp_norm', '_ag_norm', '_target_norm'],
            how='left',
            suffixes=('', '_bulk_pt')
        )

    # Resolve IDs
    id_cols = ['CampaignId', 'AdGroupId', 'KeywordId', 'TargetingId']
    for col in id_cols:
        if col in df.columns:
            df[col] = df[col].replace('', np.nan).replace('nan', np.nan)
            
        col_kw = f'{col}_bulk_kw'
        col_pt = f'{col}_bulk_pt'
        
        # Priority: Exact Keyword Match > Exact PT Match > Existing
        if col_kw in df.columns:
            df[col] = df[col].fillna(df[col_kw])
        if col_pt in df.columns:
            df[col] = df[col].fillna(df[col_pt])
            
    # Fallback: Campaign/Ad Group IDs if still missing
    missing_basics = df.get('CampaignId', pd.Series([np.nan]*len(df))).isna() | df.get('AdGroupId', pd.Series([np.nan]*len(df))).isna()
    if missing_basics.any():
        fallback_lookup = bulk.groupby(['_camp_norm', '_ag_norm'])[['CampaignId', 'AdGroupId']].first().reset_index()
        df = df.merge(fallback_lookup, on=['_camp_norm', '_ag_norm'], how='left', suffixes=('', '_fallback'))
        
        df['CampaignId'] = df.get('CampaignId', pd.Series([np.nan]*len(df))).fillna(df.get('CampaignId_fallback', pd.Series([np.nan]*len(df))))
        df['AdGroupId'] = df.get('AdGroupId', pd.Series([np.nan]*len(df))).fillna(df.get('AdGroupId_fallback', pd.Series([np.nan]*len(df))))

    # Sync Recommendation Objects
    if 'recommendation' in df.columns:
        def sync_rec(row):
            rec = row['recommendation']
            if not isinstance(rec, OptimizationRecommendation):
                return rec
            
            # Use mapped IDs - handle empty strings as None
            def get_id(val):
                if pd.isna(val) or str(val).strip() == "":
                    return None
                return str(val)

            rec.campaign_id = get_id(row.get('CampaignId')) or rec.campaign_id
            rec.ad_group_id = get_id(row.get('AdGroupId')) or rec.ad_group_id
            rec.keyword_id = get_id(row.get('KeywordId')) or rec.keyword_id
            rec.product_targeting_id = get_id(row.get('TargetingId')) or rec.product_targeting_id
            
            # Re-validate
            rec.validation_result = validate_recommendation(rec)
            return rec
            
        df['recommendation'] = df.apply(sync_rec, axis=1)

    # Cleanup internal columns
    drop_cols = [c for c in df.columns if c.startswith('_') or c.endswith('_bulk_kw') or c.endswith('_bulk_pt') or c.endswith('_fallback')]
    df.drop(columns=drop_cols, inplace=True, errors='ignore')
    
    return df


def identify_negative_candidates(
    df: pd.DataFrame, 
    config: dict, 
    harvest_df: pd.DataFrame,
    account_benchmarks: dict = None
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Identify negative keyword candidates:
    1. Isolation negatives - harvest terms to negate in source campaigns (unique per campaign/ad group)
    2. Performance negatives - bleeders with 0 sales, high spend (CVR-based thresholds)
    3. ASIN Mapper integration - competitor ASINs flagged for negation
    
    CHANGES:
    - Uses CVR-based dynamic thresholds for hard stop
    
    Returns: (keyword_negatives_df, product_target_negatives_df, your_products_review_df)
    """
    # Get account benchmarks for CVR-based thresholds
    if account_benchmarks is None:
        account_benchmarks = calculate_account_benchmarks(df, config)
    
    soft_threshold = account_benchmarks['soft_threshold']
    hard_stop_threshold = account_benchmarks['hard_stop_threshold']
    
    negatives = []
    your_products_review = []
    seen_keys = set()  # Track (campaign, ad_group, term) for uniqueness
    
    # Stage 1: Isolation negatives
    if not harvest_df.empty:
        harvested_terms = set(
            harvest_df["Customer Search Term"].astype(str).str.strip().str.lower()
        )
        
        # Strip PT prefixes from main df for accurate matching
        df_cst_clean = df["Customer Search Term"].apply(strip_targeting_prefix).astype(str).str.strip().str.lower()
        
        # Find all occurrences in non-exact campaigns
        # EXCLUDE harvest destination campaigns from receiving isolation negatives
        harvest_dest_pattern = r'harvestexact|harvest_exact|_exact_|exactmatch'
        is_harvest_destination = df["Campaign Name"].str.contains(harvest_dest_pattern, case=False, na=False)
        
        isolation_mask = (
            df_cst_clean.isin(harvested_terms) &
            (~df["Match Type"].str.contains("exact", case=False, na=False)) &
            (~df["Match Type"].str.upper().isin(["PT", "PRODUCT TARGETING"])) &
            (~is_harvest_destination)
        )
        
        isolation_df = df[isolation_mask].copy()
        # Store the cleaned term for grouping
        isolation_df["_cst_clean"] = df_cst_clean[isolation_mask]
        
        # Aggregate logic for Isolation Negatives (Fix for "metrics broken down by date")
        if not isolation_df.empty:
            # Group by CLEANED term to match harvest (prefixes already stripped)
            agg_cols = {"Clicks": "sum", "Spend": "sum"}
            meta_cols = {c: "first" for c in ["CampaignId", "AdGroupId", "KeywordId", "TargetingId", "Campaign Targeting Type"] if c in isolation_df.columns}
            
            isolation_agg = isolation_df.groupby(
                ["Campaign Name", "Ad Group Name", "_cst_clean"], as_index=False
            ).agg({**agg_cols, **meta_cols})
            isolation_agg = isolation_agg.rename(columns={"_cst_clean": "Customer Search Term"})
            
            # Get winner campaign for each term (to exclude from negation)
            winner_camps = dict(zip(
                harvest_df["Customer Search Term"].str.lower(),
                harvest_df["Campaign Name"]
            ))
            
            for _, row in isolation_agg.iterrows():
                campaign = row["Campaign Name"]
                ad_group = row["Ad Group Name"]
                term = str(row["Customer Search Term"]).strip().lower()
                
                # Skip the winner campaign - don't negate where we're promoting
                if campaign == winner_camps.get(term):
                    continue
                
                # Unique key per campaign/ad group (redundant after groupby but good for safety)
                key = (campaign, ad_group, term)
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                
                
                # Create recommendation object for validation
                rec = OptimizationRecommendation(
                    recommendation_id=f"iso_{campaign}_{term}",
                    recommendation_type=RecommendationType.NEGATIVE_ISOLATION,
                    campaign_name=campaign,
                    campaign_id=row.get("CampaignId", ""),
                    campaign_targeting_type=row.get("Campaign Targeting Type", "Manual"),
                    ad_group_name=None, # Isolation is campaign-level
                    keyword_text=term,
                    match_type="campaign negative exact",
                    currency=config.get("currency", "AED")
                )
                rec.validation_result = validate_recommendation(rec)
                
                negatives.append({
                    "Type": "Isolation",
                    "Campaign Name": campaign,
                    "Ad Group Name": ad_group,
                    "Term": term,
                    "Is_ASIN": is_asin(term),
                    "Clicks": row["Clicks"],
                    "Spend": row["Spend"],
                    "CampaignId": row.get("CampaignId", ""),
                    "AdGroupId": row.get("AdGroupId", ""),
                    "KeywordId": row.get("KeywordId", ""),
                    "TargetingId": row.get("TargetingId", ""),
                    "recommendation": rec # Store for UI and Export
                })
    
    # Stage 2: Performance negatives (bleeders) - CVR-BASED THRESHOLDS
    non_exact_mask = ~df["Match Type"].str.contains("exact", case=False, na=False)
    # Don't filter Sales==0 yet - wait until aggregated
    bleeders = df[non_exact_mask].copy()
    
    if not bleeders.empty:
        # Group by lowercased term to avoid case-based duplicates
        bleeders['_term_norm_group'] = bleeders['Customer Search Term'].astype(str).str.strip().str.lower()
        
        # Aggregate by campaign + ad group + term
        agg_cols = {"Clicks": "sum", "Spend": "sum", "Impressions": "sum", "Sales": "sum"}
        meta_cols = {c: "first" for c in ["CampaignId", "AdGroupId", "KeywordId", "TargetingId", "Campaign Targeting Type"] if c in bleeders.columns}
        
        bleeder_agg = bleeders.groupby(
            ["Campaign Name", "Ad Group Name", "_term_norm_group"], as_index=False
        ).agg({**agg_cols, **meta_cols})
        bleeder_agg = bleeder_agg.rename(columns={"_term_norm_group": "Customer Search Term"})
        
        # Apply CVR-based thresholds (Sales == 0 AND Clicks > threshold)
        # Currency threshold removed - only clicks-based logic
        bleeder_mask = (
            (bleeder_agg["Sales"] == 0) &
            (bleeder_agg["Clicks"] >= soft_threshold)
        )
        
        for _, row in bleeder_agg[bleeder_mask].iterrows():
            campaign = row["Campaign Name"]
            ad_group = row["Ad Group Name"]
            term = str(row["Customer Search Term"]).strip().lower()
            
            key = (campaign, ad_group, term)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            
            # Use CVR-based hard stop threshold
            reason = "Hard Stop" if row["Clicks"] >= hard_stop_threshold else "Performance"
            
            # Create recommendation object for validation
            rec = OptimizationRecommendation(
                recommendation_id=f"bld_{campaign}_{ad_group}_{term}",
                recommendation_type=RecommendationType.NEGATIVE_BLEEDER,
                campaign_name=campaign,
                campaign_id=row.get("CampaignId", ""),
                campaign_targeting_type=row.get("Campaign Targeting Type", "Manual"),
                ad_group_name=ad_group,
                ad_group_id=row.get("AdGroupId", ""),
                keyword_text=term,
                match_type="negative exact",
                currency=config.get("currency", "AED")
            )
            rec.validation_result = validate_recommendation(rec)
            
            negatives.append({
                "Type": f"Bleeder ({reason})",
                "Campaign Name": campaign,
                "Ad Group Name": ad_group,
                "Term": term,
                "Is_ASIN": is_asin(term),
                "Clicks": row["Clicks"],
                "Spend": row["Spend"],
                "CampaignId": row.get("CampaignId", ""),
                "AdGroupId": row.get("AdGroupId", ""),
                "KeywordId": row.get("KeywordId", ""),
                "TargetingId": row.get("TargetingId", ""),
                "recommendation": rec # Store for UI and Export
            })
    
    # Stage 3: ASIN Mapper Integration
    asin_mapper_stats = {'total': 0, 'added': 0, 'duplicates': 0}
    
    if 'latest_asin_analysis' in st.session_state:
        asin_results = st.session_state['latest_asin_analysis']
        
        if 'optimizer_negatives' in asin_results:
            optimizer_data = asin_results['optimizer_negatives']
            
            # Add competitor ASINs (auto-negate recommended)
            competitor_asins = optimizer_data.get('competitor_asins', [])
            asin_mapper_stats['total'] = len(competitor_asins)
            
            for asin_neg in competitor_asins:
                term = asin_neg['Term'].lower()
                campaign = asin_neg.get('Campaign Name', '')
                ad_group = asin_neg.get('Ad Group Name', '')
                
                key = (campaign, ad_group, term)
                if key in seen_keys:
                    asin_mapper_stats['duplicates'] += 1
                    continue
                seen_keys.add(key)
                
                negatives.append(asin_neg)
                asin_mapper_stats['added'] += 1
            
            # Collect your products for separate review section
            your_products_review = optimizer_data.get('your_products_review', [])
    
    neg_df = pd.DataFrame(negatives)
    your_products_df = pd.DataFrame(your_products_review)
    
    if neg_df.empty:
        empty = pd.DataFrame(columns=["Campaign Name", "Ad Group Name", "Term", "Match Type"])
        return empty.copy(), empty.copy(), your_products_df
    
    # CRITICAL: Map KeywordId and TargetingId for negatives
    # Negatives are at campaign+adgroup+term level, so we need to look up IDs
    # FINAL ENRICHMENT: Map IDs from Bulk for export
    # NOTE: Calling DataHub() inside might cause circular imports if not careful.
    # It's better to pass ID mapping as argument, but for now we'll assume DataHub is safe here.
    neg_df = enrich_with_ids(neg_df, DataHub().get_data('bulk_id_mapping'))
    
    # Split into keywords vs product targets
    neg_kw = neg_df[~neg_df["Is_ASIN"]].copy()
    neg_pt = neg_df[neg_df["Is_ASIN"]].copy()
    
    # Format for output
    if not neg_kw.empty:
        neg_kw["Match Type"] = "negativeExact"
    if not neg_pt.empty:
        neg_pt["Match Type"] = "Negative Product Targeting"
        neg_pt["Term"] = neg_pt["Term"].apply(lambda x: f'asin="{x.upper()}"')
    
    # Store ASIN Mapper stats for UI display
    st.session_state['asin_mapper_integration_stats'] = asin_mapper_stats
    
    return neg_kw, neg_pt, your_products_df
