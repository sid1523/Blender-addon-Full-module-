import json
import glob
import os
import pytest

from canvas3d.utils.spec_validation import validate_scene_spec


def _list_corpus_specs():
    return sorted(glob.glob(os.path.join(os.path.dirname(__file__), "corpus", "*.json")))


@pytest.mark.parametrize("spec_path", _list_corpus_specs() or ["__NO_SPECS__"])
def test_corpus_specs_validate_and_optionally_traverse(spec_path):
    if spec_path == "__NO_SPECS__":
        pytest.skip("No corpus specs found in tests/corpus/. Add JSON specs to run this test.")

    with open(spec_path, "r", encoding="utf-8") as f:
        try:
            spec = json.load(f)
        except Exception as ex:
            pytest.fail(f"Failed to parse JSON for {spec_path}: {ex}")

    ok, issues = validate_scene_spec(spec, expect_version="1.0.0")
    if not ok:
        readable = "; ".join(f"{i.path}: {i.message} ({i.code})" for i in issues[:10])
        pytest.fail(f"Spec failed validation ({spec_path}): {readable}")

    # Traversability checks removed from MVP; schema validation is the responsibility of the validator.