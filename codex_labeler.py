"""
Codex CLI labeling helper.
Generates prompts and processes Codex outputs for article labeling.

Usage:
  1. Generate a batch: python codex_labeler.py generate --batch-size 5
  2. Run Codex CLI: codex "Label the articles in codex_batch.json following label_schema.json, output to codex_output.json"
  3. Import results: python codex_labeler.py import
"""
import argparse
import json
from pathlib import Path

ARTICLES_FILE = "articles_week.json"
LABELS_FILE = "labels.json"
SCHEMA_FILE = "label_schema.json"
BATCH_FILE = "codex_batch.json"
OUTPUT_FILE = "codex_output.json"


def load_json(path: str) -> dict | list:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_unlabeled_articles() -> list[dict]:
    articles = load_json(ARTICLES_FILE)
    labels = load_json(LABELS_FILE) if Path(LABELS_FILE).exists() else {}
    return [a for a in articles if a["url"] not in labels]


def generate_batch(batch_size: int):
    unlabeled = get_unlabeled_articles()
    if not unlabeled:
        print("All articles are already labeled!")
        return

    batch = unlabeled[:batch_size]
    schema = load_json(SCHEMA_FILE)

    output = {
        "instructions": (
            "Label each article below. For each article, determine if it's about labour unrest "
            "(strikes, work stoppages, union actions, workplace accidents, etc.). "
            "Output a JSON array with one label object per article."
        ),
        "schema": schema,
        "articles": [
            {
                "url": a["url"],
                "title": a.get("title", ""),
                "published_at": a.get("published_at", ""),
                "tags": a.get("tags", []),
                "body": a.get("body", "")[:2000],  # Truncate for context limits
            }
            for a in batch
        ],
    }

    save_json(BATCH_FILE, output)
    print(f"Generated batch with {len(batch)} articles in {BATCH_FILE}")
    print(f"\nRun Codex CLI:")
    print(f'  codex "Read {BATCH_FILE} and {SCHEMA_FILE}. Label each article and write results to {OUTPUT_FILE}"')


def import_results():
    if not Path(OUTPUT_FILE).exists():
        print(f"No {OUTPUT_FILE} found. Run Codex first.")
        return

    labels = load_json(LABELS_FILE) if Path(LABELS_FILE).exists() else {}
    new_labels = load_json(OUTPUT_FILE)

    # Handle both array and dict formats
    if isinstance(new_labels, list):
        for label in new_labels:
            if "url" in label:
                labels[label["url"]] = label
    elif isinstance(new_labels, dict):
        if "labels" in new_labels:
            for label in new_labels["labels"]:
                if "url" in label:
                    labels[label["url"]] = label
        else:
            for url, label in new_labels.items():
                label["url"] = url
                labels[url] = label

    save_json(LABELS_FILE, labels)
    print(f"Imported labels. Total: {len(labels)}")


def show_progress():
    articles = load_json(ARTICLES_FILE)
    labels = load_json(LABELS_FILE) if Path(LABELS_FILE).exists() else {}

    total = len(articles)
    labeled = len(labels)
    yes_count = sum(1 for l in labels.values() if l.get("strike_or_labour_unrest") == "yes")
    no_count = sum(1 for l in labels.values() if l.get("strike_or_labour_unrest") == "no")

    print(f"Progress: {labeled}/{total} articles labeled ({100*labeled/total:.1f}%)")
    print(f"  Labour unrest (yes): {yes_count}")
    print(f"  Not labour unrest (no): {no_count}")
    print(f"  Remaining: {total - labeled}")


def main():
    parser = argparse.ArgumentParser(description="Codex CLI labeling helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    gen = subparsers.add_parser("generate", help="Generate a batch for Codex")
    gen.add_argument("--batch-size", type=int, default=5, help="Number of articles per batch")

    subparsers.add_parser("import", help="Import Codex results")
    subparsers.add_parser("progress", help="Show labeling progress")

    args = parser.parse_args()

    if args.command == "generate":
        generate_batch(args.batch_size)
    elif args.command == "import":
        import_results()
    elif args.command == "progress":
        show_progress()


if __name__ == "__main__":
    main()
