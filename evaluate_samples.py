"""Run the 10 sample descriptions through the current indexed corpus."""

import json
from pathlib import Path

from rag.pipeline import get_ayurvedic_response


questions = json.loads((Path(__file__).parent / "tests" / "sample_questions.json").read_text(encoding="utf-8"))
for number, question in enumerate(questions, start=1):
    result = get_ayurvedic_response(question)
    print(f"{number:02d}. {question}")
    print(f"    mode={result['mode']}; evidence={result['evidence_sufficient']}; passages={len(result['passages'])}; urgent={result['urgent_care']}")
    if not result["passages"]:
        print("    abstention: sufficient classical evidence not found in the indexed source")
