"""Small explicit persistence helpers; JSON is canonical and reproducible."""
import hashlib
import json
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + '\n', encoding='utf-8')


def verify_run(directory: Path) -> None:
    """Detect changed/missing/added files against a local manifest (not a signed attestation)."""
    manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
    actual = {str(p.relative_to(directory)) for p in directory.rglob('*') if p.is_file() and p.relative_to(directory).as_posix() != 'manifest.json'}
    if actual != set(manifest['files']):
        raise ValueError('Run file set differs from manifest')
    for name, expected in manifest['files'].items():
        if digest(directory / name) != expected:
            raise ValueError(f'Run integrity failure: {name}')
