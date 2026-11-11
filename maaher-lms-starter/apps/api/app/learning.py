"""Published lessons, revision-aware own completion and ordered next steps."""
from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException,Query
from pydantic import Field
from .auth import principal,connection,verify_origin
from .enrollment import page
from .courses import Input,audit

router=APIRouter(prefix='/learning/courses')


class Completion(Input): revision:int=Field(ge=1)


def student(actor=Depends(principal)):
    if actor.role!='student':raise HTTPException(403,'Halaman ini tersedia untuk akun siswa')
    return actor


def enrollment(db,actor,cid):
    row=db.execute("SELECT id FROM enrollments WHERE tenant_id=%s AND course_id=%s AND student_id=%s AND status='active'",
                   (actor.tenant_id,cid,actor.user_id)).fetchone()
    if not row:raise HTTPException(404,'Kursus tidak tersedia untuk enrollment Anda')
    return row['id']


def summaries(db,actor,cid,eid):
    return db.execute("""SELECT l.id,l.module_id,l.title,l.position,l.revision,
      (p.lesson_revision=l.revision) IS TRUE AS completed,
      (p.lesson_id IS NOT NULL AND p.lesson_revision<>l.revision) AS needs_review
      FROM course_lessons l JOIN course_modules m ON m.tenant_id=l.tenant_id AND m.course_id=l.course_id AND m.id=l.module_id
      LEFT JOIN lesson_progress p ON p.tenant_id=l.tenant_id AND p.course_id=l.course_id AND p.lesson_id=l.id AND p.enrollment_id=%s
      WHERE l.tenant_id=%s AND l.course_id=%s ORDER BY m.position,m.id,l.position,l.id""",(eid,actor.tenant_id,cid)).fetchall()


@router.get('')
def catalog(after:UUID|None=None,limit:int=Query(30,ge=1,le=50),actor=Depends(student),db=Depends(connection,scope='function')):
    db.execute("SET LOCAL statement_timeout='2s'")
    rows=db.execute("""SELECT id,title,description,state,version,updated_at FROM courses WHERE tenant_id=%s AND state='published'
      AND (id>%s::uuid OR %s::uuid IS NULL) ORDER BY id LIMIT %s""",(actor.tenant_id,after,after,limit+1)).fetchall()
    return page(rows,limit,'courses')


@router.get('/{cid}')
def outline(cid:UUID,actor=Depends(student),db=Depends(connection,scope='function')):
    db.execute("SET LOCAL statement_timeout='2s'")
    eid=enrollment(db,actor,cid)
    row=db.execute('SELECT id,title,description,state,version FROM courses WHERE tenant_id=%s AND id=%s',(actor.tenant_id,cid)).fetchone()
    if not row:raise HTTPException(404,'Kursus tidak tersedia')
    modules=db.execute('SELECT id,title,position FROM course_modules WHERE tenant_id=%s AND course_id=%s ORDER BY position,id',(actor.tenant_id,cid)).fetchall()
    lessons=summaries(db,actor,cid,eid)
    grouped={}
    for lesson in lessons:grouped.setdefault(lesson['module_id'],[]).append(lesson)
    for module in modules:module['lessons']=grouped.get(module['id'],[])
    complete=sum(l['completed'] for l in lessons)
    row.update(modules=modules,progress={'completed':complete,'total':len(lessons)},
               resume=next(({'id':l['id'],'module_id':l['module_id']} for l in lessons if not l['completed']),None))
    return row


@router.get('/{cid}/modules/{mid}/lessons/{lid}')
def lesson(cid:UUID,mid:UUID,lid:UUID,actor=Depends(student),db=Depends(connection,scope='function')):
    db.execute("SET LOCAL statement_timeout='2s'")
    eid=enrollment(db,actor,cid)
    row=db.execute('SELECT id,title,content,resources,revision FROM course_lessons WHERE tenant_id=%s AND course_id=%s AND module_id=%s AND id=%s',
                   (actor.tenant_id,cid,mid,lid)).fetchone()
    if not row:raise HTTPException(404,'Pelajaran tidak tersedia')
    lessons=summaries(db,actor,cid,eid); index=next(i for i,l in enumerate(lessons) if l['id']==lid)
    def link(i):return {'id':lessons[i]['id'],'module_id':lessons[i]['module_id'],'title':lessons[i]['title']} if 0<=i<len(lessons) else None
    row.update(completed=lessons[index]['completed'],needs_review=lessons[index]['needs_review'],previous=link(index-1),next=link(index+1))
    return row


def change_completion(cid,mid,lid,body,actor,db,complete):
    eid=enrollment(db,actor,cid)
    row=db.execute('SELECT id,revision FROM course_lessons WHERE tenant_id=%s AND course_id=%s AND module_id=%s AND id=%s',
                   (actor.tenant_id,cid,mid,lid)).fetchone()
    if not row:raise HTTPException(404,'Pelajaran tidak tersedia')
    if row['revision']!=body.revision:raise HTTPException(409,'Materi telah berubah. Muat ulang pelajaran sebelum menandai selesai')
    if complete:
        changed=db.execute("""INSERT INTO lesson_progress(tenant_id,course_id,enrollment_id,student_id,lesson_id,lesson_revision)
          VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT(enrollment_id,lesson_id) DO UPDATE SET lesson_revision=excluded.lesson_revision,completed_at=now()
          WHERE lesson_progress.lesson_revision<>excluded.lesson_revision RETURNING lesson_id""",
          (actor.tenant_id,cid,eid,actor.user_id,lid,body.revision)).fetchone()
    else:
        changed=db.execute('DELETE FROM lesson_progress WHERE tenant_id=%s AND enrollment_id=%s AND lesson_id=%s RETURNING lesson_id',
                           (actor.tenant_id,eid,lid)).fetchone()
    if changed:audit(db,actor,'lesson.completed' if complete else 'lesson.uncompleted',lid,'lesson')
    return {'id':lid,'revision':row['revision'],'completed':complete}


@router.post('/{cid}/modules/{mid}/lessons/{lid}/complete',dependencies=[Depends(verify_origin)])
def complete(cid:UUID,mid:UUID,lid:UUID,body:Completion,actor=Depends(student),db=Depends(connection,scope='function')):
    return change_completion(cid,mid,lid,body,actor,db,True)


@router.post('/{cid}/modules/{mid}/lessons/{lid}/uncomplete',dependencies=[Depends(verify_origin)])
def uncomplete(cid:UUID,mid:UUID,lid:UUID,body:Completion,actor=Depends(student),db=Depends(connection,scope='function')):
    return change_completion(cid,mid,lid,body,actor,db,False)
