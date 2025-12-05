from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field


class SCMMessage(BaseModel):
    model_config: ConfigDict = ConfigDict(validate_by_name=True, validate_by_alias=True)
    ID: int = Field(alias="EndpointID")
    Type: int = Field(alias="EndpointType")
    Consumption: int


class Reading(BaseModel):
    Time: str
    Offset: int
    Message: SCMMessage
