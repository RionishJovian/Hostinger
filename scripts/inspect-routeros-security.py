"""Future approved session: dedicated Monitoring credential, GET-only metadata.

Does not bootstrap a router or obtain credentials. Not executed during software
development. Emits only sanitized readiness, never raw RouterOS responses.
"""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.routeros_adapter import load_routeros_monitoring_credential,RouterOSClient,RouterOSError
from backend.bootstrap_security import inspect_security_prerequisites,BootstrapSecurityError


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--router-id',required=True)
    parser.add_argument('--approved-hardware-inspection',action='store_true',required=True)
    args=parser.parse_args()
    try:
        credential=load_routeros_monitoring_credential(args.router_id)
        with RouterOSClient(credential) as client:result=inspect_security_prerequisites(client,args.router_id)
    except (RouterOSError,BootstrapSecurityError) as error:
        result={'status':'BLOCKED','code':getattr(error,'code','security_prerequisite_failed'),'connection_verified':False,'router_writes_enabled':False}
    print(json.dumps(result,indent=2))
