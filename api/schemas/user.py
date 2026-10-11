from pydantic import BaseModel, ConfigDict, Field

class UserSyncResponse(BaseModel):
    user_id: int
    auth_user_id: str = Field(validation_alias="clerk_user_id")
    full_name: str
    email: str
    role: str
    is_active: bool
    
    model_config = ConfigDict(from_attributes=True)
