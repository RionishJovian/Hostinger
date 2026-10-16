"""Durable Safe Change scheduler process."""
import os,time
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .routeros_lock import configure_routeros_lock
from .safe_changes import process_due_changes

def main():
 url=os.environ.get('DATABASE_URL')
 if not url:raise RuntimeError('DATABASE_URL is required')
 engine=create_engine(url,pool_pre_ping=True);configure_routeros_lock(engine)
 factory=sessionmaker(engine,expire_on_commit=False);interval=max(5,min(60,int(os.environ.get('MIKROMAGIC_SAFE_CHANGE_POLL_SECONDS','10'))))
 while True:
  try:process_due_changes(factory)
  except Exception:print('Safe Change scheduler pass failed; retrying without exposing details',flush=True)
  time.sleep(interval)
if __name__=='__main__':main()
