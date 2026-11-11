"""Course authoring: validated session, tenant RLS, assignments and version locks."""
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from psycopg.types.json import Jsonb
from psycopg.errors import CheckViolation, ForeignKeyViolation

from .auth import connection, principal, verify_origin
from .security import Principal
from .course_content import https_resource, validate_markdown
from .markdown_service import MarkdownComplexity,validate_maintenance
from .content_attestation import seal,valid
from .auth_support import cipher
import time

router = APIRouter(prefix="/courses")


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Title(Input):
    title: str = Field(min_length=1, max_length=160)

    @field_validator("title")
    @classmethod
    def trimmed(cls, value):
        if not value.strip():
            raise ValueError("Judul wajib diisi")
        return value.strip()


class Version(Input):
    version: int = Field(ge=1)


class NewCourse(Title):
    description: str = Field(default="", max_length=2000)


class EditCourse(NewCourse, Version):
    pass


class Module(Title, Version):
    pass


class Resource(Input):
    label: str = Field(min_length=1, max_length=120)
    url: str = Field(min_length=1, max_length=2048)
    _https = field_validator("url")(https_resource)


class Lesson(Title, Version):
    content: str = Field(default="", max_length=30000)
    resources: list[Resource] = Field(default_factory=list, max_length=10)



def validate_lesson_content(body,actor=None):
    # Called inside synchronous endpoints, which FastAPI runs in a worker.
    # CommonMark adversarial input must not block the ASGI event loop.
    try:
        if actor is None:validate_markdown(body.content)
        else:validate_markdown(body.content,f"{actor.tenant_id}:{actor.user_id}")
    except MarkdownComplexity as error:
        raise HTTPException(422,str(error)) from None
    except ValueError:
        raise HTTPException(422, [{"type":"value_error", "loc":["body","content"],
            "msg":"Materi hanya boleh memakai tautan HTTPS publik tanpa karakter tersembunyi"}]) from None


class Teacher(Version):
    user_id: UUID
    assigned: bool


class Order(Version):
    ids: list[UUID] = Field(max_length=50)


def manager(actor: Principal = Depends(principal)):
    if actor.role not in {"admin", "teacher"}:
        raise HTTPException(403, "Pengelolaan kursus tersedia bagi admin dan pengajar")
    return actor


def admin(actor):
    if actor.role != "admin":
        raise HTTPException(403, "Tindakan ini memerlukan admin organisasi")


def audit(db, actor, action, target, kind="course"):
    db.execute("INSERT INTO audit_events(id,tenant_id,actor_id,action,target_type,target_id) VALUES(%s,%s,%s,%s,%s,%s)",
               (uuid4(), actor.tenant_id, actor.user_id, action, kind, target))


def locked(db, actor, course_id, version, archived=False):
    row = db.execute("SELECT id,state,version FROM courses WHERE tenant_id=%s AND id=%s FOR UPDATE", (actor.tenant_id, course_id)).fetchone()
    if not row:
        raise HTTPException(404, "Kursus tidak ditemukan")
    if row["version"] != version:
        raise HTTPException(409, "Kursus telah berubah. Muat ulang sebelum menyimpan")
    if row["state"] == "archived" and not archived:
        raise HTTPException(409, "Pulihkan kursus dari arsip terlebih dahulu")
    return row


def changed(db, actor, course_id, state="draft"):
    return db.execute("UPDATE courses SET state=%s,version=version+1,updated_at=now() WHERE tenant_id=%s AND id=%s RETURNING version,state",
                      (state, actor.tenant_id, course_id)).fetchone()


def draft(db, actor, course_id):
    # The same transaction returns published courses to draft before any edit.
    db.execute("UPDATE courses SET state='draft' WHERE tenant_id=%s AND id=%s", (actor.tenant_id, course_id))


def module_exists(db, actor, cid, mid):
    if not db.execute("SELECT 1 FROM course_modules WHERE tenant_id=%s AND course_id=%s AND id=%s", (actor.tenant_id, cid, mid)).fetchone():
        raise HTTPException(404, "Modul tidak ditemukan")


@router.get("")
def course_list(after: UUID | None = None, archived: bool = False, limit: int = Query(30, ge=1, le=50),
                actor=Depends(manager), db=Depends(connection, scope="function")):
    rows = db.execute("""SELECT id,title,description,state,version,updated_at FROM courses WHERE tenant_id=%s
        AND (id>%s::uuid OR %s::uuid IS NULL) AND (state='archived')=%s ORDER BY id LIMIT %s""",
        (actor.tenant_id, after, after, archived, limit + 1)).fetchall()
    return {"courses": rows[:limit], "next_cursor": str(rows[limit - 1]["id"]) if len(rows) > limit else None}


