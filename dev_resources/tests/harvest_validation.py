import os
import sys
import pandas as pd
import psycopg2
from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
load_dotenv()

def run_harvest_validation():
    conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
    
    # Get all harvests
    query = """
    SELECT 
        client_id, action_date, target_text, 
        winner_source_campaign as source_campaign, 
        new_campaign_name as dest_campaign
    FROM actions_log
    WHERE action_type = 'HARVEST';
    """
    
    harvests = pd.read_sql(query, conn)
    
    results = []
    
    for _, row in harvests.iterrows():
        client_id = row['client_id']
        target_text = row['target_text']
        action_date = row['action_date']
        source_campaign = row['source_campaign']
        dest_campaign = row['dest_campaign']
        
        # 30 days before action
        before_query = """
        SELECT 
            SUM(spend) as spend, SUM(sales) as sales, 
            SUM(clicks) as clicks, SUM(orders) as orders
        FROM target_stats
        WHERE client_id = %s
          AND target_text = %s
          AND start_date >= %s - INTERVAL '30 days'
          AND start_date <= %s
        """
        
        # Adding campaign filter if source_campaign is available
        b_params = [client_id, target_text, action_date, action_date]
        if source_campaign and pd.notna(source_campaign):
            before_query += " AND campaign_name = %s"
            b_params.append(source_campaign)
            
        with conn.cursor() as cur:
            cur.execute(before_query, tuple(b_params))
            before_res = cur.fetchone()
            b_spend = float(before_res[0] or 0)
            b_sales = float(before_res[1] or 0)
            b_clicks = float(before_res[2] or 0)
            b_orders = float(before_res[3] or 0)
            
        b_roas = b_sales / b_spend if b_spend > 0 else 0
        b_cvr = b_orders / b_clicks if b_clicks > 0 else 0
        b_cpc = b_spend / b_clicks if b_clicks > 0 else 0
        
        after_query = """
        SELECT 
            SUM(spend) as spend, SUM(sales) as sales, 
            SUM(clicks) as clicks, SUM(orders) as orders
        FROM target_stats
        WHERE client_id = %s
          AND target_text = %s
          AND start_date >= %s
          AND start_date <= %s + INTERVAL '30 days'
        """
        
        # Filtering for exact match or specific dest_campaign
        a_params = [client_id, target_text, action_date, action_date]
        if dest_campaign and pd.notna(dest_campaign):
            after_query += " AND campaign_name = %s"
            a_params.append(dest_campaign)
        else:
            after_query += " AND match_type = 'exact' AND campaign_name ILIKE '%%harvest%%'"
            
        with conn.cursor() as cur:
            cur.execute(after_query, tuple(a_params))
            after_res = cur.fetchone()
            a_spend = float(after_res[0] or 0)
            a_sales = float(after_res[1] or 0)
            a_clicks = float(after_res[2] or 0)
            a_orders = float(after_res[3] or 0)
            
        a_roas = a_sales / a_spend if a_spend > 0 else 0
        a_cvr = a_orders / a_clicks if a_clicks > 0 else 0
        a_cpc = a_spend / a_clicks if a_clicks > 0 else 0
        
        if b_roas > 0:
            eff_delta = (a_roas - b_roas) / b_roas
        elif a_roas > 0:
            eff_delta = a_roas # Going from 0 to positive ROAS is an infinite % increase, cap it visually or represent as absolute if needed, using absolute ROAS here.
        else:
            eff_delta = 0
            
        classification = "Failed"
        if eff_delta > 0.30:
            classification = "Strong"
        elif eff_delta > 0:
            classification = "Weak"
            
        if a_spend == 0:
            classification = "No Data"
            
        results.append({
            "client_id": client_id,
            "target_text": target_text,
            "action_date": action_date,
            "source_campaign": source_campaign,
            "dest_campaign": dest_campaign,
            "before_spend": b_spend,
            "before_sales": b_sales,
            "before_roas": b_roas,
            "before_cvr": b_cvr,
            "before_cpc": b_cpc,
            "after_spend": a_spend,
            "after_sales": a_sales,
            "after_roas": a_roas,
            "after_cvr": a_cvr,
            "after_cpc": a_cpc,
            "efficiency_delta": eff_delta,
            "classification": classification
        })
        
    res_df = pd.DataFrame(results)
    if res_df.empty:
        print("\n--- HARVEST VALIDATION SUMMARY ---")
        print("No HARVEST actions found in the database. Cannot calculate efficiency gain.")
        return
        
    res_df.to_csv('harvest_validation.csv', index=False)
    
    # summary
    has_data = res_df[res_df['classification'] != 'No Data']
    
    print("\n--- HARVEST VALIDATION SUMMARY ---")
    print(f"Total HARVEST actions found: {len(res_df)}")
    if not has_data.empty:
        avg_eff_gain = has_data['efficiency_delta'].mean()
        print(f"Total items with post-harvest data: {len(has_data)}")
        print(f"Average Efficiency Gain (ROAS Delta %): {avg_eff_gain:.2%}")
        
        strong = len(has_data[has_data['classification'] == 'Strong'])
        weak = len(has_data[has_data['classification'] == 'Weak'])
        failed = len(has_data[has_data['classification'] == 'Failed'])
        
        print("\nClassifications:")
        print(f"Strong (>30% gain) : {strong} ({strong/len(has_data):.1%})")
        print(f"Weak (0-30% gain)  : {weak} ({weak/len(has_data):.1%})")
        print(f"Failed (<0% gain)  : {failed} ({failed/len(has_data):.1%})")
        
        avg_b_roas = has_data['before_roas'].mean()
        avg_a_roas = has_data['after_roas'].mean()
        avg_b_cvr = has_data['before_cvr'].mean()
        avg_a_cvr = has_data['after_cvr'].mean()
        avg_b_cpc = has_data['before_cpc'].mean()
        avg_a_cpc = has_data['after_cpc'].mean()
        
        print("\nMetric Averages:")
        print(f"ROAS: {avg_b_roas:.2f}x -> {avg_a_roas:.2f}x")
        print(f"CVR:  {avg_b_cvr:.2%} -> {avg_a_cvr:.2%}")
        print(f"CPC:  {avg_b_cpc:.2f} -> {avg_a_cpc:.2f}")
    else:
        print("No harvest actions have post-harvest data available.")
        
    print("\n--- CLIENT BREAKDOWN ---")
    print("Found Harvest Actions from:")
    print(res_df['client_id'].value_counts().to_string())
    if not has_data.empty:
        print("\nSuccessfully Matched Post-Harvest Data from:")
        print(has_data['client_id'].value_counts().to_string())
        
    print("\nDetailed results saved to harvest_validation.csv")

if __name__ == "__main__":
    run_harvest_validation()
