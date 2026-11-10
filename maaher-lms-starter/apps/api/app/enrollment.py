"""Tenant-scoped cohort and enrollment lifecycle; all writes are admin-only."""
from uuid import UUID,uuid4

from fastapi import APIRouter,Depends,HTTPException,Query
from psycopg.errors import UniqueViolation,CheckViolation,ForeignKeyViolation

from .auth import connection,principal,verify_origin
from .courses import Title,Version,Input,admin,audit

router=APIRouter()


class NewCohort(Title): course_id:UUID
class EditCohort(Title,Version): pass
class NewEnrollment(Input):
    course_id:UUID
    cohort_id:UUID
    student_id:UUID
class MoveEnrollment(Version): cohort_id:UUID


def course_lock(db,actor,cid):
    row=db.execute('SELECT id,state FROM courses WHERE tenant_id=%s AND id=%s FOR UPDATE',(actor.tenant_id,cid)).fetchone()
    if not row: raise HTTPException(404,'Kursus tidak ditemukan')
    if row['state']=='archived': raise HTTPException(409,'Pulihkan kursus sebelum mengelola cohort dan enrollment')


def cohort_lock(db,actor,cid,hid,active=True):
    row=db.execute('SELECT id,title,state,version FROM cohorts WHERE tenant_id=%s AND course_id=%s AND id=%s FOR UPDATE',(actor.tenant_id,cid,hid)).fetchone()
    if not row: raise HTTPException(404,'Cohort tidak ditemukan pada kursus ini')
    if active and row['state']!='active': raise HTTPException(409,'Pulihkan cohort sebelum menggunakannya')
    return row


def student_lock(db,actor,uid):
    if not db.execute('SELECT enrollment_lock_student(%s,%s) AS ok',(actor.tenant_id,uid)).fetchone()['ok']:
        raise HTTPException(409,'Pilih anggota siswa aktif dari organisasi ini')


def version_check(row,version):
    if row['version']!=version: raise HTTPException(409,'Data telah berubah. Muat ulang sebelum menyimpan')


def page(rows,limit,key):
    return {key:rows[:limit],'next_cursor':str(rows[limit-1]['id']) if len(rows)>limit else None}


@router.get('/cohorts')
def cohorts(course_id:UUID,archived:bool=False,after:UUID|None=None,limit:int=Query(30,ge=1,le=50),
            actor=Depends(principal),db=Depends(connection,scope='function')):
    rows=db.execute("""SELECT id,course_id,title,state,version,created_at,updated_at FROM cohorts
      WHERE tenant_id=%s AND course_id=%s AND (state='archived')=%s AND (id>%s::uuid OR %s::uuid IS NULL)
      ORDER BY id LIMIT %s""",(actor.tenant_id,course_id,archived,after,after,limit+1)).fetchall()
    return page(rows,limit,'cohorts')


@router.post('/cohorts',dependencies=[Depends(verify_origin)],status_code=201)
def create_cohort(body:NewCohort,actor=Depends(principal),db=Depends(connection,scope='function')):
    admin(actor); course_lock(db,actor,body.course_id)
    if db.execute('SELECT count(*) AS n FROM cohorts WHERE tenant_id=%s AND course_id=%s',(actor.tenant_id,body.course_id)).fetchone()['n']>=100:
        raise HTTPException(409,'Batas 100 cohort per kursus telah tercapai')
    hid=uuid4()
    row=db.execute('INSERT INTO cohorts(id,tenant_id,course_id,title) VALUES(%s,%s,%s,%s) RETURNING id,version,state',
                   (hid,actor.tenant_id,body.course_id,body.title)).fetchone()
    audit(db,actor,'cohort.created',hid,'cohort'); return row


@router.post('/cohorts/{hid}',dependencies=[Depends(verify_origin)])
def edit_cohort(hid:UUID,body:EditCohort,actor=Depends(principal),db=Depends(connection,scope='function')):
    admin(actor); row=db.execute('SELECT course_id FROM cohorts WHERE tenant_id=%s AND id=%s',(actor.tenant_id,hid)).fetchone()
    if not row: raise HTTPException(404,'Cohort tidak ditemukan')
    course_lock(db,actor,row['course_id']); current=cohort_lock(db,actor,row['course_id'],hid); version_check(current,body.version)
    result=db.execute('UPDATE cohorts SET title=%s,version=version+1,updated_at=now() WHERE tenant_id=%s AND id=%s RETURNING id,version,state',
                      (body.title,actor.tenant_id,hid)).fetchone()
    audit(db,actor,'cohort.updated',hid,'cohort'); return result


def change_cohort_state(hid,body,actor,db,state):
    admin(actor); row=db.execute('SELECT course_id FROM cohorts WHERE tenant_id=%s AND id=%s',(actor.tenant_id,hid)).fetchone()
    if not row: raise HTTPException(404,'Cohort tidak ditemukan')
    course_lock(db,actor,row['course_id']); current=cohort_lock(db,actor,row['course_id'],hid,False); version_check(current,body.version)
    if current['state']==state: raise HTTPException(409,'Status cohort sudah sesuai. Muat ulang data')
    result=db.execute('UPDATE cohorts SET state=%s,version=version+1,updated_at=now() WHERE tenant_id=%s AND id=%s RETURNING id,version,state',
                      (state,actor.tenant_id,hid)).fetchone()
    audit(db,actor,'cohort.archived' if state=='archived' else 'cohort.restored',hid,'cohort'); return result


@router.post('/cohorts/{hid}/archive',dependencies=[Depends(verify_origin)])
def archive_cohort(hid:UUID,body:Version,actor=Depends(principal),db=Depends(connection,scope='function')):
    return change_cohort_state(hid,body,actor,db,'archived')


