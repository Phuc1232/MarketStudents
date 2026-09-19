import os
import sys
from pathlib import Path

# Ensure UTF-8 output encoding on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def scan_project(root_dir="."):
    root = Path(root_dir).resolve()
    stats = {}
    total_lines = 0
    total_files = 0

    ignore_dirs = {'.git', '.venv', '__pycache__', '.vscode', 'node_modules', '.idea', 'alembic'}

    for path in root.rglob('*'):
        if any(ignored in path.parts for ignored in ignore_dirs):
            continue
        if path.is_file():
            ext = path.suffix.lower() or '(no ext)'
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = sum(1 for _ in f)
                stats[ext] = stats.get(ext, {'count': 0, 'lines': 0})
                stats[ext]['count'] += 1
                stats[ext]['lines'] += lines
                total_lines += lines
                total_files += 1
            except Exception:
                pass

    print("=" * 60)
    print(f"CODEBASE METRICS: {root.name}")
    print("=" * 60)
    print(f"Total Files : {total_files}")
    print(f"Total Lines : {total_lines}")
    print("-" * 60)
    print(f"{'Extension':<15} {'Files':<10} {'Lines of Code':<15}")
    print("-" * 60)
    for ext, data in sorted(stats.items(), key=lambda x: x[1]['lines'], reverse=True):
        print(f"{ext:<15} {data['count']:<10} {data['lines']:<15}")
    print("=" * 60)

if __name__ == "__main__":
    scan_project()
