"""Tests for evidence/sources module.

TDD: Define expected structure and validation for primary sources.
"""

import pytest
from whatnut.evidence import SOURCES, Source, get_source, validate_sources


class TestSourceStructure:
    """Each source must have required fields with valid data."""

    def test_sources_not_empty(self):
        assert len(SOURCES) > 0

    def test_each_source_has_required_fields(self):
        required_fields = ["id", "citation", "url", "study_type", "key_finding"]
        for source in SOURCES:
            for field in required_fields:
                assert hasattr(source, field), f"Source {source.id} missing {field}"

    def test_each_source_has_valid_url(self):
        for source in SOURCES:
            assert source.url.startswith("http"), f"Invalid URL for {source.id}"

    def test_each_source_has_doi_or_database(self):
        """Must have DOI (for papers) or database reference (USDA, etc)."""
        for source in SOURCES:
            has_doi = source.doi is not None
            has_database = source.database is not None
            assert has_doi or has_database, f"Source {source.id} needs DOI or database"


class TestSourceContent:
    """Validate specific sources we depend on."""

    def test_aune_2016_meta_analysis_exists(self):
        source = get_source("aune2016")
        assert source is not None
        assert "BMC Medicine" in source.citation
        assert source.study_type == "meta_analysis"

    def test_aune_2016_has_effect_size(self):
        source = get_source("aune2016")
        assert source.effect_size is not None
        assert source.effect_size.metric == "relative_risk"
        # RR 0.78 for all-cause mortality
        assert 0.70 < source.effect_size.point_estimate < 0.85
        assert source.effect_size.ci_lower is not None
        assert source.effect_size.ci_upper is not None

    def test_bao_2013_nejm_exists(self):
        source = get_source("bao2013")
        assert source is not None
        assert "N Engl J Med" in source.citation or "NEJM" in source.citation
        assert source.study_type == "cohort"

    def test_usda_fooddata_exists(self):
        source = get_source("usda_fdc")
        assert source is not None
        assert source.database == "USDA FoodData Central"


class TestSourceValidation:
    """Validate all sources pass quality checks."""

    def test_all_sources_valid(self):
        errors = validate_sources()
        assert len(errors) == 0, f"Validation errors: {errors}"

    def test_no_duplicate_ids(self):
        ids = [s.id for s in SOURCES]
        assert len(ids) == len(set(ids)), "Duplicate source IDs found"
