import json
import threading
import subprocess
from typing import cast
from typing import override
from typing import TypedDict
from prometheus_client.core import REGISTRY
from prometheus_client import start_http_server
from prometheus_client.registry import Collector
from prometheus_client.core import CounterMetricFamily
from prometheus_client import Counter
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict


class Settings(BaseSettings):
    model_config: SettingsConfigDict = SettingsConfigDict(env_prefix="METERREADER_")
    rtl_sdr_address: str = "127.0.0.1:1234"


class SCMMessage(TypedDict):
    ID: int
    Type: int
    Consumption: int


class SCMPlusMessage(TypedDict):
    EndpointID: int
    EndpointType: int
    Consumption: int


class Event(TypedDict):
    Time: str
    Offset: int
    Message: SCMMessage | SCMPlusMessage


class MeterReader(Collector):
    metrics: dict[str, dict[str, int]]
    lock: threading.Lock
    reader_thread: threading.Thread
    consumption: CounterMetricFamily

    def __init__(self):
        self.metrics = {
            "consumption": {},
            "metertypes": {},
        }
        self.lock = threading.Lock()
        self.consumption = CounterMetricFamily(
            "consumption", "Energy consumed", labels=["meterid", "metertype"]
        )
        self.reader_thread = threading.Thread(target=self.reader)
        self.reader_thread.start()

    def reader(self):
        p = subprocess.Popen(
            [
                "rtlamr",
                "-msgtype=scm,scm+,idm,netidm",
                "-format=json",
                f"-server={SETTINGS.rtl_sdr_address}",
            ],
            stdout=subprocess.PIPE,
        )

        line: bytes
        data: Event

        if p.stdout is None:
            return

        for line in p.stdout:
            data = cast(Event, json.loads(line))
            msg: SCMMessage | SCMPlusMessage
            meterid: int
            consumption: int
            MESSAGES.inc()
            if msg := data.get("Message"):
                if meterid := msg.get("ID", msg.get("EndpointID")):
                    metertype = msg.get("Type", msg.get("EndpointType"))
                    if consumption := msg.get("Consumption"):
                        with self.lock:
                            self.metrics["consumption"][str(meterid)] = consumption
                            if metertype is not None:
                                self.metrics["metertypes"][str(meterid)] = metertype

    @override
    def collect(self):
        with self.lock:
            for meterid, value in self.metrics["consumption"].items():
                labels = [str(meterid)]
                if (metertype := self.metrics["metertypes"].get(meterid)) is not None:
                    labels.append(str(metertype))

                self.consumption.add_metric(labels, value)

        yield self.consumption


MESSAGES = Counter("rtlamr_messages", "Messages received from rtlamr")
SETTINGS = Settings()
REGISTRY.register(MeterReader())


def main():
    _, t = start_http_server(9000)
    t.join()


if __name__ == "__main__":
    main()
