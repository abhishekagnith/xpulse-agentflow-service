"""
Script to fix node_detail table entries by converting hyphens to underscores.

The issue: Flow nodes use underscores (e.g., "button_question") but the database
has hyphens (e.g., "button-question"). This script:
1. Finds all node_details with hyphens in node_id
2. Creates new entries with underscores
3. Optionally removes old hyphenated entries

Run this script to fix the mismatch between flow node types and database node_ids.
"""

import asyncio
import sys
import os
from datetime import datetime

# Add src directory to path to import modules
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
src_dir = os.path.join(project_root, 'src')
sys.path.insert(0, src_dir)
sys.path.insert(0, project_root)

from utils.log_utils import LogUtil
from utils.environment_utils import EnvironmentUtils
from database.flow_db import FlowDB
from models.node_detail_data import NodeDetailData

# Mapping of hyphenated to underscore versions
HYPHEN_TO_UNDERSCORE_MAP = {
    "button-question": "button_question",
    "list-question": "list_question",
    "trigger-keyword": "trigger_keyword",
    "trigger-template": "trigger_template"
}


async def fix_node_detail_hyphens(delete_old: bool = False):
    """
    Fix node_detail entries by converting hyphens to underscores.
    
    Args:
        delete_old: If True, deletes old hyphenated entries after creating underscore versions
    """
    # Initialize utilities
    log_util = LogUtil()
    environment_utils = EnvironmentUtils(log_util=log_util)
    
    # Initialize database
    flow_db = FlowDB(log_util=log_util, environment_utils=environment_utils)
    
    try:
        log_util.info(
            service_name="FixNodeDetailHyphens",
            message="Starting node detail hyphen to underscore conversion..."
        )
        
        # Get all node details
        all_node_details = await flow_db.get_all_node_details()
        log_util.info(
            service_name="FixNodeDetailHyphens",
            message=f"Found {len(all_node_details)} node details in database"
        )
        
        # Find entries with hyphens that need to be converted
        hyphenated_entries = []
        for node_detail in all_node_details:
            if "-" in node_detail.node_id and node_detail.node_id in HYPHEN_TO_UNDERSCORE_MAP:
                hyphenated_entries.append(node_detail)
        
        log_util.info(
            service_name="FixNodeDetailHyphens",
            message=f"Found {len(hyphenated_entries)} entries with hyphens to convert"
        )
        
        if not hyphenated_entries:
            log_util.info(
                service_name="FixNodeDetailHyphens",
                message="No hyphenated entries found. Nothing to fix."
            )
            return
        
        # Create new entries with underscores
        created_count = 0
        updated_count = 0
        error_count = 0
        
        for old_node_detail in hyphenated_entries:
            try:
                new_node_id = HYPHEN_TO_UNDERSCORE_MAP[old_node_detail.node_id]
                
                # Check if underscore version already exists
                existing = await flow_db.get_node_detail_by_id(new_node_id)
                
                if existing:
                    log_util.info(
                        service_name="FixNodeDetailHyphens",
                        message=f"Entry with node_id '{new_node_id}' already exists, skipping creation"
                    )
                    updated_count += 1
                else:
                    # Create new entry with underscore
                    new_node_detail = NodeDetailData(
                        node_id=new_node_id,
                        node_name=old_node_detail.node_name,
                        category=old_node_detail.category,
                        user_input_required=old_node_detail.user_input_required,
                        is_internal=old_node_detail.is_internal,
                        created_at=old_node_detail.created_at,
                        updated_at=datetime.utcnow()
                    )
                    
                    result = await flow_db.upsert_node_detail(new_node_detail)
                    
                    if result:
                        created_count += 1
                        log_util.info(
                            service_name="FixNodeDetailHyphens",
                            message=f"[SUCCESS] Created: {old_node_detail.node_id} -> {new_node_id}"
                        )
                    else:
                        error_count += 1
                        log_util.error(
                            service_name="FixNodeDetailHyphens",
                            message=f"[ERROR] Failed to create: {old_node_detail.node_id} -> {new_node_id}"
                        )
                        
            except Exception as e:
                error_count += 1
                log_util.error(
                    service_name="FixNodeDetailHyphens",
                    message=f"[ERROR] Error processing {old_node_detail.node_id}: {str(e)}"
                )
        
        # Optionally delete old hyphenated entries
        deleted_count = 0
        if delete_old:
            log_util.info(
                service_name="FixNodeDetailHyphens",
                message="Deleting old hyphenated entries..."
            )
            
            for old_node_detail in hyphenated_entries:
                try:
                    result = await flow_db.delete_node_detail(old_node_detail.node_id)
                    if result:
                        deleted_count += 1
                        log_util.info(
                            service_name="FixNodeDetailHyphens",
                            message=f"[DELETED] Removed old entry: {old_node_detail.node_id}"
                        )
                except Exception as e:
                    log_util.error(
                        service_name="FixNodeDetailHyphens",
                        message=f"[ERROR] Error deleting {old_node_detail.node_id}: {str(e)}"
                    )
        
        # Summary
        log_util.info(
            service_name="FixNodeDetailHyphens",
            message=f"Conversion complete! Created: {created_count}, Already existed: {updated_count}, Errors: {error_count}"
        )
        
        if delete_old:
            log_util.info(
                service_name="FixNodeDetailHyphens",
                message=f"Deleted {deleted_count} old hyphenated entries"
            )
        
        # Display all node details
        all_nodes = await flow_db.get_all_node_details()
        log_util.info(
            service_name="FixNodeDetailHyphens",
            message=f"Total node details in database: {len(all_nodes)}"
        )
        
        print("\n" + "="*60)
        print("NODE DETAILS SUMMARY")
        print("="*60)
        for node in all_nodes:
            print(f"  • {node.node_name} ({node.node_id})")
            print(f"    Category: {node.category}, User Input Required: {node.user_input_required}")
            print()
        
        print("="*60)
        print(f"Total: {len(all_nodes)} nodes")
        print("="*60)
        
    except Exception as e:
        log_util.error(
            service_name="FixNodeDetailHyphens",
            message=f"Fatal error: {str(e)}"
        )
        print(f"❌ Fatal error: {str(e)}")
        raise
    finally:
        # Close database connection
        flow_db.close()
        log_util.info(
            service_name="FixNodeDetailHyphens",
            message="Database connection closed"
        )


if __name__ == "__main__":
    print("="*60)
    print("Node Detail Hyphen to Underscore Conversion Script")
    print("="*60)
    print("This script will:")
    print("  1. Find all node_details with hyphens (e.g., 'button-question')")
    print("  2. Create new entries with underscores (e.g., 'button_question')")
    print("  3. Optionally delete old hyphenated entries")
    print("="*60)
    print()
    
    # Ask user if they want to delete old entries
    delete_old = False
    if len(sys.argv) > 1 and sys.argv[1] == "--delete-old":
        delete_old = True
        print("⚠️  WARNING: Will delete old hyphenated entries after creating underscore versions")
    else:
        print("ℹ️  Old hyphenated entries will be kept (use --delete-old to remove them)")
    
    print()
    
    try:
        asyncio.run(fix_node_detail_hyphens(delete_old=delete_old))
        print("\n[SUCCESS] Script completed successfully!")
    except KeyboardInterrupt:
        print("\n[WARNING] Script interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Script failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

