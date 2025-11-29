"""
Script to import node detail data into MongoDB database.
This script inserts node details into the node_details collection.
"""
import asyncio
import sys
import os
from datetime import datetime, UTC
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

# Add parent directory to path to import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# MongoDB connection string
MONGO_CONNECTION_STRING = "mongodb://agentflowservice:4g3ntfL0wuS3r@143.244.131.181:27017/?authSource=admin"
DB_NAME = "flow_db"

# Node details data to import
# is_internal: True for condition and delay nodes, False for all others
NODE_DETAILS_DATA = [
    {
        "_id": ObjectId("6920066c73da52cdcbb78de8"),
        "node_id": "trigger-keyword",
        "node_name": "Keyword Trigger",
        "category": "Trigger",
        "user_input_required": False,
        "is_internal": False,
        "created_at": datetime(2025, 11, 21, 6, 46, 38, 349000),
        "updated_at": datetime(2025, 11, 21, 6, 46, 38, 422000)
    },
    {
        "_id": ObjectId("6920066c73da52cdcbb78de9"),
        "node_id": "trigger-template",
        "node_name": "Template Trigger",
        "category": "Trigger",
        "user_input_required": False,
        "is_internal": False,
        "created_at": datetime(2025, 11, 21, 6, 46, 38, 850000),
        "updated_at": datetime(2025, 11, 21, 6, 46, 38, 850000)
    },
    {
        "_id": ObjectId("6920066c73da52cdcbb78dea"),
        "node_id": "message",
        "node_name": "Send A Message",
        "category": "Action",
        "user_input_required": False,
        "is_internal": False,
        "created_at": datetime(2025, 11, 21, 6, 46, 39, 1000),
        "updated_at": datetime(2025, 11, 21, 6, 46, 39, 1000)
    },
    {
        "_id": ObjectId("6920066c73da52cdcbb78deb"),
        "node_id": "question",
        "node_name": "Text Question",
        "category": "Action",
        "user_input_required": True,
        "is_internal": False,
        "created_at": datetime(2025, 11, 21, 6, 46, 39, 152000),
        "updated_at": datetime(2025, 11, 21, 6, 46, 39, 152000)
    },
    {
        "_id": ObjectId("6920066d73da52cdcbb78dec"),
        "node_id": "button-question",
        "node_name": "Button Question",
        "category": "Action",
        "user_input_required": True,
        "is_internal": False,
        "created_at": datetime(2025, 11, 21, 6, 46, 39, 303000),
        "updated_at": datetime(2025, 11, 21, 6, 46, 39, 303000)
    },
    {
        "_id": ObjectId("6920066d73da52cdcbb78ded"),
        "node_id": "list-question",
        "node_name": "List Question",
        "category": "Action",
        "user_input_required": True,
        "is_internal": False,
        "created_at": datetime(2025, 11, 21, 6, 46, 39, 452000),
        "updated_at": datetime(2025, 11, 21, 6, 46, 39, 452000)
    },
    {
        "_id": ObjectId("6920066d73da52cdcbb78dee"),
        "node_id": "condition",
        "node_name": "Condition",
        "category": "Condition",
        "user_input_required": False,
        "is_internal": True,  # Internal node
        "created_at": datetime(2025, 11, 21, 6, 46, 39, 601000),
        "updated_at": datetime(2025, 11, 21, 6, 46, 39, 601000)
    },
    {
        "_id": ObjectId("6920066d73da52cdcbb78def"),
        "node_id": "delay",
        "node_name": "Delay",
        "category": "Delay",
        "user_input_required": False,
        "is_internal": True,  # Internal node
        "created_at": datetime(2025, 11, 21, 6, 46, 39, 750000),
        "updated_at": datetime(2025, 11, 21, 6, 46, 39, 750000)
    },
    {
        "_id": ObjectId("69200acfe9cfc51efd4df930"),
        "node_id": "conditional_delay",
        "node_name": "Conditional Delay",
        "category": "Delay",
        "user_input_required": True,
        "is_internal": True,  # Internal node (delay category)
        "created_at": datetime(2025, 11, 21, 6, 46, 39, 969000),
        "updated_at": datetime(2025, 11, 21, 6, 46, 39, 923000)
    }
]


