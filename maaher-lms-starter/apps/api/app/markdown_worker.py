"""Trusted parser worker: text data only, no learner program execution."""
import json
import resource
import signal
import sys

from .markdown_parse import validate_markdown_raw


class CpuBudget(BaseException): pass

def expired(*_): raise CpuBudget()


def main():
    # Worker receives no DB/Auth0/encryption credentials. Memory is bounded on
    # supported POSIX hosts; hard wall timeout is always enforced by the parent.
    try: resource.setrlimit(resource.RLIMIT_AS,(256*1024*1024,256*1024*1024))
    except (ValueError,OSError): pass
    signal.signal(signal.SIGPROF,expired)
    for line in sys.stdin.buffer:
        if len(line)>131072: return 1
        result='invalid'
        try:
            value=json.loads(line)['content']
            if not isinstance(value,str) or len(value)>30000: raise ValueError()
            signal.setitimer(signal.ITIMER_PROF,.12)
            validate_markdown_raw(value); result='ok'
        except CpuBudget: result='complexity'
        except (ValueError,RecursionError,MemoryError): result='invalid'
        finally: signal.setitimer(signal.ITIMER_PROF,0)
        sys.stdout.buffer.write(json.dumps({'result':result}).encode()+b'\n');sys.stdout.buffer.flush()
    return 0


if __name__=='__main__': raise SystemExit(main())
