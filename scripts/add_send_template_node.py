"""
Script to add the "send_template" node to the node_details collection.

This script adds the new "send_template" node type which is used for sending
WhatsApp template messages with dynamic header values and button URLs.

Run this script to add the send_template node to the database.
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
from models.node_detail_data import NodeDetailData


async def add_send_template_node():
    """
    Add the send_template node to the node_details collection.
    """
    # Initialize utilities
    log_util = LogUtil()
    environment_utils = EnvironmentUtils(log_util=log_util)
    
    # Initialize database
    flow_db = FlowDB(log_util=log_util, environment_utils=environment_utils)
    
    try:
        log_util.info(
            service_name="AddSendTemplateNode",
            message="Starting to add send_template node..."
        )
        
        # Create NodeDetailData object for send_template
        node_detail = NodeDetailData(
            node_id="send_template",
            node_name="Send Template",
            category="Action",
            user_input_required=False,  # Template messages don't require user input
            is_internal=False  # This is an external action node
        )
        
        # Check if node already exists
        existing = await flow_db.get_node_detail_by_id("send_template")
        if existing:
            log_util.info(
                service_name="AddSendTemplateNode",
                message="send_template node already exists. Updating..."
            )
            # Update existing node
            result = await flow_db.update_node_detail("send_template", node_detail)
        else:
            log_util.info(
                service_name="AddSendTemplateNode",
                message="Creating new send_template node..."
            )
            # Create new node
            result = await flow_db.create_node_detail(node_detail)
        
        if result:
            log_util.info(
                service_name="AddSendTemplateNode",
                message=f"[SUCCESS] Successfully added/updated: {result.node_name} ({result.node_id})"
            )
            print(f"\n[SUCCESS] Successfully added/updated: {result.node_name} ({result.node_id})")
            print(f"   Category: {result.category}")
            print(f"   User Input Required: {result.user_input_required}")
            print(f"   Is Internal: {result.is_internal}")
        else:
            log_util.error(
                service_name="AddSendTemplateNode",
                message="[ERROR] Failed to add send_template node"
            )
            print("\n[ERROR] Failed to add send_template node")
            return False
        
        # Verify the node was added
        verify_node = await flow_db.get_node_detail_by_id("send_template")
        if verify_node:
            print("\n[SUCCESS] Verification: send_template node found in database")
            print(f"   Node ID: {verify_node.node_id}")
            print(f"   Node Name: {verify_node.node_name}")
            print(f"   Category: {verify_node.category}")
        else:
            print("\n[WARNING] Could not verify send_template node in database")
        
        return True
        
    except Exception as e:
        log_util.error(
            service_name="AddSendTemplateNode",
            message=f"Fatal error: {str(e)}"
        )
        print(f"\n[ERROR] Fatal error: {str(e)}")
        raise
    finally:
        # Close database connection
        flow_db.close()
        log_util.info(
            service_name="AddSendTemplateNode",
            message="Database connection closed"
        )


if __name__ == "__main__":
    print("="*60)
    print("Add Send Template Node Script")
    print("="*60)
    print("This script will add the 'send_template' node type")
    print("to the node_details collection.")
    print("="*60)
    print()
    
    try:
        asyncio.run(add_send_template_node())
        print("\n[SUCCESS] Script completed successfully!")
    except KeyboardInterrupt:
        print("\n[WARNING] Script interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Script failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

