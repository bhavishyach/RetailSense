import json
import sqlite3
from pathlib import Path

import pytest

import evaluation


@pytest.fixture
def sample_rows():
    return [
        {
            'asin': 'B001',
            'title': 'Example title',
            'category_name': 'Books',
            'standardized_category': 'Books',
            'generated_description': 'A useful product description.',
            'attributes': '{"format": "hardcover"}',
            'confidence_score': 0.87,
            'latency_ms': 125,
            'enrichment_status': 'success',
            'failure_reason': None,
            'enriched_at': '2026-01-01T00:00:00',
            'model_version': 'claude-3.5',
        },
        {
            'asin': 'B002',
            'title': 'Short',
            'category_name': 'Books',
            'standardized_category': '',
            'generated_description': '',
            'attributes': '{}',
            'confidence_score': 0.45,
            'latency_ms': 300,
            'enrichment_status': 'failed',
            'failure_reason': 'timeout',
            'enriched_at': '2026-01-01T00:00:01',
            'model_version': 'claude-3.5',
        },
    ]


def test_evaluate_record_computes_expected_values(sample_rows):
    result = evaluation.evaluate_record(sample_rows[0])

    assert result['completeness_score'] == pytest.approx(1.0)
    assert result['quality_flags'] == []
    assert result['final_status'] == 'SUCCESS'


def test_evaluate_record_generates_quality_flags(sample_rows):
    result = evaluation.evaluate_record(sample_rows[1])

    assert result['completeness_score'] == pytest.approx(0.0)
    assert 'LOW_CONFIDENCE' in result['quality_flags']
    assert 'MISSING_DESCRIPTION' in result['quality_flags']
    assert 'EMPTY_ATTRIBUTES' in result['quality_flags']
    assert 'MISSING_STANDARDIZED_CATEGORY' in result['quality_flags']
    assert 'FAILED_ENRICHMENT' in result['quality_flags']
    assert result['final_status'] == 'FAILED'
