"""Read-only student access, backed by live enrollment/membership/course RLS."""
from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException,Query
from .auth import principal,connection
from .enrollment import page
from .courses import course_detail,lesson_detail

router=APIRouter(prefix='/learning/courses')


def student(actor=Depends(principal)):
    if actor.role!='student': raise HTTPException(403,'Halaman ini tersedia untuk akun siswa')
    return actor


@router.get('')
def catalog(after:UUID|None=None,limit:int=Query(30,ge=1,le=50),actor=Depends(student),db=Depends(connection,scope='function')):
    rows=db.execute("""SELECT id,title,description,state,version,updated_at FROM courses WHERE tenant_id=%s AND state='published'
        AND (id>%s::uuid OR %s::uuid IS NULL) ORDER BY id LIMIT %s""",(actor.tenant_id,after,after,limit+1)).fetchall()
    return page(rows,limit,'courses')


@router.get('/{cid}')
def outline(cid:UUID,actor=Depends(student),db=Depends(connection,scope='function')):
    # Shared explicit projections. RLS grants students only a published course
    # with their active enrollment/cohort; no management dependency is bypassed
    # on any authoring route. Assignment table itself remains staff-only.
    result=course_detail(cid,actor,db)
    result.pop('teachers',None)
    return result


@router.get('/{cid}/modules/{mid}/lessons/{lid}')
def lesson(cid:UUID,mid:UUID,lid:UUID,actor=Depends(student),db=Depends(connection,scope='function')):
    return lesson_detail(cid,mid,lid,actor,db)