@router.post("", dependencies=[Depends(verify_origin)], status_code=201)
def create_course(body: NewCourse, actor=Depends(manager), db=Depends(connection, scope="function")):
    admin(actor)
    db.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", ("course-create:" + str(actor.tenant_id),))
    if db.execute("SELECT count(*) AS n FROM courses WHERE tenant_id=%s", (actor.tenant_id,)).fetchone()["n"] >= 500:
        raise HTTPException(409, "Batas 500 kursus per organisasi telah tercapai")
    cid = uuid4()
    row = db.execute("INSERT INTO courses(id,tenant_id,owner_id,title,description) VALUES(%s,%s,%s,%s,%s) RETURNING id,version,state",
                     (cid, actor.tenant_id, actor.user_id, body.title, body.description)).fetchone()
    audit(db, actor, "course.created", cid)
    return row


@router.get("/{cid}")
def course_detail(cid: UUID, actor=Depends(manager), db=Depends(connection, scope="function")):
    row = db.execute("SELECT id,title,description,state,version,created_at,updated_at FROM courses WHERE tenant_id=%s AND id=%s", (actor.tenant_id, cid)).fetchone()
    if not row:
        raise HTTPException(404, "Kursus tidak ditemukan")
    modules = db.execute("SELECT id,title,position FROM course_modules WHERE tenant_id=%s AND course_id=%s ORDER BY position,id",
                         (actor.tenant_id, cid)).fetchall()
    lessons = db.execute("SELECT id,module_id,title,position FROM course_lessons WHERE tenant_id=%s AND course_id=%s ORDER BY position,id",
                         (actor.tenant_id, cid)).fetchall()
    for mod in modules:
        mod["lessons"] = [lesson for lesson in lessons if lesson["module_id"] == mod["id"]]
    row["modules"] = modules
    row["teachers"] = [str(r["user_id"]) for r in db.execute("SELECT user_id FROM courses_teachers WHERE tenant_id=%s AND course_id=%s ORDER BY user_id", (actor.tenant_id, cid)).fetchall()]
    return row


@router.post("/{cid}", dependencies=[Depends(verify_origin)])
def edit_course(cid: UUID, body: EditCourse, actor=Depends(manager), db=Depends(connection, scope="function")):
    locked(db, actor, cid, body.version)
    db.execute("UPDATE courses SET title=%s,description=%s WHERE tenant_id=%s AND id=%s", (body.title, body.description, actor.tenant_id, cid))
    result = changed(db, actor, cid)
    audit(db, actor, "course.updated", cid)
    return result


@router.post("/{cid}/publish", dependencies=[Depends(verify_origin)])
def publish(cid: UUID, body: Version, actor=Depends(manager), db=Depends(connection, scope="function")):
    locked(db, actor, cid, body.version)
    modules = db.execute("SELECT id FROM course_modules WHERE tenant_id=%s AND course_id=%s", (actor.tenant_id, cid)).fetchall()
    incomplete = db.execute("""SELECT 1 FROM course_modules m WHERE m.tenant_id=%s AND m.course_id=%s
        AND NOT EXISTS(SELECT 1 FROM course_lessons l WHERE l.tenant_id=m.tenant_id AND l.course_id=m.course_id AND l.module_id=m.id) LIMIT 1""", (actor.tenant_id, cid)).fetchone()
    empty = db.execute("SELECT 1 FROM course_lessons WHERE tenant_id=%s AND course_id=%s AND length(btrim(content))=0 LIMIT 1", (actor.tenant_id, cid)).fetchone()
    if not modules or incomplete or empty:
        raise HTTPException(409, "Isi setiap modul dengan pelajaran dan materi sebelum menerbitkan")
    # Saved, signed proofs make this a bounded linear scan, never parser work.
    ring=cipher()
    with db.cursor(name="course_publish_links") as cursor:
        cursor.itersize=20
        cursor.execute("SELECT id,revision,content,resources,content_attestation FROM course_lessons WHERE tenant_id=%s AND course_id=%s",(actor.tenant_id,cid))
        for lesson in cursor:
            if not valid(lesson['content_attestation'],'lesson',(actor.tenant_id,lesson['id'],lesson['revision']),lesson['content'],lesson['resources'],ring):
                raise HTTPException(409,'Materi belum diverifikasi pada revisi ini. Gunakan Periksa materi lama sebelum menerbitkan')
    result = changed(db, actor, cid, "published"); audit(db, actor, "course.published", cid)
    return result


