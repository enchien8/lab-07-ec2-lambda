#!/usr/bin/env python3
"""Print the proof of completion for Lab 07: on which machines the books in gutenberg.books were analyzed.

Run on your computer after each part: uv run python src/book_analysis/report.py
"""

import logging

from pymongo.errors import PyMongoError

from book_analysis.analyze import COLLECTION, DATABASE, connect

logger = logging.getLogger(__name__)

# How many of the last processed books to list
LAST_PROCESSED = 5


def print_table(columns, rows):
    """Print rows (dicts) as a Markdown table."""
    print("| " + " | ".join(columns) + " |")
    print("|" + "---|" * len(columns))
    for row in rows:
        print("| " + " | ".join(str(row.get(c, "")) for c in columns) + " |")


def runs_by_machine(books):
    """Return one row per machine: its host name and how many books it analyzed."""
    rows = []
    # every host name that appears in any document's runs list
    for host in books.distinct("runs.host"):
        # matches a book if any of its runs has this host name
        count = books.count_documents({"runs.host": host})
        rows.append({"host": host, "books": count})
    return rows


def last_processed(books):
    """Return the books that were processed last, the latest first."""
    rows = []
    # sorting by runs.at from newest to oldest uses each book's latest run
    for doc in books.find().sort("runs.at", -1).limit(LAST_PROCESSED):
        doc["file_name"] = doc["_id"]
        doc["runs"] = len(doc["runs"])  # how many times the book was analyzed
        rows.append(doc)
    return rows


def main():
    """Print both tables, ready to paste into README.md."""
    client = connect()
    try:
        books = client[DATABASE][COLLECTION]
        print(f"### gutenberg.books: {books.count_documents({})} documents\n")
        print("### Runs by machine\n")
        print_table(["host", "books"], runs_by_machine(books))
        print("\n### Last processed books\n")
        print_table(["file_name", "title", "author", "word_count", "unique_lemmas", "vocabulary_ratio", "runs"],
                    last_processed(books))
    except PyMongoError as e:
        logger.error("Cannot read from MongoDB: %s", e)
        raise
    finally:
        client.close()  # closes the connections to Atlas, also after an error


if __name__ == "__main__":
    main()
