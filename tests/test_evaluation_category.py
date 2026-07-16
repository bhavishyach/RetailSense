import pytest

import evaluation


def test_compute_category_metrics_from_records():
    records = [
        {
            'asin': 'A1',
            'confidence_score': 0.8,
            'enrichment_status': 'success',
            'generated_description': 'desc',
            'attributes': '{"color": "blue"}',
            'standardized_category': 'Books',
        },
        {
            'asin': 'A2',
            'confidence_score': 0.5,
            'enrichment_status': 'failed',
            'generated_description': '',
            'attributes': '{}',
            'standardized_category': '',
        },
        {
            'asin': 'A3',
            'confidence_score': 0.9,
            'enrichment_status': 'success',
            'generated_description': 'desc',
            'attributes': '{"size": "M"}',
            'standardized_category': 'Books',
        },
    ]

    evaluated = [evaluation.evaluate_record(record) for record in records]
    metrics = evaluation.compute_category_metrics(records, evaluated)

    assert len(metrics) == 2
    assert metrics[0]['category'] == 'Books'
    assert metrics[0]['record_count'] == 2
    assert metrics[0]['avg_confidence'] == pytest.approx(0.85)
    assert metrics[0]['failure_rate'] == pytest.approx(0.0)
    assert metrics[0]['completeness_score'] == pytest.approx(1.0)

    unclassified = next(item for item in metrics if item['category'] == 'UNCLASSIFIED')
    assert unclassified['record_count'] == 1
    assert unclassified['failure_rate'] == pytest.approx(1.0)
    assert unclassified['avg_confidence'] == pytest.approx(0.5)
