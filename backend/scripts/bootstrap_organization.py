"""Create an organization and invite its first administrator (run by an operator, not over HTTP).

    .venv/bin/python -m backend.scripts.bootstrap_organization --name "Acme Research" --admin-email you@gmail.com

The invitation is bound to the email: it is accepted by signing in with Google using that verified
address. Nothing secret is printed.
"""
import argparse
import re
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import psycopg
from fdi.db.config import dsn


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', required=True)
    parser.add_argument('--admin-email', required=True)
    parser.add_argument('--expires-in-days', type=int, default=7)
    args = parser.parse_args()
    email = args.admin_email.strip().lower()
    if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
        raise SystemExit('Invalid email address')
    org = uuid4()
    with psycopg.connect(dsn(admin=True)) as conn:
        conn.execute('INSERT INTO fdi.organizations (id, name) VALUES (%s,%s)', (org, args.name.strip()))
        inv = conn.execute('''INSERT INTO fdi.invitations (organization_id, email, role, expires_at)
            VALUES (%s,%s,'admin',%s) RETURNING id''',
            (org, email, datetime.now(timezone.utc) + timedelta(days=args.expires_in_days))).fetchone()[0]
    print(f'Organization {org} created; admin invitation {inv} for {email} '
          f'(expires in {args.expires_in_days} days; accept by signing in with that Google account)')


if __name__ == '__main__':
    main()
