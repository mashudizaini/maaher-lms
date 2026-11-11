"""Test-only actual CPU workload for the worker timer; never in runtime image."""
import time
from app import markdown_worker as worker
original=worker.validate_markdown_raw


def cpu_probe(value):
    if value=='test-only-cpu-budget':
        end=time.process_time()+5
        while time.process_time()<end:pass
    return original(value)


worker.validate_markdown_raw=cpu_probe
if __name__=='__main__':raise SystemExit(worker.main())
