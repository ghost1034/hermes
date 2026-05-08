import os
import json
from pathlib import Path

def generate_manifest(base_dir: Path, output_path: Path):
    manifest = {}
    
    if not base_dir.exists():
        return
        
    for item in base_dir.iterdir():
        if item.is_dir() and not item.name.startswith('.'):
            files = []
            for filepath in item.rglob('*'):
                if filepath.is_file() and not filepath.name.startswith('.') and filepath.name != 'manifest.json':
                    # Calculate path relative to the repo root (~/)
                    rel_path = filepath.relative_to(base_dir.parent)
                    files.append({
                        "name": filepath.name,
                        "path": str(rel_path),
                        "type": filepath.suffix.lower()
                    })
            if files:
                manifest[item.name] = files
                
    with open(output_path, 'w') as f:
        json.dump(manifest, f, indent=2)

if __name__ == '__main__':
    pipelines_dir = Path(__file__).parent
    manifest_path = pipelines_dir / 'manifest.json'
    generate_manifest(pipelines_dir, manifest_path)
    print(f"Manifest written to {manifest_path}")
