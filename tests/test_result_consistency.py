from frontend.symptom_components import analysis_plain_text


def test_failed_generation_keeps_retrieved_evidence_in_export_text():
    result = {"mode": "ollama", "validation_failed": True, "evidence_summary": "schema failed", "limitations": "not validated", "passages": [{"reference": "Source · PDF page 4", "text": "Retrieved excerpt"}], "user_query": "query"}
    text = analysis_plain_text(result)
    assert "Retrieved excerpt" in text
    assert "schema failed" in text
