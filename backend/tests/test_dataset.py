"""The committed dataset must be exactly what the generator produces, and the
generator's self-check (the dataset matches its own ground truth) must pass."""
import importlib.util
import json
import sys

from pramana.config import REPO_ROOT

GEN_DIR = REPO_ROOT / "dataset"


def load_generator():
    sys.path.insert(0, str(GEN_DIR))
    spec = importlib.util.spec_from_file_location("pramana_dataset_generate", GEN_DIR / "generate.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_generator_is_deterministic_and_matches_the_committed_dataset(tmp_path):
    gen = load_generator()
    report = gen.build(tmp_path / "a", gen.DEFAULT_SEED)
    assert report["problems"] == []
    fresh = json.loads((tmp_path / "a" / "manifest.json").read_text(encoding="utf-8"))
    committed = json.loads((GEN_DIR / "tri_city_v1" / "manifest.json").read_text(encoding="utf-8"))
    assert fresh["files"] == committed["files"]


def test_spec_scale_targets(tmp_path):
    committed = json.loads((GEN_DIR / "tri_city_v1" / "manifest.json").read_text(encoding="utf-8"))
    s = committed["stats"]
    assert s["cases"] == 30 and s["narratives"] == 40 and s["hindi_or_hinglish_narratives"] >= 5
    assert s["bank_branches"] == 3 and s["bank_officials"] == 6
    assert 1300 <= s["transactions"] <= 1700 and 170 <= s["accounts"] <= 240
