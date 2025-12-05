from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
    Time: datetime
    Offset: int
    Type: MessageType = MessageType.UNKNOWN
    Message: SCMMessage

    @classmethod
    @field_validator("Time", mode="before")
    def parse_time(cls, v: str | datetime):
        if isinstance(v, str):
            v = datetime.fromisoformat(v)

        return v
