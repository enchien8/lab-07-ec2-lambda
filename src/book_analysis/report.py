#!/usr/bin/env python3
"""Print a report on gutenberg.books as JSON: on which machines the books were analyzed, and the last processed books."""

import argparse
import json
import logging

from pymongo.errors import PyMongoError

from book_analysis.analyze import COLLECTION, DATABASE, connect

logger = logging.getLogger(__name__)

# How many of the last processed books to list
LAST_PROCESSED = 3


def runs_by_machine(books):
    """Return one entry per machine: its host name and how many books it analyzed."""
    rows = []
    # every host name that appears in any document's runs list
    for host in books.distinct("runs.host"):
        # matches a book if any of its runs has this host name
        count = books.count_documents({"runs.host": host})
        rows.append({"host": host, "books": count})
    return rows


def last_processed(books):
    """Return the documents of the books that were processed last, the latest first."""
    # sorting by runs.at from newest to oldest uses each book's latest run
    return list(books.find().sort("runs.at", -1).limit(LAST_PROCESSED))


def query_by_author(books, author):
    """Return the documents of all books by one author."""
    return list(books.find({"author": author}))


def main():
    """Print the report, or only the books by one author, as one JSON document."""
    parser = argparse.ArgumentParser(description="Print a report of the books in gutenberg.books as JSON.")
    parser.add_argument("--author", help='only list the books by this author, for example "Mark Twain"')
    args = parser.parse_args()

    client = connect()
    try:
        books = client[DATABASE][COLLECTION]
        if args.author:
            result = query_by_author(books, args.author)
        else:
            result = {
                "documents": books.count_documents({}),
                "runs_by_machine": runs_by_machine(books),
                "last_processed": last_processed(books),
            }
        # default=str turns the dates in runs into text: json cannot write datetime values itself
        print(json.dumps(result, indent=2, default=str))
    except PyMongoError as e:
        logger.error("Cannot read from MongoDB: %s", e)
        raise
    finally:
        client.close()  # closes the connections to Atlas, also after an error


if __name__ == "__main__":
    main()
