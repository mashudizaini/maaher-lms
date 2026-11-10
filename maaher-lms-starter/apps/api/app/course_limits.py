"""Committed per-membership course budgets, before parsing mutation bodies."""
from fastapi import HTTPException

from .auth import principal, verify_origin
from .database import transaction


def admit_course_write(request):
    verify_origin(request)
    # This independent transaction commits even if subsequent body validation,
    # object lookup, version checks or the authoring transaction fails.
    with transaction() as db:
        actor = principal(request, db)
        if actor.role not in {"admin", "teacher"}:
            raise HTTPException(403, "Pengelolaan kursus tersedia bagi admin dan pengajar")
        row = db.execute("""INSERT INTO course_write_limits(tenant_id,user_id,attempts,window_start)
            VALUES(%s,%s,1,now()) ON CONFLICT(tenant_id,user_id) DO UPDATE SET
            attempts=CASE WHEN course_write_limits.window_start<=now()-interval '1 minute' THEN 1
                          ELSE LEAST(course_write_limits.attempts+1,61) END,
            window_start=CASE WHEN course_write_limits.window_start<=now()-interval '1 minute'
                              THEN now() ELSE course_write_limits.window_start END
            WHERE course_write_limits.attempts<61 OR course_write_limits.window_start<=now()-interval '1 minute'
            RETURNING attempts""", (actor.tenant_id, actor.user_id)).fetchone()
        return row is not None and row["attempts"] <= 60
