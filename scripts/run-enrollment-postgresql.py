"""Approved local lab only: new PG17 cluster, Unix socket only, no live DB.

Preserves its directory/evidence. Stops ONLY its own server in finally. Does not
change Homebrew services, launchd, existing clusters, Lima or Docker.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from urllib.parse import quote

ROOT=Path(__file__).resolve().parents[1]
BIN=Path('/opt/homebrew/opt/postgresql@17/bin')


def main():
    os.umask(0o077)
    folder=Path(tempfile.mkdtemp(prefix='mm-enroll-pg-',dir='/private/tmp'))
    data=folder/'data';sock=folder/'socket';sock.mkdir(mode=0o700)
    started=False
    report={'directory':str(folder),'tcp_listener':False,'synthetic_only':True}
    def run(args,**kw):
        return subprocess.run([str(x) for x in args],check=True,capture_output=True,text=True,**kw)
    try:
        run([BIN/'initdb','-D',data,'--auth-local=trust','--auth-host=reject','--no-locale','--encoding=UTF8'])
        run([BIN/'pg_ctl','-D',data,'-l',folder/'server.log','-o',f"-c listen_addresses='' -c unix_socket_directories='{sock}' -c unix_socket_permissions=0700 -c shared_buffers=32MB -c max_connections=24",'-w','start'])
        started=True
        import psycopg
        with psycopg.connect(host=str(sock),dbname='postgres',autocommit=True) as admin:
            assert admin.execute('SHOW listen_addresses').fetchone()[0]==''
            report['postgresql_version']=admin.execute('SHOW server_version').fetchone()[0]
            admin.execute('CREATE ROLE mm_enrollment_test LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION')
            admin.execute('CREATE DATABASE mm_enrollment_test OWNER mm_enrollment_test')
        url='postgresql+psycopg://mm_enrollment_test@/mm_enrollment_test?host='+quote(str(sock),safe='')
        env={**os.environ,'DATABASE_URL':url,'MM_ENROLLMENT_TEST_URL':url,'PYTHONPATH':str(ROOT)+':'+str(ROOT/'tests')}
        run([sys.executable,'-m','alembic','upgrade','head'],cwd=ROOT,env=env)
        run([sys.executable,'-m','alembic','upgrade','head'],cwd=ROOT,env=env)
        report['migration_second_upgrade']='PASS'
        with psycopg.connect(host=str(sock),dbname='mm_enrollment_test',user='mm_enrollment_test') as db:
            report['migration_revision']=db.execute('SELECT version_num FROM alembic_version').fetchone()[0]
            assert report['migration_revision']=='032'
        result=subprocess.run([sys.executable,'-W','ignore::ResourceWarning','-m','unittest','-v','test_enrollment_postgresql'],cwd=ROOT,env=env,capture_output=True,text=True)
        # Tests report only synthetic IDs and assertion labels; never DB contents.
        (folder/'tests.log').write_text(result.stdout+result.stderr)
        report['test_exit_code']=result.returncode
        report['status']='PASS' if result.returncode==0 else 'FAIL'
        report['tests']=[line for line in result.stderr.splitlines() if line.startswith('test_')]
    except Exception as exc:
        report.update(status='BLOCKED',failure_type=type(exc).__name__)
        if isinstance(exc,subprocess.CalledProcessError):
            # Keep diagnostics private; do not stream potentially sensitive SQL.
            (folder/'failure.log').write_text((exc.stdout or '')+(exc.stderr or ''))
    finally:
        if started:
            try:run([BIN/'pg_ctl','-D',data,'-m','fast','-w','stop']);report['own_server_stopped']=True
            except Exception:report['own_server_stopped']=False
        (folder/'result.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2))
    return 0 if report.get('status')=='PASS' else 1


if __name__=='__main__':sys.exit(main())
