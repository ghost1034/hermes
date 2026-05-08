import os
import json
import pytest
from pathlib import Path
import sys

# Add parent dir to path so we can import pipelines module if needed
sys.path.insert(0, str(Path(__file__).parent.parent))
from pipelines.generate_manifest import generate_manifest

def test_generate_manifest(tmp_path):
    pipelines_dir = tmp_path / "pipelines"
    pipelines_dir.mkdir()
    (pipelines_dir / "b2b_lead").mkdir()
    (pipelines_dir / "b2b_lead" / "output.csv").write_text("a,b\n1,2")
    
    # Should ignore hidden files/dirs
    (pipelines_dir / "b2b_lead" / ".hidden").write_text("hidden")
    
    manifest_path = pipelines_dir / "manifest.json"
    generate_manifest(pipelines_dir, manifest_path)
    
    assert manifest_path.exists()
    data = json.loads(manifest_path.read_text())
    assert "b2b_lead" in data
    assert len(data["b2b_lead"]) == 1
    assert data["b2b_lead"][0]["name"] == "output.csv"
    assert data["b2b_lead"][0]["path"] == "pipelines/b2b_lead/output.csv"
