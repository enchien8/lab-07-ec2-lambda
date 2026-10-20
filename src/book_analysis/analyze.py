#!/usr/bin/env python3
"""Summarize the books in an S3 bucket and store one document per book in MongoDB.

The same code runs on your computer, on an EC2 instance (uv run analyze), and in
AWS Lambda (book-analyzer/app.py calls analyze_book). The documents go into the
collection gutenberg.books of your MongoDB Atlas cluster from Lab 05.

Atlas settings come from the Lab 05 environment variables MONGODB_ATLAS_URL,
MONGODB_ATLAS_USER, and MONGODB_ATLAS_PWD when they are set (your computer), and
otherwise from the SSM parameter /lab07/mongodb (EC2 and Lambda). No password is
stored in this repository.

Every run appends where it happened to the document's runs list:
  ec2:<instance id>, lambda:<function name>, or local:<host name>
"""

import argparse
import json
import logging
import os
import re
import socket
import time
import urllib.request
from collections import Counter
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError
from pymongo import MongoClient

logger = logging.getLogger(__name__)

SSM_PARAMETER = "/lab07/mongodb"
DATABASE = "gutenberg"
COLLECTION = "books"

# One client per process: Lambda reuses it for every event a warm environment handles
_client = None


def where_am_i():
    """Return a label for the machine this code runs on."""
    # Lambda sets this variable in every function's environment
    if "AWS_LAMBDA_FUNCTION_NAME" in os.environ:
        return f"lambda:{os.environ['AWS_LAMBDA_FUNCTION_NAME']}"
    # On EC2, the instance metadata service answers at a fixed local address (IMDSv2)
    try:
        token_request = urllib.request.Request(
            "http://169.254.169.254/latest/api/token",
            method="PUT",
            headers={"X-aws-ec2-metadata-token-ttl-seconds": "60"},
        )
        token = urllib.request.urlopen(token_request, timeout=1).read().decode()
        id_request = urllib.request.Request(
            "http://169.254.169.254/latest/meta-data/instance-id",
            headers={"X-aws-ec2-metadata-token": token},
        )
        return f"ec2:{urllib.request.urlopen(id_request, timeout=1).read().decode()}"
    except OSError:
        return f"local:{socket.gethostname()}"


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
        resp = boto3.client("ssm").get_parameter(Name=SSM_PARAMETER, WithDecryption=True)
    except ClientError as e:
        logger.error("Cannot read SSM parameter %s: %s", SSM_PARAMETER, e)
        raise
    return json.loads(resp["Parameter"]["Value"])


def get_books():
    """Return the books collection, connecting to Atlas on first use."""
    global _client
    if _client is None:
        settings = get_atlas_settings()
        _client = MongoClient(
            settings["url"],
            username=settings["user"],
            password=settings["password"],
            serverSelectionTimeoutMS=10000,  # fail after 10 s instead of 30 s
        )
    return _client[DATABASE][COLLECTION]


def list_books(bucket):
    """Return the keys of all .txt objects in the bucket."""
    s3 = boto3.client("s3")
    keys = []
    # list_objects_v2 returns at most 1000 keys per call; the paginator asks for the rest
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket):
        keys += [obj["Key"] for obj in page.get("Contents", []) if obj["Key"].endswith(".txt")]
    return keys


def download(bucket, key):
    """Return the text of one book in S3."""
    try:
        obj = boto3.client("s3").get_object(Bucket=bucket, Key=key)
    except ClientError as e:
        logger.error("Cannot download s3://%s/%s: %s", bucket, key, e)
        raise
    return obj["Body"].read().decode("utf-8", errors="replace")


def strip_gutenberg(text):
    """Return only the book itself, without Project Gutenberg's header and license."""
    start = re.search(r"\*\*\* ?START OF TH(E|IS) PROJECT GUTENBERG EBOOK.*?\*\*\*", text)
    end = re.search(r"\*\*\* ?END OF TH(E|IS) PROJECT GUTENBERG EBOOK", text)
    return text[start.end() if start else 0 : end.start() if end else len(text)]