@router.post("/{cid}/unpublish", dependencies=[Depends(verify_origin)])
def unpublish(cid: UUID, body: Version, actor=Depends(manager), db=Depends(connection, scope="function")):
    locked(db, actor, cid, body.version)
    result = changed(db, actor, cid); audit(db, actor, "course.unpublished", cid)
    return result


@router.post("/{cid}/archive", dependencies=[Depends(verify_origin)])
def archive(cid: UUID, body: Version, actor=Depends(manager), db=Depends(connection, scope="function")):
    admin(actor); locked(db, actor, cid, body.version)
    result = changed(db, actor, cid, "archived"); audit(db, actor, "course.archived", cid)
    return result


@router.post("/{cid}/restore", dependencies=[Depends(verify_origin)])
def restore(cid: UUID, body: Version, actor=Depends(manager), db=Depends(connection, scope="function")):
    admin(actor); locked(db, actor, cid, body.version, archived=True)
    result = changed(db, actor, cid); audit(db, actor, "course.restored", cid)
    return result


@router.post("/{cid}/teachers", dependencies=[Depends(verify_origin)])
def assign_teacher(cid: UUID, body: Teacher, actor=Depends(manager), db=Depends(connection, scope="function")):
    admin(actor); course = locked(db, actor, cid, body.version)
    if body.assigned:
        role = db.execute("SELECT course_member_role(%s,%s) AS role", (actor.tenant_id, body.user_id)).fetchone()["role"]
        if role != "teacher":
            raise HTTPException(404, "Pengajar aktif tidak ditemukan dalam organisasi ini")
        count = db.execute("SELECT count(*) AS n FROM courses_teachers WHERE tenant_id=%s AND course_id=%s", (actor.tenant_id, cid)).fetchone()["n"]
        present = db.execute("SELECT 1 FROM courses_teachers WHERE tenant_id=%s AND course_id=%s AND user_id=%s", (actor.tenant_id, cid, body.user_id)).fetchone()
        if count >= 50 and not present:
            raise HTTPException(409, "Batas 50 pengajar per kursus telah tercapai")
        try:
            db.execute("INSERT INTO courses_teachers(tenant_id,course_id,user_id) VALUES(%s,%s,%s) ON CONFLICT DO NOTHING", (actor.tenant_id, cid, body.user_id))
        except (CheckViolation, ForeignKeyViolation):
            raise HTTPException(409, "Keanggotaan pengajar telah berubah. Muat ulang sebelum menugaskan") from None
    else:
        db.execute("DELETE FROM courses_teachers WHERE tenant_id=%s AND course_id=%s AND user_id=%s", (actor.tenant_id, cid, body.user_id))
    result = changed(db, actor, cid, course["state"]); audit(db, actor, "course.teacher_assigned" if body.assigned else "course.teacher_removed", body.user_id, "course_teacher")
    return result


@router.post("/{cid}/modules", dependencies=[Depends(verify_origin)], status_code=201)
def create_module(cid: UUID, body: Module, actor=Depends(manager), db=Depends(connection, scope="function")):
    locked(db, actor, cid, body.version)
    count = db.execute("SELECT count(*) AS n FROM course_modules WHERE tenant_id=%s AND course_id=%s", (actor.tenant_id, cid)).fetchone()["n"]
    if count >= 30: raise HTTPException(409, "Batas 30 modul per kursus telah tercapai")
    draft(db, actor, cid); mid = uuid4()
    db.execute("INSERT INTO course_modules(id,tenant_id,course_id,title,position) VALUES(%s,%s,%s,%s,%s)", (mid, actor.tenant_id, cid, body.title, count + 1))
    result = changed(db, actor, cid); audit(db, actor, "module.created", mid, "module")
    return {**result, "id": mid}


@router.post("/{cid}/modules/{mid}", dependencies=[Depends(verify_origin)])
def edit_module(cid: UUID, mid: UUID, body: Module, actor=Depends(manager), db=Depends(connection, scope="function")):
    locked(db, actor, cid, body.version); module_exists(db, actor, cid, mid); draft(db, actor, cid)
    db.execute("UPDATE course_modules SET title=%s WHERE tenant_id=%s AND course_id=%s AND id=%s", (body.title, actor.tenant_id, cid, mid))
    result = changed(db, actor, cid); audit(db, actor, "module.updated", mid, "module")
    return result


