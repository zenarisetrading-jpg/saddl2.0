import os
import sys
import pandas as pd
import numpy as np
import lightgbm as lgb
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
import psycopg2
from sqlalchemy import create_engine
from datetime import timedelta
from dotenv import load_dotenv
import warnings
warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from app_core.constants import ACTION_MATURITY_DAYS

def get_db_connection():
    # Load .env from the current directory
    load_dotenv()
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        raise ValueError("DATABASE_URL not found in environment variables. Please check your .env file.")
    print("Connecting to database...")
    engine = create_engine(db_url)
    return engine

def load_data(engine):
    print("Loading data from database...")
    
    # Load actions log - focus on bid changes
    actions_query = """
    SELECT action_date, client_id, campaign_name, ad_group_name, target_text,
           old_value, new_value, reason
    FROM actions_log
    WHERE action_type = 'BID_CHANGE'
    """
    
    # Load target stats for performance
    stats_query = """
    SELECT client_id, start_date, campaign_name, ad_group_name, target_text, match_type,
           impressions, clicks, spend, sales, orders
    FROM target_stats
    """
    
    try:
        actions_df = pd.read_sql(actions_query, engine)
        stats_df = pd.read_sql(stats_query, engine)
        
        # Convert numeric columns
        actions_df['old_value'] = pd.to_numeric(actions_df['old_value'], errors='coerce')
        actions_df['new_value'] = pd.to_numeric(actions_df['new_value'], errors='coerce')
        actions_df['action_date'] = pd.to_datetime(actions_df['action_date'])
        
        stats_df['start_date'] = pd.to_datetime(stats_df['start_date'])
        for col in ['impressions', 'clicks', 'spend', 'sales', 'orders']:
            stats_df[col] = pd.to_numeric(stats_df[col], errors='coerce').fillna(0)
            
        print(f"Loaded {len(actions_df)} bid changes and {len(stats_df)} daily performance records.")
        return actions_df, stats_df
    except Exception as e:
        print(f"Error loading data: {e}")
        raise

def build_training_dataset(actions_df, stats_df):
    print("Building training dataset...")
    if actions_df.empty or stats_df.empty:
        print("Empty data, returning empty dataset.")
        return pd.DataFrame()
        
    dataset = []
    
    # Group stats for faster lookup
    # Add a mock combination key
    stats_df['key'] = stats_df['client_id'].astype(str) + "|" + stats_df['campaign_name'] + "|" + stats_df['ad_group_name'] + "|" + stats_df['target_text']
    
    # Optimize by indexing target_stats
    stats_indexed = stats_df.set_index(['key', 'start_date']).sort_index()

    for i, row in actions_df.iterrows():
        if pd.isna(row['old_value']) or pd.isna(row['new_value']) or row['old_value'] <= 0:
            continue
            
        key = f"{row['client_id']}|{row['campaign_name']}|{row['ad_group_name']}|{row['target_text']}"
        action_date = row['action_date']
        
        # ACTION_MATURITY_DAYS pre/post windows
        pre_start = action_date - timedelta(days=ACTION_MATURITY_DAYS)
        pre_end = action_date - timedelta(days=1)
        post_start = action_date
        post_end = action_date + timedelta(days=29)
        
        # Try to extract the time periods efficiently
        try:
            # Slicing the MultiIndex
            pre_stats = stats_indexed.loc[(key, slice(pre_start, pre_end)), :]
            post_stats = stats_indexed.loc[(key, slice(post_start, post_end)), :]
        except KeyError:
            # Key doesn't exist in target_stats
            continue
            
        if pre_stats.empty or post_stats.empty:
            continue
            
        # Aggregate stats
        def aggregate_metrics(df_window):
            """Returns ACoS as a percentage (0-100), not a ratio."""
            clicks = df_window['clicks'].sum()
            spend = df_window['spend'].sum()
            sales = df_window['sales'].sum()
            orders = df_window['orders'].sum()
            impressions = df_window['impressions'].sum()
            days = len(df_window)

            return {
                'clicks': clicks,
                'spend': spend,
                'sales': sales,
                'orders': orders,
                'impressions': impressions,
                'days': days,
                'acos': (spend / sales * 100) if sales > 0 else 0,
                'roas': sales / spend if spend > 0 else 0,
                'cvr': orders / clicks if clicks > 0 else 0,
                'ctr': clicks / impressions if impressions > 0 else 0,
                'avg_spend': spend / days if days > 0 else 0
            }
            
        pre_metrics = aggregate_metrics(pre_stats)
        post_metrics = aggregate_metrics(post_stats)
        
        # We need somewhat meaningful pre-data to learn from
        if pre_metrics['clicks'] == 0:
            continue
            
        # Label: Did ROAS improve?
        outcome = 1 if post_metrics['roas'] > pre_metrics['roas'] else 0
        
        # Bid change pct
        bid_change_pct = (row['new_value'] - row['old_value']) / row['old_value']
        
        match_type = pre_stats['match_type'].iloc[0] if 'match_type' in pre_stats.columns and not pd.isna(pre_stats['match_type'].iloc[0]) else 'unknown'
        
        dataset.append({
            'client_id': row['client_id'],
            'campaign_name': row['campaign_name'],
            'ad_group_name': row['ad_group_name'],
            'target_text': row['target_text'],
            'pre_acos': pre_metrics['acos'],
            'pre_roas': pre_metrics['roas'],
            'pre_cvr': pre_metrics['cvr'],
            'pre_ctr': pre_metrics['ctr'],
            'pre_avg_spend': pre_metrics['avg_spend'],
            'pre_clicks_14d': pre_metrics['clicks'],
            'bid_change_pct': bid_change_pct,
            'match_type': match_type,
            'days_since_last_change': 14, # Placeholder, hard to calculate fast without lead/lag
            'outcome': outcome,
            'current_bid': row['new_value']
        })
        
        if len(dataset) % 1000 == 0:
            print(f"Processed {len(dataset)} valid bid change events...")
            
    print(f"Generated {len(dataset)} training examples.")
    return pd.DataFrame(dataset)

