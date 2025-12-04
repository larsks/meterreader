from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field


class SCMMessage(BaseModel):
    model_config: ConfigDict = ConfigDict(validate_by_name=True, validate_by_alias=True)
    ID: int = Field(alias="EndpointID")
    Type: int = Field(alias="EndpointType")
    Consumption: int


class Event(BaseModel):
    Time: str
    Offset: int
    Message: SCMMessage


class Sample(BaseModel):
    ID: int
    Type: int
    Consumption: int

    @classmethod
    def from_message(cls, msg: Event):
        return cls(
            ID=msg.Message.ID,
            Type=msg.Message.Type,
            Consumption=msg.Message.Consumption,
        )
