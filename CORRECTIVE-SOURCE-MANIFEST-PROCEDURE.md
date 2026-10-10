# Corrective source manifest procedure

Run from the root of this corrective working copy:

```sh
node scripts/generate-source-manifest.mjs
shasum -a 256 .corrective-source-manifest.txt
```

The generator walks regular files recursively; rejects symlinks; uses UTF-8
relative paths with `/`; sorts paths by UTF-8 byte order; and writes one record
per file as `<lowercase SHA-256><two spaces><relative path><LF>`. The manifest
is UTF-8 with a final LF. The SHA-256 reported by the generator and by
`shasum` is the digest of the complete manifest bytes.

Excluded directory names are `.git`, `.venv`, `node_modules`, `dist`,
`__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `secrets`, and
`routeros-secrets`. Excluded files are `.corrective-source-manifest.txt`,
`.env`, `.DS_Store`, `.coverage`, and files ending in `.pyc`. All other regular
files, including this procedure and the generator, are covered by the manifest.

This is a new post-correction identity baseline. It does not claim to reproduce
or match the undocumented historical manifest digest.
