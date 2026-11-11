"""Original assignment authoring and own append-only submission workflow."""
from datetime import datetime,timezone
from typing import Literal
from uuid import UUID,uuid4
from fastapi import APIRouter,Depends,HTTPException,Query
from pydantic import Field,field_validator,model_validator
from psycopg.errors import CheckViolation,ForeignKeyViolation,UniqueViolation
from psycopg.types.json import Jsonb
from .auth import connection,verify_origin
from .courses import Input,Version,manager,audit,validate_lesson_content
from .learning import student,enrollment
from .content_attestation import seal,valid
from .enrollment import page

router=APIRouter(prefix='/assignments')
work=APIRouter(prefix='/work')
VERSION_FIELDS='id,assignment_id,version_no,title,instructions,language,starter_code,rubric,due_at,max_attempts,allow_late,created_at'
META='id,course_id,assignment_id,version_id,attempt_no,draft_revision,submitted_at,status'


class Criterion(Input):
    criterion:str=Field(min_length=1,max_length=200)
    max_points:int=Field(ge=1,le=100,strict=True)
    @field_validator('criterion')
    @classmethod
    def name(cls,value):
        if not value.strip():raise ValueError('Kriteria wajib diisi')
        return plain(value.strip())


class Content(Input):
    title:str=Field(min_length=1,max_length=160)
    instructions:str=Field(min_length=1,max_length=30000)
    language:Literal['python','javascript','text']='python'
    starter_code:str=Field(default='',max_length=30000)
    rubric:list[Criterion]=Field(min_length=1,max_length=10)
    due_at:datetime|None=None
    max_attempts:int=Field(default=3,ge=1,le=20)
    allow_late:bool=False
    @field_validator('title','instructions')
    @classmethod
    def required(cls,value):
        if not value.strip():raise ValueError('Judul dan instruksi wajib diisi')
        return value.strip()
    @field_validator('title','instructions','starter_code')
    @classmethod
    def encoding(cls,value):return plain(value)
    @field_validator('due_at')
    @classmethod
    def aware(cls,value):
        if value is not None:
            if value.tzinfo is None or value.utcoffset() is None:raise ValueError('Deadline harus memuat zona waktu')
            return value.astimezone(timezone.utc)
        return value
    @model_validator(mode='after')
    def total(self):
        if sum(c.max_points for c in self.rubric)!=100:raise ValueError('Total rubrik harus 100 poin')
        return self


class New(Content):
    course_id:UUID
    lesson_id:UUID


class Edit(Content,Version):pass


class Draft(Input):
    version_id:UUID
    revision:int=Field(ge=0)
    source_code:str=Field(default='',max_length=30000)
    note:str=Field(default='',max_length=2000)
    @field_validator('source_code','note')
    @classmethod
    def text(cls,value):return plain(value)


class Submit(Input):
    version_id:UUID
    draft_revision:int=Field(ge=1)
    request_id:UUID


def plain(value):
    if '\x00' in value:raise ValueError('Teks memuat karakter NUL')
    try:value.encode('utf8')
    except UnicodeError:raise ValueError('Encoding teks tidak valid') from None
    return value


def course(db,actor,cid,lock=False):
    row=db.execute('SELECT id,state FROM courses WHERE tenant_id=%s AND id=%s'+(' FOR UPDATE' if lock else ''),(actor.tenant_id,cid)).fetchone()
    if not row:raise HTTPException(404,'Kursus tidak ditemukan')
    return row


def task(db,actor,aid,version=None,mutable=False):
    row=db.execute('SELECT id,course_id,lesson_id,state,version,draft_version_id,published_version_id FROM assignments WHERE tenant_id=%s AND id=%s'+(' FOR UPDATE' if mutable else ''),(actor.tenant_id,aid)).fetchone()
    if not row:raise HTTPException(404,'Tugas tidak tersedia')
    c=course(db,actor,row['course_id'])
    if mutable and c['state']=='archived':raise HTTPException(409,'Pulihkan kursus dari arsip terlebih dahulu')
    if version is not None and row['version']!=version:raise HTTPException(409,'Tugas telah berubah. Muat ulang sebelum menyimpan')
    return row


def version_data(db,actor,vid):
    if vid is None:return None
    return db.execute('SELECT '+VERSION_FIELDS+' FROM assignment_versions WHERE tenant_id=%s AND id=%s',(actor.tenant_id,vid)).fetchone()


def proof_payload(data):
    # Same canonical values before INSERT and after PostgreSQL readback.
    return [data['title'],data['language'],data['starter_code'],data['rubric'],data['due_at'].astimezone(timezone.utc).isoformat() if data['due_at'] else None,data['max_attempts'],data['allow_late']]


