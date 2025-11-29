"""
Script to import flow data into MongoDB database.
This script inserts the exact flow data provided into the flows collection.
"""
import asyncio
import sys
import os
from datetime import datetime
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

# Add parent directory to path to import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# MongoDB connection string
MONGO_CONNECTION_STRING = "mongodb://agentflowservice:4g3ntfL0wuS3r@143.244.131.181:27017/?authSource=admin"
DB_NAME = "flow_db"

# Flow data to import
FLOW_DATA = {
    "_id": ObjectId("691ee40841e8102454474848"),
    "name": "WhatsApp Flow",
    "created": datetime(2025, 11, 20, 9, 48, 56, 35000),
    "flowNodes": [
        {
            "id": "trigger_keyword-node-1763631396283-h1ymxv3e3",
            "type": "trigger_keyword",
            "flowNodeType": "Trigger",
            "flowNodePosition": {
                "posX": "-172.05862702802577",
                "posY": "-174.58879253510307"
            },
            "isStartNode": True,
            "triggerKeywords": ["Learn"]
        },
        {
            "id": "button_question-node-1763631411168-xvt6ul76r",
            "type": "button_question",
            "flowNodeType": "Question",
            "flowNodePosition": {
                "posX": "128.1836866802322",
                "posY": "-164.33805984645159"
            },
            "isStartNode": False,
            "interactiveButtonsHeader": {
                "type": "Text",
                "text": "Welcome to the world of Education",
                "media": None
            },
            "interactiveButtonsBody": "This is the start of your journey",
            "interactiveButtonsFooter": "Choose Below",
            "interactiveButtonsUserInputVariable": "",
            "interactiveButtonsDefaultNodeResultId": "",
            "expectedAnswers": [
                {
                    "id": "button_question-node-1763631411168-xvt6ul76r_btn_1763631411175_9d9hjo5o0",
                    "expectedInput": "IIT",
                    "isDefault": True,
                    "nodeResultId": "message-node-1763631492438-a1hb9xkx4"
                },
                {
                    "id": "button_question-node-1763631411168-xvt6ul76r_btn_1763631472139_494zdqa5w",
                    "expectedInput": "CUET",
                    "isDefault": False,
                    "nodeResultId": "message-node-1763631495204-1q4gopcgg"
                },
                {
                    "id": "button_question-node-1763631411168-xvt6ul76r_btn_1763631483191_5q8mk1wub",
                    "expectedInput": "NEET",
                    "isDefault": False,
                    "nodeResultId": "message-node-1763631498886-gbhplpkmc"
                }
            ]
        },
        {
            "id": "message-node-1763631492438-a1hb9xkx4",
            "type": "message",
            "flowNodeType": "Message",
            "flowNodePosition": {
                "posX": "545.602358690219",
                "posY": "-175.84172403570318"
            },
            "isStartNode": False,
            "flowReplies": [
                {
                    "flowReplyType": "Text",
                    "data": "Welcome to IIT",
                    "caption": "",
                    "mimeType": ""
                }
            ]
        },
        {
            "id": "message-node-1763631495204-1q4gopcgg",
            "type": "message",
            "flowNodeType": "Message",
            "flowNodePosition": {
                "posX": "557.1060228794707",
                "posY": "-39.44113436314839"
            },
            "isStartNode": False,
            "flowReplies": [
                {
                    "flowReplyType": "Text",
                    "data": "Welcome To CUET",
                    "caption": "",
                    "mimeType": ""
                }
            ]
        },
        {
            "id": "message-node-1763631498886-gbhplpkmc",
            "type": "message",
            "flowNodeType": "Message",
            "flowNodePosition": {
                "posX": "540.6722168948256",
                "posY": "133.1138284756258"
            },
            "isStartNode": False,
            "flowReplies": [
                {
                    "flowReplyType": "Text",
                    "data": "Welcome to NEET",
                    "caption": "",
                    "mimeType": ""
                }
            ]
        },
        {
            "id": "question-node-1763631557672-ldr6y58cm",
            "type": "question",
            "flowNodeType": "Question",
            "flowNodePosition": {
                "posX": "986.0875064026509",
                "posY": "-127.30094594288883"
            },
            "isStartNode": False,
            "flowReplies": [
                {
                    "flowReplyType": "Text",
                    "data": "Give me a Name",
                    "caption": "",
                    "mimeType": ""
                }
            ],
            "userInputVariable": "@name",
            "answerValidation": {
                "type": "None",
                "minValue": "",
                "maxValue": "",
                "regex": "",
                "fallback": "I'm afraid I didn't understand, could you try again, please?",
                "failsCount": "3"
            },
            "isMediaAccepted": False
        },
        {
            "id": "delay-node-1764137867486-8xdbezftq",
            "type": "delay",
            "flowNodeType": "Delay",
            "flowNodePosition": {
                "posX": "1292.4405433372042",
                "posY": "-93.56382480302693"
            },
            "isStartNode": False,
            "delayDuration": 1,
            "delayUnit": "minutes",
            "waitForReply": False
        },
        {
            "id": "condition-node-1764137879453-ao0gxorij",
            "type": "condition",
            "flowNodeType": "Condition",
            "flowNodePosition": {
                "posX": "969.3761965367235",
                "posY": "114.12039814013937"
            },
            "isStartNode": False,
            "flowNodeConditions": [
                {
                    "id": "condition-node-1764137879453-ao0gxorij_condition",
                    "flowConditionType": "Equal",
                    "variable": "@name",
                    "value": "Abhishek"
                }
            ],
            "conditionResult": {
                "yResultNodeId": "message-node-1764137938657-tabkhmtm3",
                "nResultNodeId": "message-node-1764137890067-713umxmm3"
            },
            "conditionOperator": "None"
        },
        {
            "id": "message-node-1764137890067-713umxmm3",
            "type": "message",
            "flowNodeType": "Message",
            "flowNodePosition": {
                "posX": "1390.0698789087785",
                "posY": "231.27560082602804"
            },
            "isStartNode": False,
            "flowReplies": [
                {
                    "flowReplyType": "Text",
                    "data": "Welcome Random Person",
                    "caption": "",
                    "mimeType": ""
                }
            ]
        },
        {
            "id": "message-node-1764137938657-tabkhmtm3",
            "type": "message",
            "flowNodeType": "Message",
            "flowNodePosition": {
                "posX": "1395.3951153945006",
                "posY": "51.99263914004686"
            },
            "isStartNode": False,
            "flowReplies": [
                {
                    "flowReplyType": "Text",
                    "data": "Welcome Abhishek",
                    "caption": "",
                    "mimeType": ""
                }
            ]
        }
    ],
    "flowEdges": [
        {
            "id": "reactflow__edge-trigger_keyword-node-1763631396283-h1ymxv3e3-button_question-node-1763631411168-xvt6ul76r",
            "sourceNodeId": "trigger_keyword-node-1763631396283-h1ymxv3e3",
            "targetNodeId": "button_question-node-1763631411168-xvt6ul76r"
        },
        {
            "id": "reactflow__edge-button_question-node-1763631411168-xvt6ul76rbutton_question-node-1763631411168-xvt6ul76r_btn_1763631411175_9d9hjo5o0-message-node-1763631492438-a1hb9xkx4",
            "sourceNodeId": "button_question-node-1763631411168-xvt6ul76r_btn_1763631411175_9d9hjo5o0",
            "targetNodeId": "message-node-1763631492438-a1hb9xkx4"
        },
        {
            "id": "reactflow__edge-button_question-node-1763631411168-xvt6ul76rbutton_question-node-1763631411168-xvt6ul76r_btn_1763631472139_494zdqa5w-message-node-1763631495204-1q4gopcgg",
            "sourceNodeId": "button_question-node-1763631411168-xvt6ul76r_btn_1763631472139_494zdqa5w",
            "targetNodeId": "message-node-1763631495204-1q4gopcgg"
        },
        {
            "id": "reactflow__edge-button_question-node-1763631411168-xvt6ul76rbutton_question-node-1763631411168-xvt6ul76r_btn_1763631483191_5q8mk1wub-message-node-1763631498886-gbhplpkmc",
            "sourceNodeId": "button_question-node-1763631411168-xvt6ul76r_btn_1763631483191_5q8mk1wub",
            "targetNodeId": "message-node-1763631498886-gbhplpkmc"
        },
        {
            "id": "reactflow__edge-message-node-1763631492438-a1hb9xkx4-question-node-1763631557672-ldr6y58cm",
            "sourceNodeId": "message-node-1763631492438-a1hb9xkx4",
            "targetNodeId": "question-node-1763631557672-ldr6y58cm"
        },
        {
            "id": "reactflow__edge-message-node-1763631495204-1q4gopcgg-question-node-1763631557672-ldr6y58cm",
            "sourceNodeId": "message-node-1763631495204-1q4gopcgg",
            "targetNodeId": "question-node-1763631557672-ldr6y58cm"
        },
        {
            "id": "reactflow__edge-message-node-1763631498886-gbhplpkmc-question-node-1763631557672-ldr6y58cm",
            "sourceNodeId": "message-node-1763631498886-gbhplpkmc",
            "targetNodeId": "question-node-1763631557672-ldr6y58cm"
        },
        {
            "id": "reactflow__edge-question-node-1763631557672-ldr6y58cm-delay-node-1764137867486-8xdbezftq",
            "sourceNodeId": "question-node-1763631557672-ldr6y58cm",
            "targetNodeId": "delay-node-1764137867486-8xdbezftq"
        },
        {
            "id": "reactflow__edge-delay-node-1764137867486-8xdbezftq-condition-node-1764137879453-ao0gxorij",
            "sourceNodeId": "delay-node-1764137867486-8xdbezftq",
            "targetNodeId": "condition-node-1764137879453-ao0gxorij"
        },
        {
            "id": "reactflow__edge-condition-node-1764137879453-ao0gxorijcondition-node-1764137879453-ao0gxorij__false-message-node-1764137890067-713umxmm3",
            "sourceNodeId": "condition-node-1764137879453-ao0gxorij__false",
            "targetNodeId": "message-node-1764137890067-713umxmm3"
        },
        {
            "id": "reactflow__edge-condition-node-1764137879453-ao0gxorijcondition-node-1764137879453-ao0gxorij__true-message-node-1764137938657-tabkhmtm3",
            "sourceNodeId": "condition-node-1764137879453-ao0gxorij__true",
            "targetNodeId": "message-node-1764137938657-tabkhmtm3"
        }
    ],
    "lastUpdated": datetime(2025, 11, 26, 6, 19, 26, 294000),
    "transform": {
        "posX": "-291.9032002832754",
        "posY": "181.9096700607243",
        "zoom": "0.5633552628213727"
    },
    "isPro": False,
    "brand_id": 1,
    "user_id": 1,
    "created_at": datetime(2025, 11, 20, 9, 48, 56, 35000),
    "updated_at": datetime(2025, 11, 26, 6, 19, 27, 634000)
}


