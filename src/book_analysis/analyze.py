#!/usr/bin/env python3
"""Analyze the books in an S3 bucket and store one document per book in MongoDB.

The same code runs on your computer, on an EC2 instance (uv run python src/book_analysis/analyze.py), and in
AWS Lambda (book-analyzer/app.py calls analyze_book). The documents go into the
collection gutenberg.books of your MongoDB Atlas cluster from Lab 05.

Atlas settings come from the Lab 05 environment variables MONGODB_ATLAS_URL,
MONGODB_ATLAS_USER, and MONGODB_ATLAS_PWD when they are set (your computer), and
otherwise from the SSM parameter /lab07/mongodb_credentials (EC2 and Lambda).
No password is stored in this repository.

Every run appends the name of the machine it ran on (its host name) and the
time to the document's runs list.
"""

import argparse
import json
import logging
import os
import re
import socket
import tempfile
import time
from datetime import datetime, timezone

import boto3
import nltk
from botocore.exceptions import ClientError
from nltk.stem import WordNetLemmatizer
from pymongo import MongoClient
from pymongo.errors import PyMongoError

logger = logging.getLogger(__name__)

# The Learner Lab runs in us-east-1. An EC2 instance has no default region, so it is set here
REGION = "us-east-1"
SSM_PARAMETER = "/lab07/mongodb_credentials"
DATABASE = "gutenberg"
COLLECTION = "books"

# Lambda can only write to /tmp, so the NLTK data is downloaded there everywhere.
# NLTK only reads and writes data in the folders listed in nltk.data.path
NLTK_DATA = os.path.join(tempfile.gettempdir(), "nltk_data")
nltk.data.path.append(NLTK_DATA)

# Part of speech from nltk.pos_tag ("NN", "VBD", ...) -> WordNet part of speech;
# words of any other kind are lemmatized as nouns
WORDNET_POS = {"N": "n", "V": "v", "J": "a", "R": "r"}


def get_atlas_settings():
    """Return url, user, and password for MongoDB Atlas."""
    # Your computer (and HPC in Lab 08): the environment variables from Lab 05
    if "MONGODB_ATLAS_URL" in os.environ:
        return {
            "url": os.environ["MONGODB_ATLAS_URL"],
            "user": os.environ["MONGODB_ATLAS_USER"],
            "password": os.environ["MONGODB_ATLAS_PWD"],
        }
    # EC2 and Lambda: the SSM parameter, read with the role LabRole
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
    """Return the keys of all .txt objects in the bucket."""
    s3 = boto3.client("s3", region_name=REGION)
    keys = []
    # list_objects_v2 returns at most 1000 keys per call; the paginator asks for the rest
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket):
        keys += [obj["Key"] for obj in page.get("Contents", []) if obj["Key"].endswith(".txt")]
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
    """Return title, author, language, and release date from the Project Gutenberg header.

    The release date is when Project Gutenberg published the eBook, not when the
    book was written. A field the header does not have is left out.
    """
    # header label (in lowercase) -> name in the metadata
    fields = {"title": "title", "author": "author", "language": "language",
              "release date": "gutenberg_release"}
    header = text[:5000]  # the header is at the very top of the file
    metadata = {}
    for line in header.splitlines():
        label, _, value = line.partition(":")  # "Title: Emma" -> "Title", ":", " Emma"
        name = fields.get(label.lower())
        value = value.strip()
        if name and value and name not in metadata:
            if value.endswith("]") and "[" in value:
                # "June 1, 1998 [eBook #1342]" -> "June 1, 1998"
                value = value[:value.find("[")].strip()
            metadata[name] = value
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


def strip_gutenberg(text):
    """Return only the book itself, without Project Gutenberg's header and license.

    Every Gutenberg file marks the book with a line "*** START OF THE PROJECT
    GUTENBERG EBOOK ... ***" before it and "*** END OF THE PROJECT GUTENBERG EBOOK"
    after it. Without these lines, the whole text is returned.
    """
    start = find_marker(text, "START")
    end = find_marker(text, "END")
    # the book begins on the line after the START marker and ends on the line before the END marker
    begin = text.find("\n", start) + 1 if start != -1 else 0
    stop = text.rfind("\n", 0, end) if end != -1 else len(text)
    return text[begin:stop]


def lemmatize(words):
    """Return the dictionary form (lemma) of each word.

    "running" -> "run", "whispered" -> "whisper", "mice" -> "mouse". The lemmatizer
    needs to know each word's part of speech, so nltk.pos_tag finds it first.
    """
    # The first call downloads the NLTK data; later calls only check that it is there
    nltk.download("wordnet", download_dir=NLTK_DATA, quiet=True)
    nltk.download("averaged_perceptron_tagger_eng", download_dir=NLTK_DATA, quiet=True)
    lemmatizer = WordNetLemmatizer()
    lemmas = []
    for word, tag in nltk.pos_tag(words):
        # the first letter of the tag says noun (N), verb (V), adjective (J), or adverb (R)
        lemmas.append(lemmatizer.lemmatize(word, WORDNET_POS.get(tag[0], "n")))
    return lemmas


def process(text):
    """Return metadata and word statistics for one book.

    A word is a run of letters and apostrophes, compared in lowercase.
    """
    metadata = read_header(text)
    text = strip_gutenberg(text)
    words = re.findall(r"[a-z']+", text.lower())
    unique_lemmas = len(set(lemmatize(words)))
    return {
        **metadata,
        "word_count": len(words),
        "unique_words": len(set(words)),
        "unique_lemmas": unique_lemmas,
        "vocabulary_ratio": round(unique_lemmas / len(words), 4) if words else 0.0,
    }


def save(books, key, stats):
    """Create or update the book's document and record this run."""
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
        save(client[DATABASE][COLLECTION], key, stats)
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
            save(books, key, process(download(args.bucket, key)))
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