# Words too common to say anything about a book; they do not count toward a sentence's score
STOPWORDS = set("""
a about after again all also am an and any are as at be been before being but by can could
did do does down for from had has have he her here him his how i if in into is it its just
me more my no not now of on once one only or other our out over said she so some than that
the their them then there these they this to too up upon very was we were what when where
which while who will with would you your
""".split())


def summarize(text, sentences=3):
    """Return the most representative sentences of a book, in their original order.

    An extractive summary: it picks sentences from the book instead of writing new
    ones. Each sentence scores the average frequency of its words in the whole book,
    so sentences about the book's main topics and characters score highest.
    """
    words = [w for w in re.findall(r"[a-z']+", text.lower()) if w not in STOPWORDS]
    freq = Counter(words)
    # Gutenberg wraps lines at about 70 characters: join them before splitting sentences
    flat = " ".join(text.split())
    # A sentence ends at . ! or ? (plus closing quotes), but not after a title such as "Mr."
    candidates = re.split(
        r"(?<!\bMr\.)(?<!\bMrs\.)(?<!\bDr\.)(?<!\bSt\.)(?:(?<=[.!?])|(?<=[.!?][”’\"']))\s+(?=[“‘\"'_A-Z])",
        flat,
    )

    scored = []
    for position, sentence in enumerate(candidates):
        content = [w for w in re.findall(r"[a-z']+", sentence.lower()) if w not in STOPWORDS]
        # Narrative sentences of medium length make the best summaries; skip dialogue
        if 12 <= len(sentence.split()) <= 45 and content and not re.search(r"[“”\"]", sentence):
            score = sum(freq[w] for w in content) / len(content)
            scored.append((score, position, sentence))

    best = sorted(scored, reverse=True)[:sentences]
    return " ".join(sentence for _, _, sentence in sorted(best, key=lambda s: s[1]))


def process(text):
    """Return word statistics and a short summary for one book.

    A word is a run of letters and apostrophes, compared in lowercase.
    """
    text = strip_gutenberg(text)
    words = re.findall(r"[a-z']+", text.lower())
    unique = len(set(words))
    return {
        "word_count": len(words),
        "unique_words": unique,
        "vocabulary_ratio": unique / len(words) if words else 0.0,
        "summary": summarize(text),
    }


def save(books, key, stats, processed_by):
    """Create or update the book's document and record this run."""
    books.update_one(
        {"_id": key},
        {
            "$set": stats,  # replaces the statistics of an earlier run
            "$push": {"runs": {"by": processed_by, "at": datetime.now(timezone.utc)}},
        },
        upsert=True,  # creates the document the first time
    )


def analyze_book(bucket, key):
    """Download, process, and save one book. Called by the Lambda function."""
    processed_by = where_am_i()
    stats = process(download(bucket, key))
    save(get_books(), key, stats, processed_by)
    logger.info("%s: %s words (%s)", key, stats["word_count"], processed_by)
    return stats


def main():
    """Analyze every book in the bucket given on the command line."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Summarize the books in an S3 bucket into MongoDB.")
    parser.add_argument("bucket", help="S3 bucket with the books, for example public-mst3k")
    parser.add_argument("--limit", type=int, help="only process the first N books (for testing)")
    args = parser.parse_args()

    processed_by = where_am_i()
    keys = list_books(args.bucket)[: args.limit]
    logger.info("Processing %s books from s3://%s on %s", len(keys), args.bucket, processed_by)

    start = time.time()
    books = get_books()
    for key in keys:
        save(books, key, process(download(args.bucket, key)), processed_by)
        logger.info("Saved %s", key)
    print(f"Processed {len(keys)} books from s3://{args.bucket} "
          f"in {time.time() - start:.1f} s on {processed_by}")


if __name__ == "__main__":
    main()