async def import_flow_data():
    """Import flow data into MongoDB"""
    try:
        # Connect to MongoDB
        print(f"Connecting to MongoDB...")
        client = AsyncIOMotorClient(MONGO_CONNECTION_STRING)
        db = client[DB_NAME]
        
        # Test connection
        await client.admin.command('ping')
        print(f"✅ Connected to MongoDB database: {DB_NAME}")
        
        flow_id = str(FLOW_DATA["_id"])
        
        # Check if flow already exists
        existing_flow = await db.flows.find_one({"_id": FLOW_DATA["_id"]})
        if existing_flow:
            print(f"⚠️  Flow with ID {flow_id} already exists. Deleting existing flow...")
            # Delete existing flow and related data
            await db.flows.delete_one({"_id": FLOW_DATA["_id"]})
            await db.flow_nodes.delete_many({"flow_id": flow_id})
            await db.flow_edges.delete_many({"flow_id": flow_id})
            await db.flow_triggers.delete_many({"flow_id": flow_id})
            print(f"✅ Deleted existing flow data")
        
        # Prepare flow document (exclude flowNodes and flowEdges as they're stored separately)
        flow_doc = {
            "_id": FLOW_DATA["_id"],
            "name": FLOW_DATA["name"],
            "created": FLOW_DATA["created"],
            "lastUpdated": FLOW_DATA["lastUpdated"],
            "transform": FLOW_DATA["transform"],
            "isPro": FLOW_DATA["isPro"],
            "brand_id": FLOW_DATA["brand_id"],
            "user_id": FLOW_DATA["user_id"],
            "created_at": FLOW_DATA["created_at"],
            "updated_at": FLOW_DATA["updated_at"]
        }
        
        # Insert flow document
        print(f"Inserting flow document with ID: {flow_id}...")
        await db.flows.insert_one(flow_doc)
        print(f"✅ Flow document inserted successfully")
        
        # Save flow nodes
        print(f"Inserting {len(FLOW_DATA['flowNodes'])} flow nodes...")
        node_docs = []
        for node in FLOW_DATA["flowNodes"]:
            node_doc = node.copy()
            node_doc["flow_id"] = flow_id
            node_docs.append(node_doc)
        
        if node_docs:
            await db.flow_nodes.insert_many(node_docs)
            print(f"✅ Flow nodes inserted successfully")
        
        # Save flow edges
        print(f"Inserting {len(FLOW_DATA['flowEdges'])} flow edges...")
        edge_docs = []
        for edge in FLOW_DATA["flowEdges"]:
            edge_doc = edge.copy()
            edge_doc["flow_id"] = flow_id
            edge_docs.append(edge_doc)
        
        if edge_docs:
            await db.flow_edges.insert_many(edge_docs)
            print(f"✅ Flow edges inserted successfully")
        
        # Save flow triggers (find trigger node)
        print(f"Creating flow triggers...")
        trigger_node = None
        for node in FLOW_DATA["flowNodes"]:
            if node.get("isStartNode") is True and node.get("type") == "trigger_keyword":
                trigger_node = node
                break
        
        if trigger_node:
            trigger_doc = {
                "flow_id": flow_id,
                "node_id": trigger_node["id"],
                "trigger_type": "keyword",
                "trigger_values": trigger_node.get("triggerKeywords", []),
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            await db.flow_triggers.insert_one(trigger_doc)
            print(f"✅ Flow trigger inserted successfully: {trigger_doc['trigger_type']} with values {trigger_doc['trigger_values']}")
        
        print(f"\n✅ Flow data imported successfully!")
        print(f"   Flow ID: {flow_id}")
        print(f"   Flow Name: {FLOW_DATA['name']}")
        print(f"   Nodes: {len(FLOW_DATA['flowNodes'])}")
        print(f"   Edges: {len(FLOW_DATA['flowEdges'])}")
        print(f"   Triggers: {1 if trigger_node else 0}")
        
        # Close connection
        client.close()
        print(f"\n✅ MongoDB connection closed")
        
    except Exception as e:
        print(f"❌ Error importing flow data: {str(e)}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    print("=" * 80)
    print("Flow Data Import Script")
    print("=" * 80)
    print(f"MongoDB Connection: {MONGO_CONNECTION_STRING.split('@')[1] if '@' in MONGO_CONNECTION_STRING else 'N/A'}")
    print(f"Database: {DB_NAME}")
    print("=" * 80)
    print()
    
    asyncio.run(import_flow_data())

