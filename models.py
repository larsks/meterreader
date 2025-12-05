from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

from enum import StrEnum


# This handles both SCM and SCM+ messages through the magic
# of pydantic aliases.
class SCMMessage(BaseModel):
    model_config: ConfigDict = ConfigDict(validate_by_name=True, validate_by_alias=True)
    ID: int = Field(alias="EndpointID")
    Type: int = Field(alias="EndpointType")
    Consumption: int


class MessageType(StrEnum):
    UNKNOWN = "<unknown>"
    SCM = "SCM"
    SCMPLUS = "SCM+"


class Reading(BaseModel):
    Time: str
    Offset: int
    Type: MessageType = MessageType.UNKNOWN
    Message: SCMMessage
