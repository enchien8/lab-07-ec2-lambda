#!/usr/bin/env python3
"""Print the proof of completion for Lab 07: where each book in gutenberg.books was analyzed.

Run on your computer after each part: uv run report
"""

from datetime import datetime

from book_analysis.analyze import get_books

# One row per machine: how many books it analyzed, and when
RUNS_BY_MACHINE = [
    {"$unwind": "$runs"},
    {"$group": {
        "_id": "$runs.by",
        "books": {"$addToSet": "$_id"},
        "first": {"$min": "$runs.at"},
        "last": {"$max": "$runs.at"},
    }},
    {"$project": {"_id": 0, "by": "$_id", "books": {"$size": "$books"}, "first": 1, "last": 1}},
    {"$sort": {"first": 1}},
]

# The books that a Lambda function analyzed
LAMBDA_BOOKS = {"runs.by": {"$regex": "^lambda:"}}


def cell(value):
    """Format one table cell; times to the second, in UTC."""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S UTC")
    return str(value)


def print_table(columns, rows):
    """Print rows (dicts) as a Markdown table."""
    print("| " + " | ".join(columns) + " |")
    print("|" + "---|" * len(columns))
    for row in rows:
        print("| " + " | ".join(cell(row.get(c, "")) for c in columns) + " |")


def main():
    """Print both tables, ready to paste into README.md."""
    books = get_books()
    print(f"### gutenberg.books: {books.count_documents({})} documents\n")
    print("### Runs by machine\n")
    print_table(["by", "books", "first", "last"], books.aggregate(RUNS_BY_MACHINE))
    print("\n### Books analyzed by Lambda\n")
    rows = [{**doc, "file_name": doc["_id"], "runs": len(doc["runs"])}
            for doc in books.find(LAMBDA_BOOKS)]
    print_table(["file_name", "word_count", "unique_words", "vocabulary_ratio", "runs"], rows)
    for row in rows:
        print(f"\n**{row['file_name']}:** {row.get('summary', '')}")


if __name__ == "__main__":
    main()
