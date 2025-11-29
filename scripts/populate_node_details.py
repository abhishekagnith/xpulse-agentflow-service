"""
Script to populate node_details collection with all existing node types.

This script adds all the node types that are currently supported in the flow service:
- Trigger nodes (trigger_keyword, trigger_template)
- Action nodes (message, question, button_question, list_question)
- Condition nodes (condition)
- Delay nodes (delay)

Note: Node IDs use underscores to match flow node types (e.g., "button_question" not "button-question")

Run this script once to initialize the node_details collection.
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

# Define all node types with their details
NODE_DETAILS = [
    {
        "node_id": "trigger_keyword",
        "node_name": "Keyword Trigger",
        "category": "Trigger",
        "user_input_required": False
    },
    {
        "node_id": "trigger_template",
        "node_name": "Template Trigger",
        "category": "Trigger",
        "user_input_required": False
    },
    {
        "node_id": "message",
        "node_name": "Send A Message",
        "category": "Action",
        "user_input_required": False
    },
    {
        "node_id": "question",
        "node_name": "Text Question",
        "category": "Action",
        "user_input_required": True
    },
    {
        "node_id": "button_question",
        "node_name": "Button Question",
        "category": "Action",
        "user_input_required": True
    },
    {
        "node_id": "list_question",
        "node_name": "List Question",
        "category": "Action",
        "user_input_required": True
    },
    {
        "node_id": "condition",
        "node_name": "Condition",
        "category": "Condition",
        "user_input_required": False
    },
    {
        "node_id": "delay",
        "node_name": "Delay",
        "category": "Delay",
        "user_input_required": False
    }
]


async def populate_node_details():
    """
    Populate the node_details collection with all existing node types.
    """
    # Initialize utilities
    log_util = LogUtil()
    environment_utils = EnvironmentUtils(log_util=log_util)
    
    # Initialize database
    flow_db = FlowDB(log_util=log_util, environment_utils=environment_utils)
    
    try:
        log_util.info(
            service_name="PopulateNodeDetails",
            message="Starting node details population..."
        )
        
        success_count = 0
        error_count = 0
        
        for node_data in NODE_DETAILS:
            try:
                # Create NodeDetailData object
                node_detail = NodeDetailData(
                    node_id=node_data["node_id"],
                    node_name=node_data["node_name"],
                    category=node_data["category"],
                    user_input_required=node_data["user_input_required"]
                )
                
                # Upsert (insert or update if exists)
                result = await flow_db.upsert_node_detail(node_detail)
                
                if result:
                    success_count += 1
                    log_util.info(
                        service_name="PopulateNodeDetails",
                        message=f"[SUCCESS] Successfully added/updated: {node_data['node_name']} ({node_data['node_id']})"
                    )
                else:
                    error_count += 1
                    log_util.error(
                        service_name="PopulateNodeDetails",
                        message=f"[ERROR] Failed to add: {node_data['node_name']} ({node_data['node_id']})"
                    )
                    
            except Exception as e:
                error_count += 1
                log_util.error(
                    service_name="PopulateNodeDetails",
                    message=f"[ERROR] Error processing {node_data['node_name']}: {str(e)}"
                )
        
        # Summary
        log_util.info(
            service_name="PopulateNodeDetails",
            message=f"Population complete! Success: {success_count}, Errors: {error_count}"
        )
        
        # Display all node details
        all_nodes = await flow_db.get_all_node_details()
        log_util.info(
            service_name="PopulateNodeDetails",
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
            service_name="PopulateNodeDetails",
            message=f"Fatal error: {str(e)}"
        )
        print(f"❌ Fatal error: {str(e)}")
        raise
    finally:
        # Close database connection
        flow_db.close()
        log_util.info(
            service_name="PopulateNodeDetails",
            message="Database connection closed"
        )


if __name__ == "__main__":
    print("="*60)
    print("Node Details Population Script")
    print("="*60)
    print("This script will populate the node_details collection")
    print("with all existing node types.")
    print("="*60)
    print()
    
    try:
        asyncio.run(populate_node_details())
        print("\n[SUCCESS] Script completed successfully!")
    except KeyboardInterrupt:
        print("\n[WARNING] Script interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Script failed with error: {str(e)}")
        sys.exit(1)


