"""Offline operator-only provisioning into an explicitly selected dev database.

Run python -m app.provision; never pass passwords through command arguments.
Not mounted as an API. Uses a migration owner connection, never the API role.
"""
from getpass import getpass
import os
from uuid import uuid4

import psycopg
from pwdlib import PasswordHash


def main():
    if os.environ.get("APP_ENV") != "local":
        raise SystemExit("Provisioning ini hanya untuk database pengembangan lokal")
    email = input("Email akun sintetis: ").strip().lower()
    slug = input("Slug organisasi baru: ").strip()
    name = input("Nama organisasi: ").strip()
    password = getpass("Kata sandi baru (minimal 15 karakter): ")
    if len(password) < 15 or len(password) > 1024 or not email or not slug or not name:
        raise SystemExit("Input tidak valid")
    if password != getpass("Ulangi kata sandi: "):
        raise SystemExit("Kata sandi berbeda")
    user_id, tenant_id = uuid4(), uuid4()
    with psycopg.connect(os.environ["MIGRATION_DATABASE_URL"]) as db:
        db.execute("INSERT INTO users(id,email,password_hash) VALUES (%s,%s,%s)",
                   (user_id, email, PasswordHash.recommended().hash(password)))
        db.execute("INSERT INTO tenants(id,slug,name) VALUES (%s,%s,%s)",
                   (tenant_id, slug, name))
        db.execute("INSERT INTO memberships(id,tenant_id,user_id,role) VALUES (%s,%s,%s,'admin')",
                   (uuid4(), tenant_id, user_id))
    print("Akun pengembangan dibuat. Tenant:", tenant_id)


if __name__ == "__main__":
    main()
