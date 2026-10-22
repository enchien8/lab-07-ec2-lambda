# Lab 07: background for Claude Code

This repository is a lab assignment in DS 2022 at the University of Virginia. The person
working in it is a student learning to use Amazon EC2 and AWS Lambda. README.md has the
full instructions.

## How to help

- Explain before you change anything, and keep explanations short and concrete.
- When the student asks you to write code, write the smallest piece that does the job and
  explain each part. Prefer helping the student write it over writing it for them.
- When something fails, find the cause first (logs, error message, the failing step), explain
  it, then suggest a fix.
- Do not write the answers in KNOWLEDGE_CHECK.md, and do not change README.md. The answers are graded
  on the student's own understanding.

## The environment

- AWS Academy Learner Lab, region `us-east-1`. Credentials are in `~/.aws/credentials` and
  expire with every lab session (`ExpiredToken` means: paste a fresh block from the Learner
  Lab page).
- The Learner Lab does not allow creating IAM roles. EC2 uses the instance profile
  `LabInstanceProfile`, Lambda uses the role `LabRole` (`"manage_iam_role": false` in
  `.chalice/config.json`).
- The books are in the student's S3 bucket from Lab 06, named `public-<computing ID>`.
- Results go into the student's own MongoDB Atlas cluster (Lab 05), collection
  `gutenberg.books`. On the student's computer the settings are in the environment variables
  `MONGODB_ATLAS_URL`, `MONGODB_ATLAS_USER`, `MONGODB_ATLAS_PWD`; on EC2 and Lambda in the SSM
  parameter `mongodb_credentials`.
- Python projects use `uv` (`uv sync`, `uv run ...`), also for Chalice (`uv run chalice ...`).

## The code

- `src/book_analysis/analyze.py` is provided and should not be changed. The Lambda app uses an
  identical copy in `book-analyzer/chalicelib/analyze.py`.
- The student builds `book-analyzer/` (Part 2). In the optional Part 3, they write
  `src/book_analysis/query.py` from the skeleton in README.md, with one query function:
  `vocabulary_extremes()`, `books_by_author()`, or a query of their own. `report.py` stays as it is.
- The Lambda function is `book-analyzer-dev-analyze_new_book`; its log:
  `uv run chalice logs -n analyze_new_book` in `book-analyzer/`.

## Safety

- Never print, echo, log, or commit the Atlas password or the AWS credentials, and do not read
  `~/.aws/credentials` or `.pem` files.
- Ask before commands that delete or stop something: deleting buckets or objects,
  `chalice delete`, terminating instances, dropping collections.
- Never suggest clicking **Reset** in the Learner Lab: it deletes the student's buckets.
