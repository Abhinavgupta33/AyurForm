"""Create a hash-bound approval manifest after a human inspects extracted pages."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ingestion.review import file_sha256, make_review_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Extracted page JSON reviewed by a person")
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    digest = file_sha256(args.input)
    phrase = input(f"After reviewing {args.input}, type exactly APPROVE {digest[:12]}: ").strip()
    try:
        output = make_review_manifest(args.input, args.reviewer, phrase, args.output)
    except Exception as exc:
        parser.exit(2, f"Review approval failed: {exc}\n")
    print(f"Review approval recorded: {output}")


if __name__ == "__main__":
    main()
