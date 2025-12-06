# pyright: reportUnusedCallResult=false

import argparse
import logging
import threading
from typing import override

from prometheus_client import Counter, start_http_server
from prometheus_client.core import REGISTRY, CounterMetricFamily
from prometheus_client.registry import Collector

from models import Reading
from monitor import Monitor


class ArgsNamespace(argparse.Namespace):
    verbose: int = 0
    rtl_tcp_address: str = ""
    rtlamr_path: str = ""


class MeterReader(Collector, threading.Thread):
    monitor: Monitor
    metric_valid_reading_count: Counter
    metric_invalid_reading_count: Counter
    lock: threading.Lock
    readings: dict[int, Reading]

    def __init__(self, monitor: Monitor | None = None):
        super().__init__(daemon=True)
        self.monitor = monitor or Monitor()
        self.readings = {}
        self.lock = threading.Lock()

    @override
    def run(self):
        self.monitor.start()
        for reading in self.monitor:
            with self.lock:
                self.readings[reading.Message.ID] = reading

        LOG.warning("monitor has stopped")

    @override
    def collect(self):
        metric_consumption = CounterMetricFamily(
            "consumption", "Energy consumed", labels=["meterid", "metertype"]
        )
        with self.lock:
            for reading in self.readings.values():
                metric_consumption.add_metric(
                    [str(reading.Message.ID), str(reading.Message.Type)],
                    reading.Message.Consumption,
                )

        yield metric_consumption


LOG = logging.getLogger(__name__)


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--verbose", "-v", action="count")
    p.add_argument("--rtl-tcp-address", "-a", help="<address:port> for rtl_tcp service")
    p.add_argument("--rtlamr-path", "-p", help="Path to rtlamr binary")
    return p.parse_args(namespace=ArgsNamespace)


def wait_for_first_complete(*threads: threading.Thread):
    while True:
        for t in threads:
            t.join(timeout=0.5)
            if not t.is_alive():
                return


def main():
    args = parse_args()
    loglevel = next(
        (x for i, x in enumerate(["WARNING", "INFO", "DEBUG"]) if i == args.verbose),
        "DEBUG",
    )
    logging.basicConfig(level=loglevel)

    monitor = Monitor(
        rtl_tcp_address=args.rtl_tcp_address, rtlamr_path=args.rtlamr_path
    )
    reader = MeterReader(monitor=monitor)
    reader.start()
    REGISTRY.register(reader)

    LOG.info("starting metrics server")
    server, server_thread = start_http_server(9000)

    try:
        wait_for_first_complete(reader, server_thread)
    finally:
        if server_thread.is_alive():
            LOG.warning("shutting down http service")
            server.shutdown()
            server_thread.join()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
