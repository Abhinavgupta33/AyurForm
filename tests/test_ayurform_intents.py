from ayurform_research import INTENTS, classify_intent

def test_all_research_intents_have_classification_paths():
    queries = ["What are the properties of Guduchi?", "What ingredients are in this formulation?", "What is the anupana context?", "What does the source passage say?", "Compare two sources"]
    assert all(classify_intent(q) in INTENTS for q in queries)