def reorder(db, actor, cid, table, ids, mid=None):
    # Table is selected only by server constants, never by request input.
    clause, params = "tenant_id=%s AND course_id=%s", [actor.tenant_id, cid]
    if mid is not None: clause += " AND module_id=%s"; params.append(mid)
    rows = db.execute("SELECT id FROM " + table + " WHERE " + clause + " ORDER BY position,id", params).fetchall()
    if len(ids) != len(set(ids)) or set(ids) != {r["id"] for r in rows}:
        raise HTTPException(409, "Urutan harus memuat seluruh item pada induk yang sama, tepat satu kali")
    for position, item in enumerate(ids, 1):
        db.execute("UPDATE " + table + " SET position=%s WHERE " + clause + " AND id=%s", [position, *params, item])


@router.post("/{cid}/reorder-modules", dependencies=[Depends(verify_origin)])
def order_modules(cid: UUID, body: Order, actor=Depends(manager), db=Depends(connection, scope="function")):
    locked(db, actor, cid, body.version); draft(db, actor, cid)
    reorder(db, actor, cid, "course_modules", body.ids)
    result = changed(db, actor, cid); audit(db, actor, "module.reordered", cid)
    return result


@router.post("/{cid}/modules/{mid}/delete", dependencies=[Depends(verify_origin)])
def delete_module(cid: UUID, mid: UUID, body: Version, actor=Depends(manager), db=Depends(connection, scope="function")):
    locked(db, actor, cid, body.version); module_exists(db, actor, cid, mid); draft(db, actor, cid)
    try:db.execute("DELETE FROM course_modules WHERE tenant_id=%s AND course_id=%s AND id=%s", (actor.tenant_id, cid, mid))
    except ForeignKeyViolation:raise HTTPException(409,"Modul memiliki tugas. Arsipkan kursus untuk mempertahankan histori") from None
    ids = [r["id"] for r in db.execute("SELECT id FROM course_modules WHERE tenant_id=%s AND course_id=%s ORDER BY position,id", (actor.tenant_id, cid)).fetchall()]
    reorder(db, actor, cid, "course_modules", ids)
    result = changed(db, actor, cid); audit(db, actor, "module.deleted", mid, "module")
    return result


@router.post("/{cid}/modules/{mid}/lessons", dependencies=[Depends(verify_origin)], status_code=201)
def create_lesson(cid: UUID, mid: UUID, body: Lesson, actor=Depends(manager), db=Depends(connection, scope="function")):
    validate_lesson_content(body,actor)
    locked(db, actor, cid, body.version); module_exists(db, actor, cid, mid)
    count = db.execute("SELECT count(*) AS n FROM course_lessons WHERE tenant_id=%s AND course_id=%s AND module_id=%s", (actor.tenant_id, cid, mid)).fetchone()["n"]
    if count >= 50: raise HTTPException(409, "Batas 50 pelajaran per modul telah tercapai")
    draft(db, actor, cid); lid = uuid4()
    db.execute("INSERT INTO course_lessons(id,tenant_id,course_id,module_id,title,content,resources,position) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
               (lid, actor.tenant_id, cid, mid, body.title, body.content, Jsonb([r.model_dump() for r in body.resources]), count + 1))
    certify_lesson(db,actor,cid,lid)
    result = changed(db, actor, cid); audit(db, actor, "lesson.created", lid, "lesson")
    return {**result, "id": lid}


@router.get("/{cid}/modules/{mid}/lessons/{lid}")
def lesson_detail(cid: UUID, mid: UUID, lid: UUID, actor=Depends(manager), db=Depends(connection, scope="function")):
    row = db.execute("SELECT id,title,content,resources FROM course_lessons WHERE tenant_id=%s AND course_id=%s AND module_id=%s AND id=%s", (actor.tenant_id, cid, mid, lid)).fetchone()
    if not row: raise HTTPException(404, "Pelajaran tidak ditemukan")
    return row


@router.post("/{cid}/modules/{mid}/lessons/{lid}", dependencies=[Depends(verify_origin)])
def edit_lesson(cid: UUID, mid: UUID, lid: UUID, body: Lesson, actor=Depends(manager), db=Depends(connection, scope="function")):
    validate_lesson_content(body,actor)
    locked(db, actor, cid, body.version); draft(db, actor, cid)
    row = db.execute("UPDATE course_lessons SET title=%s,content=%s,resources=%s WHERE tenant_id=%s AND course_id=%s AND module_id=%s AND id=%s RETURNING id",
        (body.title, body.content, Jsonb([r.model_dump() for r in body.resources]), actor.tenant_id, cid, mid, lid)).fetchone()
    if not row: raise HTTPException(404, "Pelajaran tidak ditemukan")
    certify_lesson(db,actor,cid,lid)
    result = changed(db, actor, cid); audit(db, actor, "lesson.updated", lid, "lesson")
    return result


