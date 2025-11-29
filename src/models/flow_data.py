from pydantic import BaseModel, Field, Discriminator, ConfigDict
from typing import Optional, List, Dict, Any, Union, Literal, Annotated
from datetime import datetime

class FlowNodePosition(BaseModel):
    posX: str
    posY: str

class FlowReply(BaseModel):
    flowReplyType: str
    data: str
    caption: Optional[str] = ""
    mimeType: Optional[str] = ""

class AnswerValidation(BaseModel):
    model_config = ConfigDict(extra='allow')  # Allow extra fields
    
    type: Optional[str] = None
    minValue: Optional[str] = ""
    maxValue: Optional[str] = ""
    regex: Optional[str] = ""
    fallback: Optional[str] = ""
    failsCount: Optional[str] = ""

class ExpectedAnswer(BaseModel):
    id: str
    expectedInput: str
    isDefault: bool
    nodeResultId: Optional[str] = None

class InteractiveButtonsHeader(BaseModel):
    type: str
    text: Optional[str] = None
    media: Optional[str] = None

class FlowNodeCondition(BaseModel):
    id: str
    flowConditionType: str
    variable: str
    value: str

class ConditionResultItem(BaseModel):
    id: str
    expectedInput: str
    isDefault: bool
    nodeResultId: str

# Base FlowNode with common fields
class BaseFlowNode(BaseModel):
    model_config = ConfigDict(extra='allow')  # Allow extra fields like 'channel', 'terminal', etc.
    
    id: str
    type: str
    flowNodeType: str
    flowNodePosition: FlowNodePosition
    isStartNode: bool

# Trigger Template Node
class TriggerTemplateNode(BaseFlowNode):
    type: Literal["trigger_template"]
    triggerTemplateId: str = ""
    triggerTemplateName: Optional[str] = None
    expectedAnswers: Optional[List[ExpectedAnswer]] = None

# Trigger Keyword Node
class TriggerKeywordNode(BaseFlowNode):
    type: Literal["trigger_keyword"]
    triggerKeywords: List[str] = []

# Message Node
class MessageNode(BaseFlowNode):
    type: Literal["message"]
    flowReplies: List[FlowReply]

# Question Node
class QuestionNode(BaseFlowNode):
    type: Literal["question"]
    flowReplies: Optional[List[FlowReply]] = []
    userInputVariable: str = ""
    answerValidation: Optional[AnswerValidation] = None
    isMediaAccepted: bool = False

# Button Question Node
class ButtonQuestionNode(BaseFlowNode):
    type: Literal["button_question"]
    interactiveButtonsHeader: InteractiveButtonsHeader
    interactiveButtonsBody: str
    interactiveButtonsFooter: Optional[str] = ""
    interactiveButtonsUserInputVariable: str = ""
    interactiveButtonsDefaultNodeResultId: Optional[str] = ""
    expectedAnswers: Optional[List[ExpectedAnswer]] = None

# List Question Node
class ListQuestionNode(BaseFlowNode):
    type: Literal["list_question"]
    flowReplies: Optional[List[FlowReply]] = []
    userInputVariable: str = ""
    answerValidation: Optional[AnswerValidation] = None
    isMediaAccepted: bool = False

# Condition Node
class ConditionNode(BaseFlowNode):
    type: Literal["condition"]
    flowNodeConditions: List[FlowNodeCondition]
    conditionResult: List[ConditionResultItem]  # Array format from frontend
    conditionOperator: str

# Delay Node
class DelayResultItem(BaseModel):
    id: str
    expectedInput: str
    isDefault: bool
    nodeResultId: str

class DelayNode(BaseFlowNode):
    type: Literal["delay"]
    delayDuration: int  # Duration in seconds
    delayUnit: str  # "seconds", "minutes", "hours", "days"
    waitForReply: Optional[bool] = False  # If true, wait for reply; if false, proceed after delay
    delayInterrupt: Optional[bool] = False  # If true, delay can be interrupted by user reply
    delayResult: Optional[List[DelayResultItem]] = None  # Array format from frontend

# Union of all node types with discriminator
FlowNode = Annotated[
    Union[
        TriggerTemplateNode,
        TriggerKeywordNode,
        MessageNode,
        QuestionNode,
        ButtonQuestionNode,
        ListQuestionNode,
        ConditionNode,
        DelayNode
    ],
    Discriminator("type")
]

class FlowEdge(BaseModel):
    id: str
    sourceNodeId: str
    targetNodeId: str

class Transform(BaseModel):
    posX: str
    posY: str
    zoom: str

class FlowData(BaseModel):
    id: Optional[str] = None
    name: str
    created: Optional[datetime] = Field(default_factory=datetime.utcnow)
    flowNodes: List[FlowNode]
    flowEdges: List[FlowEdge]
    lastUpdated: Optional[str] = None
    transform: Optional[Transform] = None
    isPro: Optional[bool] = False
    status: Optional[str] = Field(default="draft", description="Flow status: draft, published, etc.")
    brand_id: Optional[int] = None
    user_id: Optional[int] = None
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default_factory=datetime.utcnow)

