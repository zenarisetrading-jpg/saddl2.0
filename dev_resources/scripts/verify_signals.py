
import time
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
from app_core.db_manager import get_db_manager

# Load environment variables
env_path = Path('../.env')
if env_path.exists():
    load_dotenv(env_path)
else:
    print(f"Warning: {env_path} not found")

# Get DB manager
db = get_db_manager(test_mode=False)

signals = [
    'signal_demand_contraction',
    'signal_organic_decay',
    'signal_non_advertised_winners',
    'signal_harvest_cannibalization',
    'signal_over_negation'
]

durations = []
failed = []

print('Signal View Query Performance:')
try:
    with db._get_connection() as conn:
        for signal in signals:
            start = time.time()
            try:
                # Use plain SQL via pandas
                query = f"SELECT COUNT(*) AS c FROM sc_analytics.{signal}"
                df = pd.read_sql_query(query, conn)
                n = int(df.iloc[0]['c'])
                dt = time.time() - start
                durations.append(dt)
                print(f'  {signal}: {dt:.2f}s (rows={n})')
            except Exception as e:
                dt = time.time() - start
                failed.append(signal)
                print(f'  {signal}: FAIL {dt:.2f}s ({e})')
except Exception as e:
    print(f"Connection failed: {e}")

print()
if failed:
    print(f'❌ Failed views: {len(failed)} -> {failed}')
else:
    if durations:
        print('✅ All queries < 2s' if all(d < 2 for d in durations) else '⚠️  Some queries slow')
    else:
        print('⚠️  No queries executed')
