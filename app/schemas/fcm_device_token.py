
from pydantic import BaseModel, Field


class FCMDeviceTokenRequest(BaseModel):
    token: str = Field(min_length=20, max_length=4096)
