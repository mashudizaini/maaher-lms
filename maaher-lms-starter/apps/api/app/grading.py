"""Private rubric grading with explicit publication and append-only history."""
from typing import Literal
from uuid import UUID,uuid4
from fastapi import APIRouter,Depends,HTTPException,Query
from pydantic import Field,field_validator
from psycopg.errors import CheckViolation,ForeignKeyViolation,InsufficientPrivilege,UniqueViolation
from psycopg.types.json import Jsonb
from .auth import connection,verify_origin
from .courses import Input,manager
from .assignments import snapshot,plain,course,work
from .learning import student
from .enrollment import page

router=APIRouter(prefix='/grading')
REVISION_FIELDS='id,entry_version,revision_no,scores,total,feedback,reason,reviewer_id,created_at'
PUBLIC_FIELDS='version,state,revision_id,revision_no,scores,total,feedback,changed_at'


class Score(Input):
    criterion_index:int=Field(ge=0,le=9,strict=True)
    points:int=Field(ge=0,le=100,strict=True)
    comment:str=Field(default='',max_length=1000)
    @field_validator('comment')
    @classmethod
    def text(cls,value):return plain(value)


class Grade(Input):
    version:int=Field(ge=0,le=299,strict=True)
    scores:list[Score]=Field(min_length=1,max_length=10)
    feedback:str=Field(default='',max_length=6000)
    reason:str=Field(default='',max_length=1000)
    @field_validator('feedback','reason')
    @classmethod
    def text(cls,value):return plain(value)


class Transition(Input):
    version:int=Field(ge=1,le=299,strict=True)
    reason:str=Field(default='',max_length=1000)
    @field_validator('reason')
    @classmethod
    def text(cls,value):return plain(value).strip()


def publication(db,actor,sid):
    return db.execute('SELECT '+PUBLIC_FIELDS+' FROM grade_publications WHERE tenant_id=%s AND submission_id=%s',(actor.tenant_id,sid)).fetchone()


def require_active(db,actor,row):
    if course(db,actor,row['course_id'])['state']=='archived':raise HTTPException(409,'Pulihkan kursus dari arsip sebelum mengubah penilaian')


def locked_entry(db,actor,row,expected):
    # snapshot() has already authorized this submission before any lock.
    db.execute('INSERT INTO grading_entries(submission_id,tenant_id,course_id) VALUES(%s,%s,%s) ON CONFLICT DO NOTHING',(row['id'],actor.tenant_id,row['course_id']))
    entry=db.execute('SELECT version,draft_revision_id FROM grading_entries WHERE tenant_id=%s AND submission_id=%s FOR UPDATE /* grading-entry-lock */',(actor.tenant_id,row['id'])).fetchone()
    if not entry:raise HTTPException(404,'Penilaian tidak tersedia')
    if entry['version']!=expected:raise HTTPException(409,'Penilaian telah berubah. Muat ulang sebelum menyimpan')
    # A separate statement rechecks active course/authority after waiting; DB
    # VOLATILE trigger checks independently cover raw runtime SQL as well.
    require_active(db,actor,row)
    return entry


@router.get('/submissions')
def queue(course_id:UUID,assignment_id:UUID|None=None,after:UUID|None=None,
          state:Literal['all','ungraded','draft','released','withdrawn','pending']='all',limit:int=Query(30,ge=1,le=50),
          actor=Depends(manager),db=Depends(connection,scope='function')):
    course(db,actor,course_id)
    rows=db.execute('''WITH items AS (
      SELECT s.id,s.assignment_id,s.version_id,s.student_id,s.attempt_no,s.status,s.submitted_at,v.title,v.version_no,
       COALESCE(g.version,0) AS grade_version,p.total AS released_total,
       CASE WHEN g.draft_revision_id IS NULL THEN 'ungraded' WHEN p.state IS NOT NULL THEN p.state ELSE 'draft' END AS grade_state,
       (p.state='released' AND g.draft_revision_id<>p.revision_id) IS TRUE AS pending_changes
      FROM submissions s JOIN assignment_versions v ON v.id=s.version_id
      LEFT JOIN grading_entries g ON g.submission_id=s.id LEFT JOIN grade_publications p ON p.submission_id=s.id
      WHERE s.tenant_id=%s AND s.course_id=%s AND (%s::uuid IS NULL OR s.assignment_id=%s) AND (%s::uuid IS NULL OR s.id>%s))
      SELECT * FROM items WHERE %s='all' OR grade_state=%s OR (%s='pending' AND pending_changes) ORDER BY id LIMIT %s''',
      (actor.tenant_id,course_id,assignment_id,assignment_id,after,after,state,state,state,limit+1)).fetchall()
    return page(rows,limit,'submissions')


@router.get('/submissions/{sid}')
def detail(sid:UUID,actor=Depends(manager),db=Depends(connection,scope='function')):
    row=snapshot(db,actor,sid)
    entry=db.execute('SELECT version,draft_revision_id,last_action,last_reason,updated_at FROM grading_entries WHERE tenant_id=%s AND submission_id=%s',(actor.tenant_id,sid)).fetchone()
    draft=None
    if entry and entry['draft_revision_id']:
        draft=db.execute('SELECT '+REVISION_FIELDS+' FROM grade_revisions WHERE tenant_id=%s AND id=%s',(actor.tenant_id,entry['draft_revision_id'])).fetchone()
    return {'submission':row,'read_only':course(db,actor,row['course_id'])['state']=='archived','version':entry['version'] if entry else 0,'draft':draft,'publication':publication(db,actor,sid)}


