"""Build a deterministic, secret-free public-test source artifact."""
from pathlib import Path
import hashlib
import zipfile

root = Path(__file__).resolve().parents[1]
output = root / "release" / "mikromagic-build21-public-test.zip"
files = [root / name for name in (
    "compose.hostinger-public-test.yaml", "Dockerfile.api", "Dockerfile.web", "Dockerfile.hub",
    ".dockerignore", "alembic.ini", "requirements.txt", "requirements.hub.txt", "package.json",
    "package-lock.json", "index.html", "vite.config.mjs", "docker/Caddyfile",
    "docker/api-entrypoint.sh",
)]
_FORBIDDEN_PARTS = {"secrets", "routeros-secrets", "node_modules", "dist", ".venv", ".runtime"}
for folder, suffixes in (
    ("backend", {".py"}),
    ("src", {".js", ".jsx", ".mjs", ".css"}),
    ("public", {".png", ".svg", ".webp", ".jpg", ".jpeg", ".ico"}),
    ("owner-web", {".ts", ".tsx", ".css", ".json", ".html"}),
):
    files.extend(
        path for path in (root / folder).rglob("*")
        if path.is_file()
        and path.suffix.lower() in suffixes
        and not any(part in _FORBIDDEN_PARTS for part in path.parts)
    )
files = sorted(set(files))
for path in files:
    if not path.is_file() or path.is_symlink():
        raise RuntimeError(f"Missing or symlinked artifact input: {path}")
    if any(part in {"secrets", "routeros-secrets", "node_modules", "dist", ".venv", ".runtime"} for part in path.parts):
        raise RuntimeError(f"Forbidden artifact input: {path}")

output.parent.mkdir(exist_ok=True)
with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
    for path in files:
        relative = path.relative_to(root)
        info = zipfile.ZipInfo(str(relative), date_time=(2026, 10, 10, 0, 0, 0))
        info.external_attr = (0o755 if relative == Path("docker/api-entrypoint.sh") else 0o644) << 16
        info.compress_type = zipfile.ZIP_DEFLATED
        archive.writestr(info, path.read_bytes())

digest = hashlib.sha256(output.read_bytes()).hexdigest()
print(f"artifact={output}")
print(f"sha256={digest}")
print(f"files={len(files)}")
