import pytest
from ayurform_sqlalchemy import Base, make_engine


def test_structured_models_have_all_tables():
    expected = {"sources","source_passages","dravya","dravya_synonyms","dravya_attributes","formulations","formulation_ingredients","anupana_relationships","expert_reviews"}
    assert expected <= set(Base.metadata.tables)


def test_postgres_url_is_required():
    with pytest.raises(RuntimeError): make_engine("sqlite:///tmp.db")
