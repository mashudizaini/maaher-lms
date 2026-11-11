"""Independent committed admission: 120 learning requests/minute per member."""
from fastapi import HTTPException
from .auth import principal,verify_origin
from .database import transaction


def admit_learning(request):
    if request.method=='POST':verify_origin(request)
    with transaction() as db:
        actor=principal(request,db)
        if actor.role!='student':raise HTTPException(403,'Halaman ini tersedia untuk akun siswa')
        row=db.execute("""INSERT INTO learning_request_limits(tenant_id,user_id,attempts,window_start)
          VALUES(%s,%s,1,now()) ON CONFLICT(tenant_id,user_id) DO UPDATE SET
          attempts=CASE WHEN learning_request_limits.window_start<=now()-interval '1 minute' THEN 1 ELSE LEAST(learning_request_limits.attempts+1,121) END,
          window_start=CASE WHEN learning_request_limits.window_start<=now()-interval '1 minute' THEN now() ELSE learning_request_limits.window_start END
          WHERE learning_request_limits.attempts<121 OR learning_request_limits.window_start<=now()-interval '1 minute'
          RETURNING attempts""",(actor.tenant_id,actor.user_id)).fetchone()
        return row is not None and row['attempts']<=120