@router.post("/{cid}/modules/{mid}/reorder-lessons", dependencies=[Depends(verify_origin)])
def order_lessons(cid: UUID, mid: UUID, body: Order, actor=Depends(manager), db=Depends(connection, scope="function")):
    locked(db, actor, cid, body.version); module_exists(db, actor, cid, mid); draft(db, actor, cid)
    reorder(db, actor, cid, "course_lessons", body.ids, mid)
    result = changed(db, actor, cid); audit(db, actor, "lesson.reordered", mid, "module")
    return result


@router.post("/{cid}/modules/{mid}/lessons/{lid}/delete", dependencies=[Depends(verify_origin)])
def delete_lesson(cid: UUID, mid: UUID, lid: UUID, body: Version, actor=Depends(manager), db=Depends(connection, scope="function")):
    locked(db, actor, cid, body.version); draft(db, actor, cid)
    try:row = db.execute("DELETE FROM course_lessons WHERE tenant_id=%s AND course_id=%s AND module_id=%s AND id=%s RETURNING id", (actor.tenant_id, cid, mid, lid)).fetchone()
    except ForeignKeyViolation:raise HTTPException(409,"Pelajaran memiliki tugas. Arsipkan kursus untuk mempertahankan histori") from None
    if not row: raise HTTPException(404, "Pelajaran tidak ditemukan")
    ids = [r["id"] for r in db.execute("SELECT id FROM course_lessons WHERE tenant_id=%s AND course_id=%s AND module_id=%s ORDER BY position,id", (actor.tenant_id, cid, mid)).fetchall()]
    reorder(db, actor, cid, "course_lessons", ids, mid)
    result = changed(db, actor, cid); audit(db, actor, "lesson.deleted", lid, "lesson")
    return result


def certify_lesson(db,actor,cid,lid,row=None):
    row=row or db.execute('SELECT revision,content,resources FROM course_lessons WHERE tenant_id=%s AND course_id=%s AND id=%s',(actor.tenant_id,cid,lid)).fetchone()
    token=seal('lesson',(actor.tenant_id,lid,row['revision']),row['content'],row['resources'])
    saved=db.execute('UPDATE course_lessons SET content_attestation=%s WHERE tenant_id=%s AND course_id=%s AND id=%s AND revision=%s AND content=%s AND resources=%s RETURNING id',(token,actor.tenant_id,cid,lid,row['revision'],row['content'],Jsonb(row['resources']))).fetchone()
    if not saved:raise HTTPException(409,'Bukti validasi belum tersimpan. Jadikan kursus draf terlebih dahulu')


class ContentBatch(Version): after: UUID|None=None


@router.post('/{cid}/validate-content',dependencies=[Depends(verify_origin)])
def validate_legacy_content(cid:UUID,body:ContentBatch,actor=Depends(manager),db=Depends(connection,scope='function')):
    current=locked(db,actor,cid,body.version)
    if current['state']!='draft':raise HTTPException(409,'Jadikan kursus draf sebelum memeriksa materi lama')
    rows=db.execute('SELECT id,revision,content,resources,content_attestation FROM course_lessons WHERE tenant_id=%s AND course_id=%s AND (id>%s::uuid OR %s::uuid IS NULL) ORDER BY id LIMIT 51',
                    (actor.tenant_id,cid,body.after,body.after)).fetchall()
    start=time.monotonic();processed=0;last=body.after;ring=cipher()
    for row in rows[:50]:
        if processed and time.monotonic()-start>2:break
        if not valid(row['content_attestation'],'lesson',(actor.tenant_id,row['id'],row['revision']),row['content'],row['resources'],ring):
            try:
                validate_maintenance(row['content'],f'{actor.tenant_id}:{actor.user_id}')
                for item in row['resources']:Resource.model_validate(item)
            except HTTPException as error:
                if error.status_code==429 and processed:break
                raise
            except ValueError:raise HTTPException(409,'Perbaiki materi/tautan pada pelajaran '+str(row['id'])+' sebelum melanjutkan') from None
            certify_lesson(db,actor,cid,row['id'],row)
        processed+=1;last=row['id']
    return {'checked':processed,'next_cursor':str(last) if processed<len(rows) else None,'version':body.version}
