"""Tests for methodology provenance metadata."""

from whatnut import __version__
from whatnut.provenance import (
    OPTIQAL_REFERENCE_COMMIT,
    WHATNUT_MODEL_VERSION,
    methodology_provenance,
)


def test_provenance_is_pinned_and_explicit():
    provenance = methodology_provenance()

    assert provenance["whatnut_model_version"] == WHATNUT_MODEL_VERSION
    assert __version__ == WHATNUT_MODEL_VERSION
    assert provenance["optiqal_reference_commit"] == OPTIQAL_REFERENCE_COMMIT
    assert len(OPTIQAL_REFERENCE_COMMIT) == 40
    assert provenance["runtime_dependency"] is False
    assert provenance["adopted"]
    assert provenance["whatnut_extensions"]
    assert "not represented by this commit pin" in provenance["optiqal_reference_scope"]
    assert provenance["deliberate_differences"]