def train_model(train_df):
    print("\\n--- Step 3: Train Model ---")
    if train_df.empty:
        print("No data to train on.")
        return None, None
        
    # Feature engineering
    features = ['pre_acos', 'pre_roas', 'pre_cvr', 'pre_ctr', 'pre_avg_spend', 
                'pre_clicks_14d', 'bid_change_pct', 'match_type_encoded', 'days_since_last_change']
                
    # Encode categorical
    le = LabelEncoder()
    train_df['match_type_encoded'] = le.fit_transform(train_df['match_type'].astype(str))
    
    X = train_df[features]
    y = train_df['outcome']
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    print(f"Training on {len(X_train)} samples, testing on {len(X_test)} samples.")
    
    model = lgb.LGBMClassifier(n_estimators=100, learning_rate=0.05, random_state=42)
    model.fit(X_train, y_train)
    
    accuracy = model.score(X_test, y_test)
    print(f"\\nModel Accuracy on test set: {accuracy:.4f}")
    
    # Feature importance
    importance = pd.DataFrame({
        'feature': features,
        'importance': model.feature_importances_
    }).sort_values('importance', ascending=False)
    
    print("\\nFeature Importance:")
    print(importance)
    
    return model, le

def generate_recommendations(model, le, stats_df, actions_df):
    print("\\n--- Step 4: Generate Recommendations ---")
    if model is None or stats_df.empty:
        print("Cannot generate recommendations without model and stats.")
        return None
        
    print("Finding active targets (last 30 days)...")
    # Get last 30 days of data
    max_date = stats_df['start_date'].max()
    if pd.isna(max_date):
        return None
        
    active_mask = stats_df['start_date'] >= (max_date - timedelta(days=30))
    active_stats = stats_df[active_mask].copy()
    
    # Calculate current 14d performance for active targets
    active_stats['key'] = active_stats['client_id'].astype(str) + "|" + active_stats['campaign_name'] + "|" + active_stats['ad_group_name'] + "|" + active_stats['target_text']
    
    # Get the latest bid for each target from actions_log
    actions_df['key'] = actions_df['client_id'].astype(str) + "|" + actions_df['campaign_name'] + "|" + actions_df['ad_group_name'] + "|" + actions_df['target_text']
    latest_bids = actions_df.sort_values('action_date').groupby('key')['new_value'].last().reset_index()
    latest_bids.columns = ['key', 'last_known_bid']
    
    # Group by target
    grouped = active_stats.groupby(['key', 'client_id', 'campaign_name', 'ad_group_name', 'target_text', 'match_type']).agg({
        'clicks': 'sum',
        'spend': 'sum',
        'sales': 'sum',
        'orders': 'sum',
        'impressions': 'sum',
        'start_date': 'nunique' # days active
    }).reset_index()
    
    grouped = grouped.merge(latest_bids, on='key', how='left')
    grouped['last_known_bid'] = grouped['last_known_bid'].fillna(1.0) # default fallback
    
    recs = []
    
    # Test possible changes: +20%, 0%, -20%
    test_changes = [0.20, 0.0, -0.20]
    
    for i, row in grouped.iterrows():
        if row['clicks'] < 5: # Need some data
            continue
            
        pre_acos = row['spend'] / row['sales'] if row['sales'] > 0 else 0
        pre_roas = row['sales'] / row['spend'] if row['spend'] > 0 else 0
        pre_cvr = row['orders'] / row['clicks'] if row['clicks'] > 0 else 0
        pre_ctr = row['clicks'] / row['impressions'] if row['impressions'] > 0 else 0
        pre_avg_spend = row['spend'] / row['start_date'] if row['start_date'] > 0 else 0
        
        match_type_encoded = le.transform([str(row['match_type'])])[0] if str(row['match_type']) in le.classes_ else 0
        
        best_pred_prob = -1
        best_change = 0
        
        for change_pct in test_changes:
            features = pd.DataFrame([{
                'pre_acos': pre_acos,
                'pre_roas': pre_roas,
                'pre_cvr': pre_cvr,
                'pre_ctr': pre_ctr,
                'pre_avg_spend': pre_avg_spend,
                'pre_clicks_14d': row['clicks'],
                'bid_change_pct': change_pct,
                'match_type_encoded': match_type_encoded,
                'days_since_last_change': 14
            }])
            
            # Predict probability of ROAS improvement (outcome=1)
            prob = model.predict_proba(features)[0][1]
            
            if prob > best_pred_prob:
                best_pred_prob = prob
                best_change = change_pct
                
        # Confidence logic
        confidence = best_pred_prob
        
        direction = 'hold'
        if best_change > 0: direction = 'increase'
        elif best_change < 0: direction = 'decrease'
        
        # Don't change if confidence isn't high enough
        if confidence < 0.55:
            direction = 'hold'
            best_change = 0.0
            
        current_bid = row['last_known_bid']
        recommended_bid = current_bid * (1 + best_change)
        
        recs.append({
            'client_id': row['client_id'],
            'campaign_name': row['campaign_name'],
            'ad_group_name': row['ad_group_name'],
            'target_text': row['target_text'],
            'current_bid': current_bid,
            'recommended_bid': round(recommended_bid, 2),
            'adjustment_pct': best_change,
            'model_confidence': round(confidence, 3),
            'predicted_roas_direction': direction
        })
        
        if len(recs) % 1000 == 0:
            print(f"Generated {len(recs)} recommendations...")
            
    recs_df = pd.DataFrame(recs)
    print(f"Total recommendations generated: {len(recs_df)}")
    
    output_path = 'ml_recs_30d.csv'
    recs_df.to_csv(output_path, index=False)
    print(f"Saved recommendations to {output_path}")
    
    return recs_df

def main():
    print("Starting ML Bid Optimizer...")
    try:
        engine = get_db_connection()
        actions_df, stats_df = load_data(engine)
        
        train_df = build_training_dataset(actions_df, stats_df)
        
        if not train_df.empty:
            model, le = train_model(train_df)
            
            # Filter for specific clients
            clients = ['s2c_uae_test', 's2c_test']
            stats_df_client = stats_df[stats_df['client_id'].isin(clients)].copy()
            actions_df_client = actions_df[actions_df['client_id'].isin(clients)].copy()
            
            print(f"Generating recommendations ONLY for clients: {clients}")
            generate_recommendations(model, le, stats_df_client, actions_df_client)
        else:
            print("Training dataset is empty. Cannot continue.")
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
