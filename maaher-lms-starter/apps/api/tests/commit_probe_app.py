"""Test-only uvicorn target: instrument real psycopg COMMIT at a barrier."""
import os
from pathlib import Path
import time
import psycopg
from app import database
from app.main import app


class ProbeConnection(psycopg.Connection):
    mutated=False

    def execute(self,query,*args,**kwargs):
        result=super().execute(query,*args,**kwargs)
        if any(text in str(query) for text in ('INSERT INTO sessions','DELETE FROM sessions')):
            self.mutated=True
        return result

    def commit(self):
        entered=Path(os.environ['LMS_COMMIT_ENTERED'])
        if self.mutated and not entered.exists():
            entered.write_text('commit entered; no response may be sent yet')
            if os.environ['LMS_COMMIT_MODE']=='fail':
                raise psycopg.errors.SerializationFailure('synthetic COMMIT failure')
            release=Path(os.environ['LMS_COMMIT_RELEASE'])
            deadline=time.monotonic()+15
            while not release.exists():
                if time.monotonic()>deadline:
                    raise RuntimeError('Test commit barrier timed out')
                time.sleep(.01)
        return super().commit()


database._connect=ProbeConnection.connect
