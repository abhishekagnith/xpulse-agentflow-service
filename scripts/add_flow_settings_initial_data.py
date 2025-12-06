"""
Script to add initial flow settings data to the flow_settings collection.

This script adds the first flow settings entry with email source email configuration.
"""

import asyncio
import sys
import os
import random
import string

# Add src directory to path to import modules
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
src_dir = os.path.join(project_root, 'src')
sys.path.insert(0, src_dir)
sys.path.insert(0, project_root)

from utils.log_utils import LogUtil
from utils.environment_utils import EnvironmentUtils
from database.flow_db import FlowDB
from models.flow_settings_data import FlowSettingsData, EmailSettings


def generate_random_id(prefix: str = "", length: int = 24) -> str:
    """
    Generate a random ID similar to MongoDB ObjectId format.
    """
    chars = string.ascii_lowercase + string.digits
    random_id = ''.join(random.choice(chars) for _ in range(length))
    if prefix:
        return f"{prefix}-{random_id}"
    return random_id


async def add_initial_flow_settings():
    """
    Add initial flow settings data.
    """
    # Initialize utilities
    log_util = LogUtil()
    environment_utils = EnvironmentUtils(log_util=log_util)
    
    # Initialize database
    flow_db = FlowDB(log_util=log_util, environment_utils=environment_utils)
    
    try:
        log_util.info(
            service_name="AddFlowSettings",
            message="Starting to add initial flow settings..."
        )
        
        print("\n" + "="*60)
        print("Add Flow Settings - Initial Data")
        print("="*60)
        
        # Generate random flow_id and node_id
        flow_id = generate_random_id("flow", 24)
        node_id = generate_random_id("send_email_template-node", 16)
        
        print(f"\nGenerated Flow ID: {flow_id}")
        print(f"Generated Node ID: {node_id}")
        print(f"Source Email: abhishekag.nith@gmail.com")
        
        # Check if settings already exist (unlikely with random IDs, but check anyway)
        existing = await flow_db.get_flow_settings(flow_id, node_id)
        if existing:
            print(f"\n[WARNING] Flow settings already exist for flow_id={flow_id}, node_id={node_id}")
            print("[INFO] Overwriting existing settings...")
        
        # Create email settings with source email
        email_settings = EmailSettings(
            source_email="abhishekag.nith@gmail.com"
        )
        
        # Create flow settings
        flow_settings = FlowSettingsData(
            flow_id=flow_id,
            node_id=node_id,
            email=email_settings
        )
        
        # Save flow settings
        result = await flow_db.save_flow_settings(flow_settings)
        
        if result:
            log_util.info(
                service_name="AddFlowSettings",
                message=f"[SUCCESS] Successfully added/updated flow settings: flow_id={flow_id}, node_id={node_id}"
            )
            print(f"\n[SUCCESS] Successfully added/updated flow settings!")
            print(f"   Flow ID: {result.flow_id}")
            print(f"   Node ID: {result.node_id}")
            print(f"   Source Email: {result.email.source_email if result.email else 'N/A'}")
            print(f"   Settings ID: {result.id}")
        else:
            log_util.error(
                service_name="AddFlowSettings",
                message="[ERROR] Failed to add flow settings"
            )
            print("\n[ERROR] Failed to add flow settings")
            return False
        
        # Verify the settings were added
        verify_settings = await flow_db.get_flow_settings(flow_id, node_id)
        if verify_settings:
            print("\n[SUCCESS] Verification: Flow settings found in database")
            print(f"   Flow ID: {verify_settings.flow_id}")
            print(f"   Node ID: {verify_settings.node_id}")
            print(f"   Source Email: {verify_settings.email.source_email if verify_settings.email else 'N/A'}")
        else:
            print("\n[WARNING] Could not verify flow settings in database")
        
        return True
        
    except Exception as e:
        log_util.error(
            service_name="AddFlowSettings",
            message=f"Fatal error: {str(e)}"
        )
        print(f"\n[ERROR] Fatal error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        # Close database connection
        flow_db.close()
        log_util.info(
            service_name="AddFlowSettings",
            message="Database connection closed"
        )


if __name__ == "__main__":
    print("="*60)
    print("Add Flow Settings - Initial Data Script")
    print("="*60)
    print("This script will add flow settings with email source email")
    print("configuration to the flow_settings collection.")
    print("="*60)
    print()
    
    try:
        asyncio.run(add_initial_flow_settings())
        print("\n[SUCCESS] Script completed successfully!")
    except KeyboardInterrupt:
        print("\n[WARNING] Script interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Script failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

