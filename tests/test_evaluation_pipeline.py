import pytest

import evaluation


def test_compute_pipeline_metrics_from_records():
    records = [
        {
            'asin': 'A1',
            'confidence_score': 0.8,
            'latency_ms': 100,
            'enrichment_status': 'success',
            'generated_description': 'desc',
            'attributes': '{"color": "blue"}',
            'standardized_category': 'Books',
        },
        {
            'asin': 'A2',
            'confidence_score': 0.5,
            'latency_ms': 200,
            'enrichment_status': 'failed',
            'generated_description': '',
            'attributes': '{}',
            'standardized_category': '',
        },
        {
            'asin': 'A3',
            'confidence_score': 0.9,
            'latency_ms': 300,
            'enrichment_status': 'success',
            'generated_description': 'desc',
            'attributes': '{"size": "M"}',
            'standardized_category': 'Electronics',
        },
    ]

    metrics = evaluation.compute_pipeline_metrics(records)

    assert metrics['total_records_processed'] == 3
    assert metrics['total_enriched'] == 2
    assert metrics['total_failed'] == 1
    assert metrics['total_skipped'] == 0
    assert metrics['avg_confidence_score'] == pytest.approx(0.7333333333333333)
    assert metrics['avg_latency_ms'] == 200.0
    assert metrics['p50_latency_ms'] == 200.0
    assert metrics['p95_latency_ms'] == 300.0
    assert metrics['failure_rate'] == 0.3333333333333333
    assert metrics['cost_estimate_usd'] == 0.0
