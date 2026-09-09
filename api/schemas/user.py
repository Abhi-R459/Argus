from pydantic import BaseModel, ConfigDict

class UserSyncResponse(BaseModel):
    user_id: int
    clerk_user_id: str
    full_name: str
    email: str
    role: str
    is_active: bool
    
    model_config = ConfigDict(from_attributes=True)
