"""Analyze newly uploaded Project Gutenberg books with AWS Lambda."""

import logging

from chalice import Chalice

from chalicelib.analyze import analyze_book

BUCKET = "public-ethanchien"

app = Chalice(app_name="book-analyzer")
logging.getLogger().setLevel(logging.INFO)


@app.on_s3_event(bucket=BUCKET, events=["s3:ObjectCreated:*"], suffix=".txt")
def analyze_new_book(event):
    """Analyze a text file as soon as it is uploaded to the books bucket."""
    analyze_book(event.bucket, event.key)
