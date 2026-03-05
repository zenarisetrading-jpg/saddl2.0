
import sys
import os

# Add root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))
# Add desktop to path (for internal imports like 'from features...')
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

print("Checking imports...")
try:
    import desktop.features.optimizer.core as core
    print(f"✅ Core Config Loaded: Launch Multiplier = {core.DEFAULT_CONFIG['HARVEST_LAUNCH_MULTIPLIER']}")
    
    from desktop.core.db_manager import DatabaseManager
    print("✅ DB Manager Loaded")
    
    from desktop.features.optimizer.strategies import harvest
    print("✅ Harvest Strategy Loaded")
    
    print("ALL SYSTEMS GO 🚀")
except ImportError as e:
    print(f"❌ Import Failed: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
