"""
Script to add "draft" status to existing flow data in the flows collection.

This migration script:
- Updates all flows that don't have a status field
- Sets status="draft" for all existing flows
- Safe to run multiple times (idempotent)

Run this script once after adding the status field to FlowData model.
"""

import asyncio
import sys
import os

# Add src directory to path to import modules
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
src_dir = os.path.join(project_root, 'src')
sys.path.insert(0, src_dir)
sys.path.insert(0, project_root)

from utils.log_utils import LogUtil
from utils.environment_utils import EnvironmentUtils
from database.flow_db import FlowDB


async def add_draft_status_to_flows():
    """
    Add "draft" status to all existing flows that don't have a status field.
    """
    # Initialize utilities
    log_util = LogUtil()
    environment_utils = EnvironmentUtils(log_util=log_util)
    
    # Initialize database
    flow_db = FlowDB(log_util=log_util, environment_utils=environment_utils)
    
    try:
        log_util.info(
            service_name="AddDraftStatus",
            message="Starting migration to add draft status to existing flows..."
        )
        
        # Get MongoDB client and collections
        client_data = flow_db._get_client_for_current_loop()
        collection = client_data['collections']['flows']
        
        # Find all flows that don't have a status field or have a different status
        # We'll update all flows to have status="draft"
        query = {
            "$or": [
                {"status": {"$exists": False}},  # No status field
                {"status": {"$ne": "draft"}}     # Status exists but is not "draft"
            ]
        }
        
        # Count flows to be updated
        count = await collection.count_documents(query)
        
        if count == 0:
            log_util.info(
                service_name="AddDraftStatus",
                message="No flows need to be updated. All flows already have status='draft'."
            )
            print("\n✅ No flows need to be updated. All flows already have status='draft'.")
            return
        
        log_util.info(
            service_name="AddDraftStatus",
            message=f"Found {count} flow(s) that need to be updated."
        )
        print(f"\n📊 Found {count} flow(s) that need to be updated.")
        
        # Update all matching flows
        result = await collection.update_many(
            query,
            {
                "$set": {
                    "status": "draft"
                }
            }
        )
        
        updated_count = result.modified_count
        
        log_util.info(
            service_name="AddDraftStatus",
            message=f"Successfully updated {updated_count} flow(s) with status='draft'."
        )
        
        # Verify the update
        remaining_count = await collection.count_documents({
            "$or": [
                {"status": {"$exists": False}},
                {"status": {"$ne": "draft"}}
            ]
        })
        
        # Get total flow count
        total_count = await collection.count_documents({})
        draft_count = await collection.count_documents({"status": "draft"})
        
        # Summary
        print("\n" + "="*60)
        print("MIGRATION SUMMARY")
        print("="*60)
        print(f"  Total flows in database: {total_count}")
        print(f"  Flows updated: {updated_count}")
        print(f"  Flows with status='draft': {draft_count}")
        print(f"  Flows still needing update: {remaining_count}")
        print("="*60)
        
        if remaining_count == 0:
            log_util.info(
                service_name="AddDraftStatus",
                message="✅ Migration completed successfully! All flows now have status='draft'."
            )
            print("\n✅ Migration completed successfully!")
            print("   All flows now have status='draft'.")
        else:
            log_util.warning(
                service_name="AddDraftStatus",
                message=f"⚠️  Migration completed but {remaining_count} flow(s) still need updating."
            )
            print(f"\n⚠️  Warning: {remaining_count} flow(s) still need updating.")
        
    except Exception as e:
        log_util.error(
            service_name="AddDraftStatus",
            message=f"Fatal error during migration: {str(e)}"
        )
        print(f"\n❌ Fatal error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        # Close database connection
        flow_db.close()
        log_util.info(
            service_name="AddDraftStatus",
            message="Database connection closed"
        )


if __name__ == "__main__":
    print("="*60)
    print("Add Draft Status to Existing Flows - Migration Script")
    print("="*60)
    print("This script will:")
    print("  • Find all flows without a status field")
    print("  • Set status='draft' for all existing flows")
    print("  • Safe to run multiple times (idempotent)")
    print("="*60)
    print()
    
    try:
        asyncio.run(add_draft_status_to_flows())
        print("\n[SUCCESS] Script completed successfully!")
    except KeyboardInterrupt:
        print("\n[WARNING] Script interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Script failed with error: {str(e)}")
        sys.exit(1)

