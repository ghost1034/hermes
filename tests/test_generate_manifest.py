import json
from pathlib import Path
import sys
import pytest

# Add parent dir to path so we can import pipelines module
sys.path.insert(0, str(Path(__file__).parent.parent))
from pipelines.generate_manifest import generate_manifest

def test_generate_manifest(tmp_path):
    pipelines_dir = tmp_path / "pipelines"
    pipelines_dir.mkdir()
    b2b_lead_dir = pipelines_dir / "b2b_lead"
    b2b_lead_dir.mkdir()
    
    # Standard file
    (b2b_lead_dir / "output.csv").write_text("a,b\n1,2")
    
    # Should ignore hidden files
    (b2b_lead_dir / ".hidden").write_text("hidden")
    
    # Should ignore manifest.json
    (b2b_lead_dir / "manifest.json").write_text("{}")

    manifest_path = pipelines_dir / "manifest.json"
    generate_manifest(pipelines_dir, manifest_path)
    
    assert manifest_path.exists()
    data = json.loads(manifest_path.read_text())
    
    assert "b2b_lead" in data
    assert len(data["b2b_lead"]) == 1
    
    file_info = data["b2b_lead"][0]
    assert file_info["name"] == "output.csv"
    assert file_info["path"] == "pipelines/b2b_lead/output.csv"

def test_generate_manifest_missing_dir(tmp_path):
    pipelines_dir = tmp_path / "pipelines"
    manifest_path = pipelines_dir / "manifest.json"
    
    with pytest.raises(FileNotFoundError):
        generate_manifest(pipelines_dir, manifest_path)
