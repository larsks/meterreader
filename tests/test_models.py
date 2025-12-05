from datetime import datetime

import pytest

import models


@pytest.mark.parametrize(
    "message,valid,expected",
    [
        pytest.param(
            '{"Time":"2025-12-05T16:44:45.730309536Z","Offset":0,"Length":40960,"Type":"SCM","Message":{"ID":44826100,"Type":12,"TamperPhy":1,"TamperEnc":0,"Consumption":548140,"ChecksumVal":47768}}',
            True,
            models.Reading(
                Time=datetime.fromisoformat("2025-12-05T16:44:45.730309536Z"),
                Offset=0,
                Type=models.MessageType.SCM,
                Message=models.SCMMessage(
                    EndpointID=44826100, EndpointType=12, Consumption=548140
                ),
            ),
            id="valid scm message",
        ),
        pytest.param(
            '{"Time":"2025-12-05T16:45:31.269518166Z","Offset":0,"Length":229376,"Type":"SCM+","Message":{"FrameSync":5795,"ProtocolID":30,"EndpointType":156,"EndpointID":78043469,"Consumption":406934,"Tamper":1280,"PacketCRC":44066}}',
            True,
            models.Reading(
                Time=datetime.fromisoformat("2025-12-05T16:45:31.269518166Z"),
                Offset=0,
                Type=models.MessageType.SCMPLUS,
                Message=models.SCMMessage(
                    EndpointID=78043469, EndpointType=156, Consumption=406934
                ),
            ),
            id="valid scm+ message",
        ),
    ],
)
def test_parse_messages(message: str, valid: bool, expected: models.Reading):
    result = models.Reading.model_validate_json(message)
    if valid:
        assert result == expected
