import json
from pathlib import Path

def generate_manifest(base_dir: Path, output_path: Path):
    manifest = {}
    
    if not base_dir.exists():
        raise FileNotFoundError(f"Directory not found: {base_dir}")
        
    for item in base_dir.iterdir():
        if item.is_dir() and not item.name.startswith('.') and item.name != '__pycache__':
            files = []
            for filepath in item.rglob('*'):
                # Check if any parent dir is hidden
                is_hidden = any(part.startswith('.') for part in filepath.relative_to(base_dir).parts)
                if not is_hidden and filepath.is_file() and filepath.name != 'manifest.json':
                    # Calculate path relative to the repo root (~/)
                    rel_path = filepath.relative_to(base_dir.parent)
                    files.append({
                        "name": filepath.name,
                        "path": str(rel_path),
                        "type": filepath.suffix.lower()
                    })
            if files:
                manifest[item.name] = files
                
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(output_path, 'w') as f:
            json.dump(manifest, f, indent=2)
    except OSError as e:
        print(f"Error writing to {output_path}: {e}")

if __name__ == '__main__':
    pipelines_dir = Path(__file__).parent
    manifest_path = pipelines_dir / 'manifest.json'
    generate_manifest(pipelines_dir, manifest_path)
    print(f"Manifest written to {manifest_path}")
