"""Trusted parser worker: text data only, no learner program execution."""
import json
import resource
import signal
import sys
import re

from .markdown_parse import validate_markdown_raw


class CpuBudget(BaseException): pass

def expired(*_): raise CpuBudget()


def main():
    # Worker receives no DB/Auth0/encryption credentials. Memory is bounded on
    # supported POSIX hosts; hard wall timeout is always enforced by the parent.
    memory_active=False
    try:
        resource.setrlimit(resource.RLIMIT_AS,(256*1024*1024,256*1024*1024))
        memory_active=resource.getrlimit(resource.RLIMIT_AS)[0]<=256*1024*1024
    except (ValueError,OSError): pass
    signal.signal(signal.SIGPROF,expired)
    while True:
        line=sys.stdin.buffer.readline(262145)
        if not line:break
        if len(line)>262144:return 1
        result='invalid'
        try:
            value=json.loads(line)['content']
            if not isinstance(value,str) or len(value)>30000 or re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]',value):raise ValueError()
            signal.setitimer(signal.ITIMER_PROF,.25)
            validate_markdown_raw(value); result='ok'
        except CpuBudget: result='complexity'
        except (ValueError,RecursionError,MemoryError): result='invalid'
        finally: signal.setitimer(signal.ITIMER_PROF,0)
        sys.stdout.buffer.write(json.dumps({'result':result,'limits':{'memory_active':memory_active,'memory_bytes':256*1024*1024 if memory_active else None,'cpu_ms':250,'wall_ms':2000}}).encode()+b'\n');sys.stdout.buffer.flush()
    return 0


if __name__=='__main__': raise SystemExit(main())