@router.post('/cohorts/{hid}/restore',dependencies=[Depends(verify_origin)])
def restore_cohort(hid:UUID,body:Version,actor=Depends(principal),db=Depends(connection,scope='function')):
    return change_cohort_state(hid,body,actor,db,'active')


@router.get('/enrollments')
def enrollments(course_id:UUID,cohort_id:UUID|None=None,status:str=Query('active',pattern='^(active|revoked)$'),
                after:UUID|None=None,limit:int=Query(30,ge=1,le=50),actor=Depends(principal),db=Depends(connection,scope='function')):
    rows=db.execute("""SELECT id,course_id,cohort_id,student_id,status,version,created_at,updated_at FROM enrollments
      WHERE tenant_id=%s AND course_id=%s AND status=%s AND (cohort_id=%s::uuid OR %s::uuid IS NULL)
      AND (id>%s::uuid OR %s::uuid IS NULL) ORDER BY id LIMIT %s""",
      (actor.tenant_id,course_id,status,cohort_id,cohort_id,after,after,limit+1)).fetchall()
    return page(rows,limit,'enrollments')


@router.post('/enrollments',dependencies=[Depends(verify_origin)],status_code=201)
def enroll(body:NewEnrollment,actor=Depends(principal),db=Depends(connection,scope='function')):
    admin(actor); course_lock(db,actor,body.course_id); cohort_lock(db,actor,body.course_id,body.cohort_id); student_lock(db,actor,body.student_id)
    if db.execute('SELECT count(*) AS n FROM enrollments WHERE tenant_id=%s AND course_id=%s',(actor.tenant_id,body.course_id)).fetchone()['n']>=5000:
        raise HTTPException(409,'Batas 5000 enrollment per kursus telah tercapai')
    eid=uuid4()
    try:
        row=db.execute('INSERT INTO enrollments(id,tenant_id,course_id,cohort_id,student_id) VALUES(%s,%s,%s,%s,%s) RETURNING id,version,status',
          (eid,actor.tenant_id,body.course_id,body.cohort_id,body.student_id)).fetchone()
    except UniqueViolation:
        raise HTTPException(409,'Siswa sudah memiliki enrollment pada kursus ini. Muat ulang; gunakan aktivasi ulang bila dicabut') from None
    except (CheckViolation,ForeignKeyViolation):
        raise HTTPException(409,'Keanggotaan atau cohort telah berubah. Muat ulang') from None
    audit(db,actor,'enrollment.created',eid,'enrollment'); return row


def enrollment_target(db,actor,eid):
    admin(actor)
    row=db.execute('SELECT course_id,student_id FROM enrollments WHERE tenant_id=%s AND id=%s',(actor.tenant_id,eid)).fetchone()
    if not row: raise HTTPException(404,'Enrollment tidak ditemukan')
    return row


def enrollment_lock(db,actor,eid,version):
    row=db.execute('SELECT id,cohort_id,version,status FROM enrollments WHERE tenant_id=%s AND id=%s FOR UPDATE',(actor.tenant_id,eid)).fetchone()
    if not row: raise HTTPException(404,'Enrollment tidak ditemukan')
    version_check(row,version); return row


@router.post('/enrollments/{eid}/move',dependencies=[Depends(verify_origin)])
def move(eid:UUID,body:MoveEnrollment,actor=Depends(principal),db=Depends(connection,scope='function')):
    target=enrollment_target(db,actor,eid); course_lock(db,actor,target['course_id']); cohort_lock(db,actor,target['course_id'],body.cohort_id)
    student_lock(db,actor,target['student_id']); row=enrollment_lock(db,actor,eid,body.version)
    if row['status']!='active': raise HTTPException(409,'Aktifkan ulang enrollment terlebih dahulu')
    result=db.execute('UPDATE enrollments SET cohort_id=%s,version=version+1,updated_at=now() WHERE tenant_id=%s AND id=%s RETURNING id,version,status',
                     (body.cohort_id,actor.tenant_id,eid)).fetchone()
    audit(db,actor,'enrollment.moved',eid,'enrollment'); return result


@router.post('/enrollments/{eid}/revoke',dependencies=[Depends(verify_origin)])
def revoke(eid:UUID,body:Version,actor=Depends(principal),db=Depends(connection,scope='function')):
    target=enrollment_target(db,actor,eid)
    # Revocation is allowed even when the course/cohort is archived or membership
    # is inactive. It never acquires a membership lock after an enrollment lock.
    row=enrollment_lock(db,actor,eid,body.version)
    if row['status']!='active': raise HTTPException(409,'Enrollment sudah dicabut')
    result=db.execute("UPDATE enrollments SET status='revoked',version=version+1,updated_at=now() WHERE tenant_id=%s AND id=%s RETURNING id,version,status",(actor.tenant_id,eid)).fetchone()
    audit(db,actor,'enrollment.revoked',eid,'enrollment'); return result


@router.post('/enrollments/{eid}/reactivate',dependencies=[Depends(verify_origin)])
def reactivate(eid:UUID,body:MoveEnrollment,actor=Depends(principal),db=Depends(connection,scope='function')):
    target=enrollment_target(db,actor,eid); course_lock(db,actor,target['course_id']); cohort_lock(db,actor,target['course_id'],body.cohort_id)
    student_lock(db,actor,target['student_id']); row=enrollment_lock(db,actor,eid,body.version)
    if row['status']!='revoked': raise HTTPException(409,'Enrollment masih aktif')
    result=db.execute("UPDATE enrollments SET cohort_id=%s,status='active',version=version+1,updated_at=now() WHERE tenant_id=%s AND id=%s RETURNING id,version,status",(body.cohort_id,actor.tenant_id,eid)).fetchone()
    audit(db,actor,'enrollment.reactivated',eid,'enrollment'); return result
