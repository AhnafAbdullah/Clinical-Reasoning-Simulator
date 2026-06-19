import copy

import pytest

from app.domain.errors import CaseValidationError
from app.infrastructure.case_schema import validate_case


def test_sample_case_validates(sample_case):
    validate_case(sample_case)  # should not raise


def test_missing_top_level_key_fails(sample_case):
    bad = copy.deepcopy(sample_case)
    del bad["rubric"]
    with pytest.raises(CaseValidationError):
        validate_case(bad)


def test_unknown_top_level_key_fails(sample_case):
    bad = copy.deepcopy(sample_case)
    bad["surprise"] = {}
    with pytest.raises(CaseValidationError):
        validate_case(bad)


def test_investigation_requires_indicated(sample_case):
    bad = copy.deepcopy(sample_case)
    del bad["investigations"]["laboratory"][0]["indicated"]
    with pytest.raises(CaseValidationError):
        validate_case(bad)
