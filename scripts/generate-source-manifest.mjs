import { createHash } from 'node:crypto';
import { readdir, readFile, writeFile } from 'node:fs/promises';
import { join, relative, sep } from 'node:path';

const root = process.cwd();
const output = '.corrective-source-manifest.txt';
const excludedDirectories = new Set(['.git', '.venv', 'node_modules', 'dist', '__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache', 'secrets', 'routeros-secrets']);
const excludedFiles = new Set([output, '.env', '.DS_Store', '.coverage']);
const files = [];

async function walk(directory) {
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    if (entry.isSymbolicLink()) throw new Error(`Symlink is not permitted in source manifest: ${relative(root, join(directory, entry.name))}`);
    if (entry.isDirectory()) {
      if (!excludedDirectories.has(entry.name)) await walk(join(directory, entry.name));
      continue;
    }
    if (!entry.isFile() || excludedFiles.has(entry.name) || entry.name.endsWith('.pyc')) continue;
    const path = relative(root, join(directory, entry.name)).split(sep).join('/');
    files.push(path);
  }
}

await walk(root);
files.sort((a, b) => Buffer.compare(Buffer.from(a, 'utf8'), Buffer.from(b, 'utf8')));
const records = [];
for (const path of files) {
  const digest = createHash('sha256').update(await readFile(join(root, path))).digest('hex');
  records.push(`${digest}  ${path}\n`);
}
const manifest = records.join('');
const digest = createHash('sha256').update(manifest, 'utf8').digest('hex');

let added = [], changed = [], deleted = [];
try {
  const previous = (await readFile(join(root, output), 'utf8')).trimEnd().split('\n').filter(Boolean);
  const old = new Map(previous.map(line => [line.slice(66), line.slice(0, 64)]));
  const current = new Map(records.map(line => [line.slice(66).trimEnd(), line.slice(0, 64)]));
  added = [...current.keys()].filter(path => !old.has(path));
  changed = [...current.keys()].filter(path => old.has(path) && current.get(path) !== old.get(path));
  deleted = [...old.keys()].filter(path => !current.has(path));
  console.log(`Previous manifest records: ${old.size}`);
  console.log(`Added: ${added.length ? added.join(', ') : 'none'}`);
  console.log(`Modified: ${changed.length ? changed.join(', ') : 'none'}`);
  console.log(`Deleted: ${deleted.length ? deleted.join(', ') : 'none'}`);
} catch (error) {
  if (error.code !== 'ENOENT') throw error;
}

await writeFile(join(root, output), manifest, { encoding: 'utf8', mode: 0o600 });
console.log(`Manifest records: ${records.length}`);
console.log(`Manifest SHA-256: ${digest}`);
