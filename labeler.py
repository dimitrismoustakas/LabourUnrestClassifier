"""
Manual labeling tool for labour unrest classification.
Run with: python labeler.py
"""
import json
import os
from datetime import datetime
from pathlib import Path

ARTICLES_FILE = "articles_week.json"
LABELS_FILE = "labels.json"

# Label schema based on guide.md PoC recommendations
LABEL_SCHEMA = {
    "strike_or_labour_unrest": ["yes", "no"],
    "event_type": [
        "strike",
        "work_stoppage",
        "protest",
        "lockout",
        "union_call",
        "negotiation",
        "workplace_accident",
        "other",
    ],
    "sector": [
        "transport",
        "education",
        "health",
        "manufacturing",
        "construction",
        "public_services",
        "retail",
        "food_industry",
        "energy",
        "telecommunications",
        "finance",
        "tourism",
        "agriculture",
        "maritime",
        "other",
    ],
    "scope": ["company", "local", "regional", "national", "general"],
}


def load_articles() -> list[dict]:
    with open(ARTICLES_FILE, encoding="utf-8") as f:
        return json.load(f)


def load_labels() -> dict:
    if Path(LABELS_FILE).exists():
        with open(LABELS_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_labels(labels: dict):
    with open(LABELS_FILE, "w", encoding="utf-8") as f:
        json.dump(labels, f, ensure_ascii=False, indent=2)


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def truncate_text(text: str, max_lines: int = 15) -> str:
    if not text:
        return "(No body)"
    lines = text.split("\n")
    if len(lines) > max_lines:
        return "\n".join(lines[:max_lines]) + f"\n... ({len(lines) - max_lines} more lines)"
    return text


def display_article(article: dict, index: int, total: int, existing_label: dict | None):
    clear_screen()
    print("=" * 80)
    print(f"ARTICLE {index + 1}/{total}")
    print("=" * 80)
    print(f"\nURL: {article.get('url', 'N/A')}")
    print(f"Published: {article.get('published_at', 'N/A')}")
    print(f"Tags: {', '.join(article.get('tags', []))}")
    print(f"\n--- TITLE ---\n{article.get('title', 'N/A')}")
    print(f"\n--- BODY (preview) ---\n{truncate_text(article.get('body', ''))}")
    print("\n" + "=" * 80)

    if existing_label:
        print("\n[EXISTING LABEL]")
        for k, v in existing_label.items():
            if k not in ("url", "labeled_at"):
                print(f"  {k}: {v}")
    print()


def prompt_choice(prompt: str, options: list[str], allow_skip: bool = True) -> str | None:
    print(f"\n{prompt}")
    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt}")
    if allow_skip:
        print("  s. Skip this field")
        print("  q. Quit labeling this article")

    while True:
        choice = input("Choice: ").strip().lower()
        if allow_skip and choice == "s":
            return None
        if allow_skip and choice == "q":
            return "QUIT"
        if choice.isdigit() and 1 <= int(choice) <= len(options):
            return options[int(choice) - 1]
        print("Invalid choice, try again.")


def label_article(article: dict, existing_label: dict | None) -> dict | None:
    label = {"url": article["url"]}

    # Binary classification
    result = prompt_choice("Is this about a strike or labour unrest?", LABEL_SCHEMA["strike_or_labour_unrest"])
    if result == "QUIT":
        return None
    label["strike_or_labour_unrest"] = result or "unknown"

    # If yes, get more details
    if label["strike_or_labour_unrest"] == "yes":
        result = prompt_choice("Event type:", LABEL_SCHEMA["event_type"])
        if result == "QUIT":
            return None
        label["event_type"] = result

        result = prompt_choice("Sector:", LABEL_SCHEMA["sector"])
        if result == "QUIT":
            return None
        label["sector"] = result

        result = prompt_choice("Scope:", LABEL_SCHEMA["scope"])
        if result == "QUIT":
            return None
        label["scope"] = result

        # Free text fields
        print("\nAction date (YYYY-MM-DD or leave empty): ", end="")
        action_date = input().strip()
        label["action_date"] = action_date if action_date else None

        print("Location (city/region or leave empty): ", end="")
        location = input().strip()
        label["location"] = location if location else None

        print("Primary actor (union/company or leave empty): ", end="")
        actor = input().strip()
        label["primary_actor"] = actor if actor else None

    label["labeled_at"] = datetime.now().isoformat()
    return label


def main():
    articles = load_articles()
    labels = load_labels()
    total = len(articles)

    print(f"Loaded {total} articles, {len(labels)} already labeled.")
    print("\nOptions:")
    print("  1. Label unlabeled articles")
    print("  2. Re-label specific article by number")
    print("  3. Show labeling stats")
    print("  4. Export for Codex CLI")
    print("  q. Quit")

    choice = input("\nChoice: ").strip().lower()

    if choice == "1":
        for i, article in enumerate(articles):
            url = article["url"]
            if url in labels:
                continue
            existing = labels.get(url)
            display_article(article, i, total, existing)

            action = input("Label this article? (y/n/q): ").strip().lower()
            if action == "q":
                break
            if action != "y":
                continue

            new_label = label_article(article, existing)
            if new_label:
                labels[url] = new_label
                save_labels(labels)
                print("\nLabel saved!")
            input("Press Enter to continue...")

    elif choice == "2":
        num = input("Article number (1-based): ").strip()
        if num.isdigit() and 1 <= int(num) <= total:
            i = int(num) - 1
            article = articles[i]
            url = article["url"]
            display_article(article, i, total, labels.get(url))
            new_label = label_article(article, labels.get(url))
            if new_label:
                labels[url] = new_label
                save_labels(labels)
                print("\nLabel saved!")

    elif choice == "3":
        total_labeled = len(labels)
        yes_count = sum(1 for l in labels.values() if l.get("strike_or_labour_unrest") == "yes")
        no_count = sum(1 for l in labels.values() if l.get("strike_or_labour_unrest") == "no")
        print(f"\nTotal labeled: {total_labeled}/{total}")
        print(f"Labour unrest (yes): {yes_count}")
        print(f"Not labour unrest (no): {no_count}")
        input("\nPress Enter to continue...")

    elif choice == "4":
        export_for_codex(articles, labels)

    print("Done.")


def export_for_codex(articles: list[dict], labels: dict):
    """Export unlabeled articles in a format suitable for Codex CLI."""
    unlabeled = [a for a in articles if a["url"] not in labels]
    if not unlabeled:
        print("All articles are labeled!")
        return

    output_file = "codex_labeling_task.md"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("# Codex CLI Labeling Task\n\n")
        f.write("Label each article below using the JSON schema.\n\n")
        f.write("## Label Schema\n")
        f.write("```json\n")
        f.write(json.dumps(LABEL_SCHEMA, indent=2))
        f.write("\n```\n\n")
        f.write("## Articles to Label\n\n")

        for i, article in enumerate(unlabeled[:10], 1):  # Limit to 10 for manageable context
            f.write(f"### Article {i}\n")
            f.write(f"- URL: {article.get('url', 'N/A')}\n")
            f.write(f"- Title: {article.get('title', 'N/A')}\n")
            f.write(f"- Published: {article.get('published_at', 'N/A')}\n")
            f.write(f"- Body: {truncate_text(article.get('body', ''), 10)}\n\n")

    print(f"Exported {min(len(unlabeled), 10)} articles to {output_file}")
    print("Run with Codex CLI: codex 'Label the articles in codex_labeling_task.md and save to codex_labels.json'")


if __name__ == "__main__":
    main()
