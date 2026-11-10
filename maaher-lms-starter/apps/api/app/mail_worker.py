"""Explicit mail-only command. Never run by API startup or migrations.

Uses MAIL_DATABASE_URL with maaher_mailer membership, not the API/owner role.
No real message is sent by the automated tests.
"""
from email.message import EmailMessage
import os
import smtplib
import ssl
from urllib.parse import urlsplit
from cryptography.fernet import InvalidToken

import psycopg
from psycopg.rows import dict_row

from .auth_support import cipher


def validate_mail_role(db):
    role = db.execute("""SELECT r.rolsuper OR r.rolbypassrls OR
                         NOT pg_has_role(current_user,'maaher_mailer','MEMBER') OR
                         pg_has_role(current_user,'maaher_runtime','MEMBER') AS unsafe
                         FROM pg_roles r WHERE r.rolname=current_user""").fetchone()
    if role["unsafe"]:
        raise RuntimeError("MAIL_DATABASE_URL harus memakai role khusus email tanpa hak API/owner")
    if db.execute("""SELECT EXISTS(SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                     WHERE n.nspname='public' AND c.relkind='r'
                       AND pg_has_role(current_user,c.relowner,'USAGE')) AS owns""").fetchone()["owns"]:
        raise RuntimeError("Role email tidak boleh memiliki tabel aplikasi")


def deliver_one(db, send):
    """At-least-once delivery: a crash after SMTP accept may send a duplicate.

    Tokens remain one-use. SKIP LOCKED supports more than one worker safely.
    Failed sends leave encrypted payload for retry; never log message/token.
    """
    validate_mail_role(db)
    encryption = cipher()  # Configuration errors are not row corruption.
    origin = os.environ["APP_ORIGIN"].rstrip("/")
    parsed = urlsplit(origin)
    if parsed.scheme != "https" or not parsed.netloc or parsed.path or parsed.query or parsed.fragment or parsed.username:
        raise ValueError("APP_ORIGIN email harus berupa origin HTTPS")
    sender = os.environ["SMTP_FROM"]
    db.execute("""UPDATE auth_mail_outbox SET encrypted_token=NULL,recipient='',dead_at=coalesce(dead_at,now()),error_code='expired'
                  WHERE sent_at IS NULL AND expires_at<=now() AND encrypted_token IS NOT NULL""")
    row = db.execute("""SELECT * FROM auth_mail_outbox WHERE sent_at IS NULL AND dead_at IS NULL
                        AND encrypted_token IS NOT NULL AND attempts<5 AND expires_at>now() AND next_attempt_at<=now()
                        ORDER BY expires_at,id FOR UPDATE SKIP LOCKED LIMIT 1""").fetchone()
    if not row:
        return False
    try:
        token = encryption.decrypt(row["encrypted_token"].encode()).decode()
        if not 32 <= len(token) <= 128 or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in token):
            raise ValueError('Invalid token format')
        mode = "invitation" if row["kind"] == "invitation" else "password-reset"
        message = EmailMessage()
        message["From"] = sender
        message["To"] = row["recipient"]
        message["Subject"] = "Undangan Maaher LMS" if mode == "invitation" else "Pemulihan kata sandi Maaher LMS"
        message.set_content(f"Tautan berlaku maksimal satu jam sejak diminta:\n{origin}/auth#{mode}={token}\n"
                            "Tautan hanya dapat digunakan sekali. Abaikan jika Anda tidak meminta ini.")
    except (InvalidToken,UnicodeError,ValueError,TypeError):
        # Persist the quarantine in this message's transaction and continue.
        # No plaintext recipient/token or exception body is retained.
        db.execute("""UPDATE auth_mail_outbox SET attempts=attempts+1,dead_at=now(),error_code='invalid_payload',
                      encrypted_token=NULL,recipient='' WHERE id=%s""",(row['id'],))
        return True
    try:
        rejected = send(message)
        if rejected:
            raise smtplib.SMTPRecipientsRefused(rejected)
    except (OSError, smtplib.SMTPException):
        db.execute("""UPDATE auth_mail_outbox SET attempts=attempts+1,next_attempt_at=now()+interval '10 minutes',
          error_code='smtp_failed',dead_at=CASE WHEN attempts>=4 THEN now() ELSE NULL END,
          encrypted_token=CASE WHEN attempts>=4 THEN NULL ELSE encrypted_token END,
          recipient=CASE WHEN attempts>=4 THEN '' ELSE recipient END WHERE id=%s""", (row["id"],))
        return True
    db.execute("""UPDATE auth_mail_outbox SET sent_at=now(),encrypted_token=NULL,recipient='',
                  attempts=attempts+1,error_code=NULL WHERE id=%s""",(row['id'],))
    return True



def main():
    # Dedicated process and role; TLS verification cannot be disabled.
    with psycopg.connect(os.environ["MAIL_DATABASE_URL"], row_factory=dict_row, autocommit=True) as db:
        validate_mail_role(db)
        with smtplib.SMTP_SSL(os.environ["SMTP_HOST"], int(os.environ.get("SMTP_PORT", "465")),
                              context=ssl.create_default_context(), timeout=15) as smtp:
            smtp.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
            # Bound each invocation; scheduler controls retries and queue monitoring.
            for _ in range(100):
                with db.transaction():
                    if not deliver_one(db, smtp.send_message):
                        break


if __name__ == "__main__":
    main()
