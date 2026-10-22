#!/usr/bin/env python3
"""Print the proof of completion for Lab 07: on which machines the books in gutenberg.books were analyzed."""

import argparse
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
        cells = []
        for c in columns:
            # row.get(c, "") leaves the cell empty when a document has no such field,
            # for example no vocabulary_ratio for an empty file
            cells.append(str(row.get(c, "")))
        print("| " + " | ".join(cells) + " |")


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


def query_by_author(books, author):
    """Return the books by one author, with the machine that processed each book last."""
    rows = []
    for doc in books.find({"author": author}):
        doc["file_name"] = doc["_id"]
        doc["last_processed_on"] = doc["runs"][-1]["host"]  # $push appends, so the last run is the latest
        rows.append(doc)
    return rows


def main():
    """Print the report as Markdown tables, or only the books by one author."""
    parser = argparse.ArgumentParser(description="Print a report of the books in gutenberg.books.")
    parser.add_argument("--author", help='only list the books by this author, for example "Mark Twain"')
    args = parser.parse_args()

    client = connect()
    try:
        books = client[DATABASE][COLLECTION]
        if args.author:
            print(f"### Books by {args.author}\n")
            print_table(["file_name", "title", "word_count", "last_processed_on"],
                        query_by_author(books, args.author))
            return  # the finally block below still closes the client
        print(f"### gutenberg.books: {books.count_documents({})} documents\n")
        print("### Runs by machine\n")
        print_table(["host", "books"], runs_by_machine(books))
        print("\n### Last processed books\n")
        print_table(["file_name", "title", "author", "word_count", "unique_words", "vocabulary_ratio", "runs"],
                    last_processed(books))
    except PyMongoError as e:
        logger.error("Cannot read from MongoDB: %s", e)
        raise
    finally:
        client.close()  # closes the connections to Atlas, also after an error


if __name__ == "__main__":
    main()
