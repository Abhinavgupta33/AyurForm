from frontend.symptom_components import analysis_plain_text


def test_screen_export_contract_contains_all_passage_fields():
    result = {"user_query": "headache", "passages": [
        {"reference": "Charaka · PDF page 12", "text": "A retrieved passage", "distance": .2345,
         "metadata": {"source_title": "Charaka Samhita", "page_number": 12, "provenance_role": "translated_source"}}
    ]}
    text = analysis_plain_text(result)
    assert "A retrieved passage" in text
    assert "Charaka · PDF page 12" in text
