#!/usr/bin/env python3
"""Analyze the books in an S3 bucket and store one document per book in MongoDB.

main() analyzes every book in a bucket; analyze_book() analyzes one book. The
documents go into the collection gutenberg.books. The Atlas settings come from the
environment variables MONGODB_ATLAS_URL, MONGODB_ATLAS_USER, and MONGODB_ATLAS_PWD
when they are set, and otherwise from the SSM parameter mongodb_credentials.

Every run appends the name of the machine it ran on (its host name) and the time
to the document's runs list.
"""

import argparse
import json
import logging
import os
import re
import socket
import time
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError
from pymongo import MongoClient
from pymongo.errors import PyMongoError

logger = logging.getLogger(__name__)

# The Learner Lab runs in us-east-1. An EC2 instance has no default region, so it is set here
REGION = "us-east-1"
SSM_PARAMETER = "mongodb_credentials"
DATABASE = "gutenberg"
COLLECTION = "books"


def get_atlas_settings():
    """Return url, user, and password for MongoDB Atlas."""
    # The environment variables, when they are set
    if "MONGODB_ATLAS_URL" in os.environ:
        return {
            "url": os.environ["MONGODB_ATLAS_URL"],
            "user": os.environ["MONGODB_ATLAS_USER"],
            "password": os.environ["MONGODB_ATLAS_PWD"],
        }
    # Otherwise load credentials from the SSM parameter set in AWS
    try:
        resp = boto3.client("ssm", region_name=REGION).get_parameter(Name=SSM_PARAMETER, WithDecryption=True)
    except ClientError as e:
        logger.error("Cannot read SSM parameter %s: %s", SSM_PARAMETER, e)
        raise
    return json.loads(resp["Parameter"]["Value"])


def connect():
    """Return a new client for MongoDB Atlas. Close it with client.close() when you are done."""
    settings = get_atlas_settings()
    return MongoClient(
        settings["url"],
        username=settings["user"],
        password=settings["password"],
        serverSelectionTimeoutMS=10000,  # fail after 10 s instead of 30 s
    )


def get_book_keys(bucket):
    """Return the keys of all .txt files in the bucket."""
    # One call returns at most 1000 objects: enough for the 100 books of this lab
    response = boto3.client("s3", region_name=REGION).list_objects_v2(Bucket=bucket)
    keys = []
    for obj in response.get("Contents", []):  # an empty bucket has no "Contents"
        if obj["Key"].endswith(".txt"):
            keys.append(obj["Key"])
    return keys


def download(bucket, key):
    """Return the text of one book in S3."""
    try:
        obj = boto3.client("s3", region_name=REGION).get_object(Bucket=bucket, Key=key)
    except ClientError as e:
        logger.error("Cannot download s3://%s/%s: %s", bucket, key, e)
        raise
    return obj["Body"].read().decode("utf-8", errors="replace")


def read_header(text):
    """Return title, author, and language from the Project Gutenberg header.

    The header lines look like "Title: Emma"; the label in lowercase is the field name.
    """
    labels = ["Title", "Author", "Language"]
    metadata = {}
    for line in text[:5000].splitlines():  # the header is at the very top of the file
        label, _, value = line.partition(": ")  # "Title: Emma" -> "Title", ": ", "Emma"
        if label in labels:
            metadata[label.lower()] = value.strip()
    return metadata


def find_marker(text, word):
    """Return where "START" or "END OF THE PROJECT GUTENBERG EBOOK" is in the text, or -1.

    Older files say "THIS" instead of "THE", so both are tried.
    """
    for marker in (f"{word} OF THE PROJECT GUTENBERG EBOOK",
                   f"{word} OF THIS PROJECT GUTENBERG EBOOK"):
        position = text.find(marker)
        if position != -1:
            return position
    return -1


def extract_book_text(text):
    """Return the text of the book itself, from the full text of a Project Gutenberg file.

    The file also contains Project Gutenberg's header before the book and its license
    after it, which must not be counted. Every Gutenberg file marks the book with a line "*** START OF THE PROJECT
    GUTENBERG EBOOK ... ***" before it and "*** END OF THE PROJECT GUTENBERG EBOOK"
    after it. Without these lines, the whole text is returned.
    """
    start = find_marker(text, "START")
    end = find_marker(text, "END")
    # the book begins on the line after the START marker and ends on the line before the END marker
    begin = text.find("\n", start) + 1 if start != -1 else 0
    stop = text.rfind("\n", 0, end) if end != -1 else len(text)
    return text[begin:stop]


def process(text):
    """Return metadata and word statistics for one book.

    A word is a run of letters and apostrophes, compared in lowercase.
    """
    stats = read_header(text)  # title, author, language
    book_text = extract_book_text(text)
    words = re.findall(r"[a-z']+", book_text.lower())
    stats["word_count"] = len(words)
    stats["unique_words"] = len(set(words))
    if words:  # an empty file has no ratio
        stats["vocabulary_ratio"] = round(stats["unique_words"] / len(words), 4)
    return stats


def save(books, bucket, key, stats):
    """Create or update the book's document and record this run.

    The document's _id is the book's key in S3; the bucket is stored with it, so the
    document says where its book file is.
    """
    stats["bucket"] = bucket
    books.update_one(
        {"_id": key},
        {
            "$set": stats,  # replaces the statistics of an earlier run
            "$push": {"runs": {"host": socket.gethostname(), "at": datetime.now(timezone.utc)}},
        },
        upsert=True,  # creates the document the first time
    )


def analyze_book(bucket, key):
    """Download, process, and save one book. Called by the Lambda function."""
    stats = process(download(bucket, key))
    client = connect()
    try:
        save(client[DATABASE][COLLECTION], bucket, key, stats)
    except PyMongoError as e:
        logger.error("Cannot save %s to MongoDB: %s", key, e)
        raise
    finally:
        client.close()  # closes the connections to Atlas, also after an error
    logger.info("%s: %s words", key, stats["word_count"])
    return stats


def main():
    """Analyze every book in the bucket given on the command line."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Analyze the books in an S3 bucket and store the results in MongoDB.")
    parser.add_argument("bucket", help="S3 bucket with the books, for example public-mst3k")
    parser.add_argument("--limit", type=int, help="only process the first N books (for testing)")
    args = parser.parse_args()

    keys = get_book_keys(args.bucket)[: args.limit]
    logger.info("Processing %s books from s3://%s", len(keys), args.bucket)

    start = time.time()
    client = connect()
    try:
        books = client[DATABASE][COLLECTION]
        for key in keys:
            save(books, args.bucket, key, process(download(args.bucket, key)))
            logger.info("Saved %s", key)
    except PyMongoError as e:
        logger.error("Cannot save to MongoDB: %s", e)
        raise
    finally:
        client.close()  # closes the connections to Atlas, also after an error
    print(f"Processed {len(keys)} books from s3://{args.bucket} "
          f"in {time.time() - start:.1f} s on {socket.gethostname()}")


if __name__ == "__main__":
    main()