@router.get('/submissions/{sid}/history')
def history(sid:UUID,after:int=Query(0,ge=0,le=300),actor=Depends(manager),db=Depends(connection,scope='function')):
    snapshot(db,actor,sid)
    events=db.execute('''SELECT id,version,action,revision_id,reason,actor_id,created_at FROM grading_events
      WHERE tenant_id=%s AND submission_id=%s AND version>%s ORDER BY version LIMIT 21''',(actor.tenant_id,sid,after)).fetchall()
    ids=list({row['revision_id'] for row in events[:20]})
    revisions=db.execute('SELECT '+REVISION_FIELDS+' FROM grade_revisions WHERE tenant_id=%s AND submission_id=%s AND id=ANY(%s) ORDER BY revision_no',(actor.tenant_id,sid,ids)).fetchall() if ids else []
    return {'events':events[:20],'revisions':revisions,'next_version':events[19]['version'] if len(events)>20 else None}


def validate_scores(body,row):
    rubric=row['assignment_version']['rubric'];scores=sorted(body.scores,key=lambda item:item.criterion_index)
    if [score.criterion_index for score in scores]!=list(range(len(rubric))) or any(score.points>rubric[score.criterion_index]['max_points'] for score in scores):
        raise HTTPException(422,'Isi setiap kriteria tepat satu kali dengan poin sesuai rubrik versi submission')
    return scores


@router.post('/submissions/{sid}/draft',dependencies=[Depends(verify_origin)],status_code=201)
def save(sid:UUID,body:Grade,actor=Depends(manager),db=Depends(connection,scope='function')):
    row=snapshot(db,actor,sid);require_active(db,actor,row);scores=validate_scores(body,row)
    try:
        locked_entry(db,actor,row,body.version)
        released=publication(db,actor,sid)
        if released and released['state']=='released' and not body.reason.strip():raise HTTPException(422,'Alasan koreksi diperlukan ketika nilai sudah dibagikan')
        rev=db.execute('''INSERT INTO grade_revisions(id,tenant_id,course_id,submission_id,entry_version,revision_no,scores,total,feedback,reason,reviewer_id)
          VALUES(%s,%s,%s,%s,%s,1,%s,0,%s,%s,%s) RETURNING id,entry_version,revision_no,total''',
          (uuid4(),actor.tenant_id,row['course_id'],sid,body.version+1,Jsonb([score.model_dump() for score in scores]),body.feedback,body.reason,actor.user_id)).fetchone()
    except (CheckViolation,ForeignKeyViolation,InsufficientPrivilege,UniqueViolation):raise HTTPException(409,'Penilaian atau akses berubah, atau batas riwayat tercapai. Muat ulang sebelum mencoba lagi') from None
    return {'submission_id':sid,'version':rev['entry_version'],'revision_id':rev['id'],'revision_no':rev['revision_no'],'total':rev['total']}


@router.post('/submissions/{sid}/{operation}',dependencies=[Depends(verify_origin)])
def transition(sid:UUID,operation:Literal['release','withdraw'],body:Transition,actor=Depends(manager),db=Depends(connection,scope='function')):
    row=snapshot(db,actor,sid);require_active(db,actor,row)
    try:
        entry=locked_entry(db,actor,row,body.version);pub=publication(db,actor,sid)
        if not entry['draft_revision_id']:raise HTTPException(409,'Simpan draf nilai terlebih dahulu')
        if operation=='withdraw' and (not pub or pub['state']!='released'):raise HTTPException(409,'Belum ada nilai yang dapat ditarik')
        if (operation=='withdraw' or pub and pub['state']=='released') and not body.reason:
            raise HTTPException(422,'Alasan koreksi atau penarikan wajib diisi')
        changed=db.execute('''UPDATE grading_entries SET version=version+1,last_action=%s,last_reason=%s
          WHERE tenant_id=%s AND submission_id=%s AND version=%s RETURNING version''',
          ('released' if operation=='release' else 'withdrawn',body.reason,actor.tenant_id,sid,body.version)).fetchone()
        if not changed:raise HTTPException(409,'Penilaian telah berubah. Muat ulang')
    except (CheckViolation,ForeignKeyViolation,InsufficientPrivilege,UniqueViolation):raise HTTPException(409,'Status penilaian atau akses telah berubah. Muat ulang sebelum mencoba lagi') from None
    return {'submission_id':sid,'version':changed['version'],'publication':publication(db,actor,sid)}


@work.get('/submissions/{sid}/grade')
def student_grade(sid:UUID,actor=Depends(student),db=Depends(connection,scope='function')):
    # Same own-enrollment and published-course contract as the immutable snapshot.
    snapshot(db,actor,sid)
    row=publication(db,actor,sid)
    return {'state':row['state'] if row else 'ungraded','grade':row if row and row['state']=='released' else None}
