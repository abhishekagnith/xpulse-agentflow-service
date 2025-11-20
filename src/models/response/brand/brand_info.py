from pydantic import BaseModel
from typing import Optional, List

class UserSegment(BaseModel):
    name: Optional[str] = None  
    age_range: Optional[str] = None
    location: Optional[str] = None
    values: Optional[List[str]] = None

class VisualIdentity(BaseModel):
    logo: Optional[str] = None
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None
    typography: Optional[List[str]] = None

class ToneOfVoice(BaseModel):
    primary: Optional[List[str]] = None
    secondary: Optional[List[str]] = None

class BrandIdentity(BaseModel):
    core_values: Optional[List[str]] = None
    mission: Optional[str] = None
    vision: Optional[str] = None
    tone_of_voice: Optional[ToneOfVoice] = None
    visual_identity: Optional[VisualIdentity] = None
    content_pillars: Optional[List[str]] = None
    emotional_adjectives: Optional[List[str]] = None
    user_segments: Optional[List[UserSegment]] = None

class BrandInfo(BaseModel):
    id: Optional[int] = None
    url: Optional[str] = None
    brand_identity: Optional[BrandIdentity] = None