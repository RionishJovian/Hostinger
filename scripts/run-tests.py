#!/usr/bin/env python3
"""Run every tests/test_*.py module in its own process, several at a time.

Same tests as `python -m unittest discover -s tests -p 'test_*.py'`, but each
module gets a fresh interpreter and environment, so modules cannot leak state
into each other. Module durations are remembered in .git so the slowest start
first. Exit status is non-zero if any module fails.

  .venv/bin/python scripts/run-tests.py            # all modules
  .venv/bin/python scripts/run-tests.py -j 4       # four workers
  .venv/bin/python scripts/run-tests.py test_hubs  # selected modules
"""
import argparse,json,os,re,subprocess,sys,time
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
TESTS=ROOT/'tests'

def timings_file():
 try:git=subprocess.run(['git','rev-parse','--git-dir'],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip()
 except (OSError,subprocess.CalledProcessError):return None
 return (ROOT/git/'mikromagic-test-timings.json').resolve()

def run(module):
 env=os.environ|{'PYTHONPATH':os.pathsep.join([str(TESTS),str(ROOT)]),'PYTHONWARNINGS':'ignore'}
 start=time.monotonic()
 done=subprocess.run([sys.executable,'-m','unittest',module],cwd=ROOT,env=env,capture_output=True,text=True)
 output=done.stderr+done.stdout
 ran=re.search(r'^Ran (\d+) tests?',output,re.M);skipped=re.search(r'skipped=(\d+)',output)
 return module,done.returncode,int(ran.group(1)) if ran else 0,int(skipped.group(1)) if skipped else 0,time.monotonic()-start,output

def resolve_module(name):
 candidate=Path(name)
 if candidate.suffix=='.py':
  for path in (candidate if candidate.is_absolute() else ROOT/candidate, TESTS/candidate.name):
   if path.is_file():
    return path.stem
 stem=Path(name).stem
 if (TESTS/f'{stem}.py').is_file():
  return stem
 alt=f'test_{stem}'
 if (TESTS/f'{alt}.py').is_file():
  return alt
 raise SystemExit(f'unknown test module: {name}')

def main():
 parser=argparse.ArgumentParser()
 parser.add_argument('-j','--jobs',type=int,default=os.cpu_count() or 4)
 parser.add_argument('modules',nargs='*',help='optional module names or paths (default: all test_*.py)')
 args=parser.parse_args()
 modules=[resolve_module(m) for m in args.modules] if args.modules else sorted(p.stem for p in TESTS.glob('test_*.py'))
 path=timings_file()
 try:timings=json.loads(path.read_text()) if path else {}
 except (OSError,ValueError):timings={}
 modules.sort(key=lambda m:-timings.get(m,(TESTS/f'{m}.py').stat().st_size/1000))
 start=time.monotonic();total=skipped=0;failed=[]
 with ThreadPoolExecutor(max_workers=max(1,args.jobs)) as pool:
  for future in as_completed([pool.submit(run,m) for m in modules]):
   module,code,ran,skip,seconds,output=future.result()
   total+=ran;skipped+=skip;timings[module]=round(seconds,2)
   if code:
    failed.append(module);print(f'FAIL {module} ({seconds:.1f}s)\n{output}',flush=True)
 if path:
  try:path.write_text(json.dumps(timings,indent=0,sort_keys=True))
  except OSError:pass
 print('-'*70)
 print(f'Ran {total} tests in {len(modules)} modules in {time.monotonic()-start:.1f}s with {args.jobs} workers')
 if failed:
  print(f'FAILED modules: {" ".join(sorted(failed))}');return 1
 print(f'OK (skipped={skipped})' if skipped else 'OK');return 0

if __name__=='__main__':sys.exit(main())