async def import_node_details():
    """Import node details into MongoDB"""
    try:
        # Connect to MongoDB
        print(f"Connecting to MongoDB...")
        client = AsyncIOMotorClient(MONGO_CONNECTION_STRING)
        db = client[DB_NAME]
        
        # Test connection
        await client.admin.command('ping')
        print(f"✅ Connected to MongoDB database: {DB_NAME}")
        
        # Update existing node details with is_internal field
        updated_count = 0
        inserted_count = 0
        skipped_count = 0
        
        print(f"\nUpdating/Inserting {len(NODE_DETAILS_DATA)} node details with is_internal field...")
        for node_detail in NODE_DETAILS_DATA:
            node_id = node_detail["node_id"]
            is_internal = node_detail.get("is_internal", False)
            
            # Check if node detail with this _id already exists
            existing = await db.node_details.find_one({"_id": node_detail["_id"]})
            if existing:
                # Update existing node with is_internal field
                await db.node_details.update_one(
                    {"_id": node_detail["_id"]},
                    {"$set": {
                        "is_internal": is_internal,
                        "updated_at": datetime.now(UTC)
                    }}
                )
                print(f"✅ Updated: {node_detail['node_name']} (node_id: {node_id}, is_internal: {is_internal})")
                updated_count += 1
                continue
            
            # Check if node detail with this node_id already exists (different _id)
            existing_by_node_id = await db.node_details.find_one({"node_id": node_id})
            if existing_by_node_id:
                # Update existing node with is_internal field
                await db.node_details.update_one(
                    {"node_id": node_id},
                    {"$set": {
                        "is_internal": is_internal,
                        "updated_at": datetime.now(UTC)
                    }}
                )
                print(f"✅ Updated: {node_detail['node_name']} (node_id: {node_id}, is_internal: {is_internal})")
                updated_count += 1
                continue
            
            # Insert new node detail if it doesn't exist
            await db.node_details.insert_one(node_detail)
            print(f"✅ Inserted: {node_detail['node_name']} (node_id: {node_id}, is_internal: {is_internal})")
            inserted_count += 1
        
        print(f"\n✅ Node details import completed!")
        print(f"   Updated: {updated_count}")
        print(f"   Inserted: {inserted_count}")
        print(f"   Skipped: {skipped_count}")
        print(f"   Total: {len(NODE_DETAILS_DATA)}")
        
        # Show summary by category and internal/external
        print(f"\n📊 Summary by category:")
        categories = {}
        for node_detail in NODE_DETAILS_DATA:
            category = node_detail["category"]
            if category not in categories:
                categories[category] = 0
            categories[category] += 1
        
        for category, count in categories.items():
            print(f"   {category}: {count}")
        
        print(f"\n📊 Summary by internal/external:")
        internal_count = sum(1 for node in NODE_DETAILS_DATA if node.get("is_internal", False))
        external_count = len(NODE_DETAILS_DATA) - internal_count
        print(f"   Internal: {internal_count} (condition, delay)")
        print(f"   External: {external_count} (triggers, actions)")
        
        # Close connection
        client.close()
        print(f"\n✅ MongoDB connection closed")
        
    except Exception as e:
        print(f"❌ Error importing node details: {str(e)}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    print("=" * 80)
    print("Node Details Import Script")
    print("=" * 80)
    print(f"MongoDB Connection: {MONGO_CONNECTION_STRING.split('@')[1] if '@' in MONGO_CONNECTION_STRING else 'N/A'}")
    print(f"Database: {DB_NAME}")
    print("=" * 80)
    print()
    
    asyncio.run(import_node_details())

