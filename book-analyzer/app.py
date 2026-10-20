"""Analyze every new book uploaded to your Lab 06 bucket, with the same code as on EC2.

chalice deploy creates the Lambda function book-analyzer-dev-analyze_new_book and
connects it to S3 ObjectCreated events for .txt files in BUCKET.
chalicelib/analyze.py is a link to src/book_analysis/analyze.py, so Lambda and EC2
run the same file.
"""
import logging

from chalice import Chalice

from chalicelib.analyze import analyze_book

# Change mst3k to your computing ID: your public bucket from Lab 06
BUCKET = "public-mst3k"

app = Chalice(app_name="book-analyzer")
# Show the logger.info lines of analyze.py in CloudWatch
logging.getLogger().setLevel(logging.INFO)


# The function only writes to MySQL, never to the bucket, so it cannot trigger itself
@app.on_s3_event(bucket=BUCKET, events=["s3:ObjectCreated:*"], suffix=".txt")
def analyze_new_book(event):
    """Analyze the uploaded book; event.key is already URL-decoded."""
    analyze_book(event.bucket, event.key)