def add_version(db,actor,row,body):
    validate_lesson_content(type('Material',(),{'content':body.instructions})(),actor)
    number=db.execute('SELECT coalesce(max(version_no),0)+1 AS n FROM assignment_versions WHERE tenant_id=%s AND assignment_id=%s',(actor.tenant_id,row['id'])).fetchone()['n']
    if number>100:raise HTTPException(409,'Batas 100 versi per tugas telah tercapai')
    vid=uuid4();data=body.model_dump(include=set(Content.model_fields));data['rubric']=[c.model_dump() for c in body.rubric]
    proof=seal('assignment',(actor.tenant_id,row['id'],vid,number),data['instructions'],proof_payload(data))
    db.execute('''INSERT INTO assignment_versions(id,tenant_id,course_id,assignment_id,version_no,title,instructions,language,starter_code,rubric,due_at,max_attempts,allow_late,content_attestation)
      VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
      (vid,actor.tenant_id,row['course_id'],row['id'],number,data['title'],data['instructions'],data['language'],data['starter_code'],Jsonb(data['rubric']),data['due_at'],data['max_attempts'],data['allow_late'],proof))
    return vid


def update(db,actor,row,**values):
    # Column names are exclusively server constants.
    from psycopg import sql
    return db.execute(sql.SQL('UPDATE assignments SET {},version=version+1,updated_at=now() WHERE tenant_id=%s AND id=%s RETURNING id,state,version,draft_version_id,published_version_id').format(
       sql.SQL(',').join(sql.SQL('{}=%s').format(sql.Identifier(k)) for k in values)),(*values.values(),actor.tenant_id,row['id'])).fetchone()


@router.get('')
def listing(course_id:UUID,lesson_id:UUID|None=None,after:UUID|None=None,limit:int=Query(30,ge=1,le=50),actor=Depends(manager),db=Depends(connection,scope='function')):
    course(db,actor,course_id)
    rows=db.execute('''SELECT a.id,a.lesson_id,a.state,a.version,a.draft_version_id,a.published_version_id,v.title,v.version_no FROM assignments a
       LEFT JOIN assignment_versions v ON v.id=a.draft_version_id WHERE a.tenant_id=%s AND a.course_id=%s
       AND (%s::uuid IS NULL OR a.lesson_id=%s) AND (%s::uuid IS NULL OR a.id>%s) ORDER BY a.id LIMIT %s''',(actor.tenant_id,course_id,lesson_id,lesson_id,after,after,limit+1)).fetchall()
    return page(rows,limit,'assignments')


@router.post('',dependencies=[Depends(verify_origin)],status_code=201)
def create(body:New,actor=Depends(manager),db=Depends(connection,scope='function')):
    c=course(db,actor,body.course_id,lock=True)
    if c['state']=='archived':raise HTTPException(409,'Pulihkan kursus dari arsip terlebih dahulu')
    if not db.execute('SELECT id FROM course_lessons WHERE tenant_id=%s AND course_id=%s AND id=%s',(actor.tenant_id,body.course_id,body.lesson_id)).fetchone():raise HTTPException(404,'Pelajaran tidak ditemukan')
    db.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",('assignment-create:'+str(body.course_id),))
    if db.execute('SELECT count(*) AS n FROM assignments WHERE tenant_id=%s AND course_id=%s',(actor.tenant_id,body.course_id)).fetchone()['n']>=100:raise HTTPException(409,'Batas 100 tugas per kursus telah tercapai')
    row={'id':uuid4(),'course_id':body.course_id}
    db.execute('INSERT INTO assignments(id,tenant_id,course_id,lesson_id) VALUES(%s,%s,%s,%s)',(row['id'],actor.tenant_id,body.course_id,body.lesson_id))
    vid=add_version(db,actor,row,body)
    result=db.execute('UPDATE assignments SET draft_version_id=%s WHERE tenant_id=%s AND id=%s RETURNING id,state,version,draft_version_id,published_version_id',(vid,actor.tenant_id,row['id'])).fetchone()
    audit(db,actor,'assignment.created',row['id'],'assignment');return result


@router.get('/{aid}')
def detail(aid:UUID,actor=Depends(manager),db=Depends(connection,scope='function')):
    row=task(db,actor,aid);row['draft']=version_data(db,actor,row['draft_version_id']);row['published']=version_data(db,actor,row['published_version_id']);return row


@router.get('/{aid}/versions')
def versions(aid:UUID,after:int=Query(0,ge=0),actor=Depends(manager),db=Depends(connection,scope='function')):
    task(db,actor,aid)
    rows=db.execute('SELECT '+VERSION_FIELDS+' FROM assignment_versions WHERE tenant_id=%s AND assignment_id=%s AND version_no>%s ORDER BY version_no LIMIT 21',(actor.tenant_id,aid,after)).fetchall()
    return {'versions':rows[:20],'next_version':rows[19]['version_no'] if len(rows)>20 else None}


@router.post('/{aid}',dependencies=[Depends(verify_origin)])
def edit(aid:UUID,body:Edit,actor=Depends(manager),db=Depends(connection,scope='function')):
    row=task(db,actor,aid,body.version,True)
    if row['state']=='archived':raise HTTPException(409,'Pulihkan tugas dari arsip terlebih dahulu')
    vid=add_version(db,actor,row,body);result=update(db,actor,row,draft_version_id=vid)
    audit(db,actor,'assignment.version_saved',aid,'assignment');return result


@router.post('/{aid}/{operation}',dependencies=[Depends(verify_origin)])
def transition(aid:UUID,operation:Literal['publish','unpublish','archive','restore'],body:Version,actor=Depends(manager),db=Depends(connection,scope='function')):
    row=task(db,actor,aid,body.version,True)
    if row['state']=='archived' and operation!='restore':raise HTTPException(409,'Pulihkan tugas dari arsip terlebih dahulu')
    if operation=='restore' and row['state']!='archived':raise HTTPException(409,'Tugas tidak berada di arsip')
    values={'state':{'publish':'published','unpublish':'draft','archive':'archived','restore':'draft'}[operation]}
    if operation=='publish':
        v=db.execute('SELECT * FROM assignment_versions WHERE tenant_id=%s AND id=%s',(actor.tenant_id,row['draft_version_id'])).fetchone()
        if not v or not valid(v['content_attestation'],'assignment',(actor.tenant_id,aid,v['id'],v['version_no']),v['instructions'],proof_payload(v)):
            raise HTTPException(409,'Instruksi perlu divalidasi ulang. Simpan versi baru sebelum menerbitkan')
        values['published_version_id']=v['id']
    result=update(db,actor,row,**values);audit(db,actor,'assignment.'+operation,aid,'assignment');return result


def student_task(db,actor,aid):
    row=task(db,actor,aid)
    if row['state']!='published':raise HTTPException(404,'Tugas tidak tersedia')
    eid=enrollment(db,actor,row['course_id'])
    return row,eid


@work.get('/assignments')
def available(course_id:UUID,lesson_id:UUID|None=None,after:UUID|None=None,limit:int=Query(30,ge=1,le=50),actor=Depends(student),db=Depends(connection,scope='function')):
    enrollment(db,actor,course_id);course(db,actor,course_id)
    rows=db.execute('''SELECT a.id,a.lesson_id,a.published_version_id,v.title,v.version_no,v.due_at,v.max_attempts,v.allow_late
       FROM assignments a JOIN assignment_versions v ON v.id=a.published_version_id WHERE a.tenant_id=%s AND a.course_id=%s AND a.state='published'
       AND (%s::uuid IS NULL OR a.lesson_id=%s) AND (%s::uuid IS NULL OR a.id>%s) ORDER BY a.id LIMIT %s''',(actor.tenant_id,course_id,lesson_id,lesson_id,after,after,limit+1)).fetchall()
    return page(rows,limit,'assignments')


@work.get('/assignments/{aid}')
def current(aid:UUID,actor=Depends(student),db=Depends(connection,scope='function')):
    row,eid=student_task(db,actor,aid)
    draft=db.execute('SELECT version_id,revision,source_code,note,updated_at FROM submission_drafts WHERE tenant_id=%s AND assignment_id=%s AND enrollment_id=%s',(actor.tenant_id,aid,eid)).fetchone()
    attempts=db.execute('SELECT count(*) AS n FROM submissions WHERE tenant_id=%s AND assignment_id=%s AND enrollment_id=%s',(actor.tenant_id,aid,eid)).fetchone()['n']
    return {'id':aid,'course_id':row['course_id'],'lesson_id':row['lesson_id'],'published':version_data(db,actor,row['published_version_id']),'draft':draft,'attempts':attempts}


@work.post('/assignments/{aid}/draft',dependencies=[Depends(verify_origin)])
def save(aid:UUID,body:Draft,actor=Depends(student),db=Depends(connection,scope='function')):
    row,eid=student_task(db,actor,aid)
    if row['published_version_id']!=body.version_id:raise HTTPException(409,'Versi tugas berubah. Muat ulang dan periksa jawaban sebelum menyimpan pada versi baru')
    try:
        if body.revision==0:
            result=db.execute('''INSERT INTO submission_drafts(tenant_id,course_id,assignment_id,enrollment_id,student_id,version_id,source_code,note)
              VALUES(%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING revision,version_id,updated_at''',(actor.tenant_id,row['course_id'],aid,eid,actor.user_id,body.version_id,body.source_code,body.note)).fetchone()
        else:
            result=db.execute('''UPDATE submission_drafts SET version_id=%s,source_code=%s,note=%s WHERE tenant_id=%s AND assignment_id=%s AND enrollment_id=%s AND revision=%s RETURNING revision,version_id,updated_at''',(body.version_id,body.source_code,body.note,actor.tenant_id,aid,eid,body.revision)).fetchone()
    except CheckViolation:raise HTTPException(409,'Versi atau enrollment berubah. Muat ulang sebelum menyimpan') from None
    if not result:raise HTTPException(409,'Draf telah berubah di sesi lain. Muat ulang sebelum menyimpan')
    audit(db,actor,'submission.draft_saved',aid,'assignment');return result


@work.post('/assignments/{aid}/submit',dependencies=[Depends(verify_origin)],status_code=201)
def submit(aid:UUID,body:Submit,actor=Depends(student),db=Depends(connection,scope='function')):
    row,eid=student_task(db,actor,aid)
    # Same order as database trigger; authority checked before either lock.
    db.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',('maaher-assignment:'+str(aid),))
    db.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',('maaher-submit:'+str(aid)+':'+str(eid),))
    old=db.execute('SELECT '+META+' FROM submissions WHERE tenant_id=%s AND assignment_id=%s AND enrollment_id=%s AND request_id=%s',(actor.tenant_id,aid,eid,body.request_id)).fetchone()
    if old:
        if old['version_id']!=body.version_id or old['draft_revision']!=body.draft_revision:raise HTTPException(409,'ID permintaan sudah digunakan untuk draf lain')
        return old
    try:
        result=db.execute('''INSERT INTO submissions(id,tenant_id,course_id,assignment_id,enrollment_id,student_id,version_id,draft_revision,request_id,attempt_no,source_code,note,submitted_at,status)
          VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,1,'','',now(),'submitted') RETURNING '''+META,(uuid4(),actor.tenant_id,row['course_id'],aid,eid,actor.user_id,body.version_id,body.draft_revision,body.request_id)).fetchone()
    except (CheckViolation,ForeignKeyViolation,UniqueViolation):
        raise HTTPException(409,'Pengiriman ditolak: periksa versi/draf terbaru, deadline, enrollment, atau batas percobaan') from None
    audit(db,actor,'submission.submitted',result['id'],'submission');return result


def history_rows(db,actor,cid,aid,after,limit,staff=False):
    course(db,actor,cid)
    if not staff:enrollment(db,actor,cid)
    rows=db.execute('SELECT '+META+(',student_id' if staff else '')+''' FROM submissions WHERE tenant_id=%s AND course_id=%s AND (%s::uuid IS NULL OR assignment_id=%s)
       AND (%s::uuid IS NULL OR id>%s) ORDER BY id LIMIT %s''',(actor.tenant_id,cid,aid,aid,after,after,limit+1)).fetchall()
    return page(rows,limit,'submissions')


@work.get('/submissions')
def history(course_id:UUID,assignment_id:UUID|None=None,after:UUID|None=None,limit:int=Query(30,ge=1,le=50),actor=Depends(student),db=Depends(connection,scope='function')):
    return history_rows(db,actor,course_id,assignment_id,after,limit)


def snapshot(db,actor,sid):
    row=db.execute('SELECT '+META+',student_id,source_code,note FROM submissions WHERE tenant_id=%s AND id=%s',(actor.tenant_id,sid)).fetchone()
    if not row:raise HTTPException(404,'Submission tidak tersedia')
    course(db,actor,row['course_id']);row['assignment_version']=version_data(db,actor,row['version_id']);return row


@work.get('/submissions/{sid}')
def submission_detail(sid:UUID,actor=Depends(student),db=Depends(connection,scope='function')):return snapshot(db,actor,sid)


# Staff submission routes use a distinct prefix so UUID task routes stay explicit.
review=APIRouter(prefix='/assignment-submissions')
@review.get('')
def received(course_id:UUID,assignment_id:UUID|None=None,after:UUID|None=None,limit:int=Query(30,ge=1,le=50),actor=Depends(manager),db=Depends(connection,scope='function')):
    return history_rows(db,actor,course_id,assignment_id,after,limit,True)


@review.get('/{sid}')
def received_detail(sid:UUID,actor=Depends(manager),db=Depends(connection,scope='function')):return snapshot(db,actor,sid)
