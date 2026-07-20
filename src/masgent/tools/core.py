"""核心工具函数：文件列表、读写、重命名、元数据装饰器"""


def with_metadata(input: schemas.ToolMetadata):
    def decorator(func):
        func._tool_metadata = input
        return func
    return decorator

def list_files() -> dict:
    runs_dir = str(config.get_runs_dir())
    file_list = []
    base_dir = Path(runs_dir)
    for item in base_dir.rglob('*'):
        if item.is_file():
            file_list.append(os.path.join(runs_dir, str(item.relative_to(base_dir))))
    return {
        'status': 'success',
        'message': f'Found {len(file_list)} files in the current session runs directory.',
        'files': file_list,
    }

def read_file(name: str) -> dict:
    runs_dir = str(config.get_runs_dir())
    base_dir = Path(runs_dir)
    try:
        with open(base_dir / name, "r") as f:
            content = f.read()
        return {'status': 'success', 'message': f'File {name} read successfully.', 'content': content}
    except Exception as e:
        return {'status': 'error', 'message': f'An error occurred while reading file {name}: {e}'}

def rename_file(name: str, new_name: str) -> dict:
    runs_dir = str(config.get_runs_dir())
    base_dir = Path(runs_dir)
    try:
        new_path = base_dir / new_name
        if not new_path.resolve().is_relative_to(base_dir.resolve()):
            return {'status': 'error', 'message': f'Renaming to {new_name} would move the file outside the session runs directory, which is not allowed.'}
        os.makedirs(new_path.parent, exist_ok=True)
        shutil.copy2(base_dir / name, new_path)
        return {'status': 'success', 'message': f'File {name} renamed to {new_name} successfully.'}
    except Exception as e:
        return {'status': 'error', 'message': f'An error occurred while renaming file {name} to {new_name}: {e}'}
import os
import shutil
from pathlib import Path
from masgent.models import schemas
from masgent._config import config

_DOCS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "docs"
_SAFE_BASE = _DOCS_DIR.resolve()
@with_metadata(schemas.ToolMetadata(
    name='Read Documentation',
    description='Read documentation or guide files from the MASgent docs/ directory. Use this when the user asks about how the system works, architecture, adding calculators, task lifecycle, file lock, recovery, or user guides. Accepts doc_path relative to docs/ root.',
    requires=['doc_path'],
    optional=[],
    defaults={},
    prereqs=[],
))
def read_doc_file(doc_path: str) -> dict:
    '''
    Read documentation files from the MASgent docs/ directory.
    doc_path should be relative to the docs/ root, e.g., "developer_guide/architecture.md"
    '''
    try:
        target = (_DOCS_DIR / doc_path).resolve()
        if not str(target).startswith(str(_SAFE_BASE)):
            return {'status': 'error', 'message': 'Access denied: path is outside the docs/ directory.'}
        if not target.is_file():
            return {'status': 'error', 'message': f'Documentation file not found: {doc_path}'}
        content = target.read_text(encoding="utf-8")
        return {
            'status': 'success',
            'message': f'Documentation file {doc_path} read successfully.',
            'content': content,
            'file': doc_path,
        }
    except Exception as e:
        return {'status': 'error', 'message': f'Failed to read documentation file {doc_path}: {e}'}
