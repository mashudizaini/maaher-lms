"""Committed staff grading read budget; writes retain course60/min admission."""
from fastapi import HTTPException
from .auth import principal
from .database import transaction


def admit_grading_read(request):
    with transaction() as db:
        actor=principal(request,db)
        if actor.role not in {'admin','teacher'}:raise HTTPException(403,'Penilaian tersedia untuk admin dan pengajar')
        row=db.execute("""INSERT INTO grading_read_limits(tenant_id,user_id,attempts,window_start) VALUES(%s,%s,1,now())
          ON CONFLICT(tenant_id,user_id) DO UPDATE SET
          attempts=CASE WHEN grading_read_limits.window_start<=now()-interval '1 minute' THEN 1 ELSE LEAST(grading_read_limits.attempts+1,181) END,
          window_start=CASE WHEN grading_read_limits.window_start<=now()-interval '1 minute' THEN now() ELSE grading_read_limits.window_start END
          WHERE grading_read_limits.attempts<181 OR grading_read_limits.window_start<=now()-interval '1 minute' RETURNING attempts""",(actor.tenant_id,actor.user_id)).fetchone()
        return row is not None and row['attempts']<=180
