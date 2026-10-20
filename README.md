# Lab 07: Analyze Books on Amazon EC2 and AWS Lambda

In [Lab 06](https://github.com/ksiller/lab-06-s3) you staged 100 Project Gutenberg books in your bucket `public-mst3k`. In this lab you analyze them in the cloud, in two ways:

1. **Part 1: Amazon EC2, as one batch job.** You launch a virtual machine that installs its own software, clones this repository at boot, and analyzes every book in your bucket. The results go into your MongoDB Atlas cluster from [Lab 05](https://github.com/ksiller/lab-05-nosql), one document per book.
2. **Part 2: AWS Lambda, one event at a time.** You deploy the same analysis code as a Lambda function with Chalice. Every book you upload afterwards is analyzed automatically, within seconds, with no machine running.

You do not write analysis code in this lab. It is provided in `src/book_analysis/analyze.py`. Your work is to deploy and run it in both places, and to document the results.

> [!IMPORTANT]
> `mst3k` is a placeholder. Replace it everywhere with your UVA computing ID, for example `public-mst3k` → `public-abc2de`. If your Lab 06 bucket has a different name, use that name.

## Learning goals

**Part 1: Virtual machines (EC2)**

- Understand what a virtual machine (VM) is
- Provision a VM in AWS (EC2) from the command line
- Connect to an EC2 instance with `ssh`
- Customize an EC2 instance at launch: install software and your own code with a startup script
- Understand the life cycle of an EC2 instance: launch, run, stop, terminate

**Part 2: Serverless computing (AWS Lambda)**

- Understand what serverless computing is
- Know the use cases for a server (EC2) vs. serverless compute (AWS Lambda)
- Write a Chalice app that deploys a Lambda function:
  - How to write a Lambda function
  - How to trigger its execution (here: an upload to S3)
  - How to deploy it to AWS

The lab builds on:

- [Lab 05: NoSQL with MongoDB](https://github.com/ksiller/lab-05-nosql): your Atlas cluster stores the results
- [Lab 06: Working with S3](https://github.com/ksiller/lab-06-s3): your bucket holds the books
- [Class 07: EC2](https://github.com/ksiller/DS2022/blob/main/class/07-ec2/README.md)
- [Class 07: Lambda](https://github.com/ksiller/DS2022/blob/main/class/07-lambda/README.md)

## What is in this repository

```text
lab-07-ec2-lambda/
├── README.md
├── pyproject.toml              # uv project: boto3, pymongo; chalice for development
├── uv.lock
├── bootstrap.sh                # EC2 user data: installs git and uv, clones this repo (Part 1)
├── src/book_analysis/
│   ├── analyze.py              # the analysis: S3 → one document per book → MongoDB
│   └── report.py               # prints your proof of completion
└── book-analyzer/              # Chalice app for Lambda (Part 2)
    ├── app.py
    ├── requirements.txt
    ├── chalicelib/analyze.py   # a link to src/book_analysis/analyze.py: one file, two places
    └── .chalice/config.json
```

`pyproject.toml` defines two commands. `uv run analyze public-mst3k` analyzes every `.txt` file in the bucket. `uv run report` prints what is in your database.

## What is computed

Each book becomes one document in the collection `books` of the database `gutenberg` on your Atlas cluster. The S3 key is the document's `_id`:

```json
{
  "_id": "pg11.txt",
  "word_count": 30478,
  "unique_words": 3013,
  "vocabulary_ratio": 0.0989,
  "summary": "It was, no doubt: only Alice did not like to be told so. And she squeezed herself up closer to Alice’s side as she spoke. Alice looked down at them, and considered a little before she gave her answer.",
  "runs": [
    {"by": "local:my-laptop",       "at": "2026-10-27T14:41:05Z"},
    {"by": "ec2:i-0123456789abcdef0", "at": "2026-10-27T15:02:11Z"}
  ]
}
```

| Field | Meaning |
| --- | --- |
| `word_count` | how many words are in the book (a word is a run of letters and apostrophes, in lowercase) |
| `unique_words` | how many distinct words are in the book |
| `vocabulary_ratio` | `unique_words / word_count`: a rough measure of how varied the wording is |
| `summary` | the three sentences that best represent the book (see below) |
| `runs` | **one entry per analysis**: where it ran (`ec2:<instance id>`, `lambda:<function name>`, or `local:<computer name>`) and when |

Before counting, `strip_gutenberg()` removes Project Gutenberg's header and license text, so only the book itself is analyzed.

`summarize()` writes an **extractive** summary: it picks existing sentences instead of writing new ones. Each sentence scores the average frequency of its words in the whole book (ignoring very common words such as *the* or *and*), so sentences about the main characters and topics win. The three best sentences are kept in their original order. It is simple and fast, and the summaries are rough. In Lab 08 a transformer model writes **abstractive** summaries, new text in its own words, into the same documents.

`save()` in `analyze.py` writes each document with one `update_one(..., upsert=True)`: `$set` replaces the statistics, and `$push` appends the run to `runs`. A second run updates the numbers and keeps the history. Lab 08 adds more fields to the same documents.

`runs` is your proof of completion. After Part 1, your 100 books list the ID of *your* EC2 instance. After Part 2, the book you uploaded lists *your* Lambda function. Read `where_am_i()` in `analyze.py` to see how the code finds out where it runs.

## Setup

### 1. Fork and clone this repository

Fork this repository on GitHub (keep the default name): [https://github.com/ksiller/lab-07-ec2-lambda](https://github.com/ksiller/lab-07-ec2-lambda). Clone **your fork** to your own computer:

```bash
mkdir -p ~/ds2022-fall-2026/
cd ~/ds2022-fall-2026/
git clone https://github.com/YOUR_USERNAME/lab-07-ec2-lambda.git
cd lab-07-ec2-lambda
```

Do all of your work in this directory, in the **terminal on your computer** unless a step says otherwise.

### 2. Python environment

The project is already set up. Create the environment from `pyproject.toml` and `uv.lock`:

```bash
uv sync
uv run analyze --help
```

`uv sync` also downloads Python 3.13 if you do not have it. If `uv` is missing, install it with [Installing uv](https://docs.astral.sh/uv/getting-started/installation/).

### 3. Start the Learner Lab and configure the AWS CLI

1. On the AWS Academy **Learner Lab** page, click **Start Lab** and wait for the green **AWS** icon. **Do not click Reset**: it deletes your Lab 06 buckets.
2. Click **AWS Details** → **AWS CLI** → **Show**, and paste the block into `~/.aws/credentials`. The credentials change with every lab session.
3. Check that the CLI works and that your bucket has the books:

   ```bash
   aws sts get-caller-identity
   aws s3 ls s3://public-mst3k/ | head
   ```

### 4. Prepare your MongoDB Atlas cluster

You use your Atlas cluster from [Lab 05](https://github.com/ksiller/lab-05-nosql). Check that the Lab 05 environment variables are still set in your terminal:

```bash
echo "$MONGODB_ATLAS_URL" "$MONGODB_ATLAS_USER"
```

If they are empty, follow [MongoDB Atlas setup](https://github.com/ksiller/DS2022/blob/main/setup/mongodb.md) again. If the Atlas web interface shows your cluster as **Paused**, click **Resume** and wait a few minutes.

**Allow access from anywhere.** In Lab 05 you allowed only UVA addresses. Your EC2 instance gets a new public address every time it starts, and a Lambda function has no fixed address at all, so Atlas must accept connections from any address. In the Atlas web interface, open **Security** → **Database & Network Access** → **IP Access List**, click **+ Add IP Address**, choose **Allow Access from Anywhere** (`0.0.0.0/0`), and confirm. Leave this entry in place for the rest of the semester: Lab 08 and Lab 10 need it too. From now on, your database user's password is the only thing that protects the cluster, so never commit it or share it.

### 5. Store your Atlas settings in SSM Parameter Store

On your computer, `analyze.py` reads the three Lab 05 environment variables. The EC2 instance and the Lambda function do not have them, and they must not be in a file you commit. **AWS Systems Manager Parameter Store** keeps such values in your AWS account. When the environment variables are missing, `analyze.py` reads the parameter `/lab07/mongodb` instead (see `get_atlas_settings()`), with the role `LabRole` on EC2 and Lambda.

Store the three values as one JSON value, copied from your environment variables:

```bash
aws ssm put-parameter --name /lab07/mongodb --type SecureString --overwrite \
  --value "{\"url\": \"$MONGODB_ATLAS_URL\", \"user\": \"$MONGODB_ATLAS_USER\", \"password\": \"$MONGODB_ATLAS_PWD\"}"
```

`SecureString` stores the value encrypted. Check it:

```bash
aws ssm get-parameter --name /lab07/mongodb --with-decryption --query Parameter.Value --output text
```

The output must be valid JSON with your URL, user, and password. If your password contains a `"` or a `\`, the JSON breaks: change the password in Atlas (**Database Access** → **Edit**) and in your shell configuration, then repeat this step.

If `put-parameter` fails with a KMS `AccessDenied` error, run it again with `--type String` (and leave out `--with-decryption` when you check). The value is then stored unencrypted in your AWS account, and it is still not in your repository.

### 6. Test on your computer

Analyze three books from your computer, then print the report:

```bash
uv run analyze public-mst3k --limit 3
uv run report
```

The report shows one row for `local:<your computer name>` with 3 books. If this works, S3 and Atlas are set up correctly. In `mongosh` (as in Lab 05), `use gutenberg` and `db.books.findOne()` show one of the documents.

To also test the Parameter Store path that EC2 and Lambda use, run the same command without the environment variables:

```bash
env -u MONGODB_ATLAS_URL uv run analyze public-mst3k --limit 1
```

## Part 1: Analyze all books on EC2

**The Case:** 100 books are a batch job: start a machine, process everything, shut it down. The machine must install its own software and get the code, because nobody should have to set it up by hand.

### Step 1: Read the bootstrap script

Open [bootstrap.sh](bootstrap.sh). Passed to the instance as **user data**, it runs once, as root, when the instance boots for the first time. It installs `git` and `uv`, clones this repository into `/home/ubuntu/lab-07-ec2-lambda`, and runs `uv sync`. Answer for yourself:

- Why does it run `uv` and `git clone` with `runuser -u ubuntu` instead of as root?
- Why is there no database password and no AWS key in this file?

### Step 2: Launch the instance

Start Lab and update `~/.aws/credentials` if your session expired. Then launch one instance. The command is the one from [Class 07: EC2](https://github.com/ksiller/DS2022/blob/main/class/07-ec2/README.md), plus two options:

```bash
IID=$(aws ec2 run-instances \
  --image-id ami-0b6d9d3d33ba97d99 \
  --instance-type t3.micro \
  --key-name vockey \
  --security-groups launch-wizard-1 \
  --iam-instance-profile Name=LabInstanceProfile \
  --user-data file://bootstrap.sh \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=lab07-mst3k}]' \
  --query 'Instances[0].InstanceId' --output text)
echo "Instance ID: $IID"
```

| Option | Why |
| --- | --- |
| `--iam-instance-profile Name=LabInstanceProfile` | gives the instance the role `LabRole`, so code on it can read S3 and Parameter Store without `~/.aws/credentials` |
| `--user-data file://bootstrap.sh` | the CLI reads `bootstrap.sh` from your computer and hands it to the instance, which runs it at first boot |

`launch-wizard-1` is the security group (SSH allowed) from class. If you do not have it, run `bash 01-launch-ec2-cli.sh` once in [class/07-ec2](https://github.com/ksiller/DS2022/tree/main/class/07-ec2), terminate that instance, and come back.

Wait for the instance and get its address:

```bash
aws ec2 wait instance-running --instance-ids "$IID"
IP=$(aws ec2 describe-instances --instance-ids "$IID" \
  --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)
echo "ssh -i ~/.ssh/labsuser.pem ubuntu@$IP"
```

### Step 3: Log in and wait for the bootstrap

```bash
ssh -i ~/.ssh/labsuser.pem ubuntu@$IP
```

You are now in the **shell on the instance** (prompt `ubuntu@ip-...`). The bootstrap may still be running. Wait for it:

```bash
cloud-init status --wait
cat ~/bootstrap-finished.txt
```

`status: done` and the line `bootstrap finished ...` mean the software is installed and the repository is cloned. If the status is `error`, read the end of `/var/log/cloud-init-output.log`: every command of the bootstrap is printed there.

### Step 4: Run the analysis

Still on the instance:

```bash
cd ~/lab-07-ec2-lambda
uv run analyze public-mst3k
```

The log lists each book. The last line looks like this:

```text
Processed 100 books from s3://public-mst3k in 61.3 s on ec2:i-0123456789abcdef0
```

**Copy this line** for your submission. Then log out with `exit`.

There is no `~/.aws/credentials` file and no `MONGODB_ATLAS_*` variable on the instance. Check how the code still gets access: `uv run python -c "import boto3; print(boto3.client('sts').get_caller_identity()['Arn'])"` prints an ARN with `assumed-role/LabRole/`. With that role, `analyze.py` reads S3 and the Atlas settings in `/lab07/mongodb`.

### Step 5: Check the database and terminate the instance

Back in the **terminal on your computer**, in your clone:

```bash
uv run report
```

The table **Runs by machine** now has a row `ec2:i-...` with 100 books, under your `local:` test runs from Setup. The instance ID is that of *your* instance. The three books from your test have two entries in `runs`: the EC2 run updated their numbers and kept the history.

The job is done, so terminate the instance:

```bash
aws ec2 terminate-instances --instance-ids "$IID"
```

**Success:** Every book in your bucket has a document with a run on your EC2 instance.

## Part 2: Analyze new books with Lambda

**The Case:** When book 101 arrives, starting a machine for one book is wasteful. A Lambda function triggered by the upload analyzes it in a few seconds, and costs nothing while no books arrive.

### Step 1: Read and configure the Chalice app

Open [book-analyzer/app.py](book-analyzer/app.py). The handler `analyze_new_book` calls `analyze_book()` from the same `analyze.py` you ran on EC2. The decorator `@app.on_s3_event` tells Chalice to run it whenever a `.txt` file is created in `BUCKET`.

Set your bucket and your account ID. The Learner Lab does not let Chalice create an IAM role, so `.chalice/config.json` uses `LabRole` (`"manage_iam_role": false`):

```bash
cd book-analyzer
sed -i.bak "s/public-mst3k/public-$USER/" app.py
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
sed -i.bak "s/ACCOUNT_ID/$ACCOUNT/" .chalice/config.json
grep '^BUCKET' app.py
grep iam_role_arn .chalice/config.json
```

`BUCKET` must be your Lab 06 bucket. If your shell's `$USER` is not your computing ID, edit the line in `app.py` by hand.

### Step 2: Deploy

```bash
uv run chalice deploy
```

Chalice packages `app.py`, `chalicelib/`, and `pymongo` (from `requirements.txt`), creates the function `book-analyzer-dev-analyze_new_book`, allows S3 to invoke it, and adds the event notification to your bucket. In the **AWS Console**, check **S3** → `public-mst3k` → **Properties** → **Event notifications**.

### Step 3: Upload a new book

Pick a book that is not among your 100, for example *The Adventures of Tom Sawyer*:

```bash
curl -sSo pg74.txt https://www.gutenberg.org/cache/epub/74/pg74.txt
aws s3 cp pg74.txt s3://public-mst3k/
```

Wait a few seconds, then read the function's log:

```bash
uv run chalice logs -n analyze_new_book
```

The log shows `pg74.txt: ... words (lambda:book-analyzer-dev-analyze_new_book)`. **The first trigger on a bucket can take up to 10 minutes to become active.** If the log stays empty, wait, then upload the book again (`aws s3 cp pg74.txt s3://public-mst3k/`); after that, events arrive within seconds.

### Step 4: Check the database

```bash
cd ..
uv run report
```

**Runs by machine** now also has a row `lambda:book-analyzer-dev-analyze_new_book` with 1 book, and **Books analyzed by Lambda** shows its statistics and summary. The document count is now 101.

**Success:** The new book was analyzed by Lambda, triggered by your upload, with the same code that ran on EC2.

Leave the app deployed. It costs nothing while no books arrive. To remove it later, run `uv run chalice delete` in `book-analyzer`.

## Submit your work

Add a section `## My results` at the **top** of this `README.md` (above the title) with:

1. The last line of `uv run analyze` on EC2 (Part 1, Step 4).
2. The complete output of `uv run report` after Part 2. It is already formatted as Markdown tables.
3. Two or three sentences: for 100 books at once and for one new book a day, would you use EC2 or Lambda, and why? Use the run time from item 1 and the `Duration` in the `REPORT` line of `chalice logs` to compare.
4. One sentence: how do the EC2 instance and the Lambda function get your Atlas password, although it is in no file?

Commit your README and the two files you changed in Part 2, and push:

```bash
git add README.md book-analyzer/app.py book-analyzer/.chalice/config.json
git commit -m "Complete Lab 07: EC2 and Lambda"
git push origin main
```

`config.json` now contains your account ID. That is not a secret. Check with `git status` that no `.pem` file, no `.aws/` folder, and no `.bak` file is staged.

Submit the URL of your fork in the Canvas assignment: `https://github.com/YOUR_USERNAME/lab-07-ec2-lambda`

> **Keep your Lab 06 bucket, the `gutenberg` database, and the `0.0.0.0/0` access list entry.** Do not click **Reset** in the Learner Lab. Lab 08 reads the same books and adds to the same documents.

## Troubleshooting

**AWS and S3**

- `ExpiredToken` **or** `InvalidClientTokenId`**.** Your lab session changed. Paste a fresh block from **AWS Details** → **AWS CLI** into `~/.aws/credentials`.
- `NoSuchBucket` **or** `The specified bucket does not exist`**.** The bucket name in your command (or in `BUCKET` in `book-analyzer/app.py`) is not your Lab 06 bucket. Did you replace `mst3k` with your computing ID? In the **AWS Console**, open **S3** → **General purpose buckets** and find the public bucket you created in Lab 06, or list your buckets with `aws s3 ls`. Use exactly that name. If the bucket is missing, make sure you are in the same Learner Lab account and region (`us-east-1`) as in Lab 06; if it is really gone, recreate it with your Lab 06 script.
- `Cannot read SSM parameter /lab07/mongodb`**.** The parameter does not exist in this account, or you created it in a region other than `us-east-1`. Repeat [Setup step 5](#5-store-your-atlas-settings-in-ssm-parameter-store).

**MongoDB Atlas**

- **Your Atlas cluster is paused.** Atlas pauses free clusters that have not been used for a while. Every connection then fails with `ServerSelectionTimeoutError`, on your computer, on EC2, and in Lambda. In the Atlas web interface, open **Database** → **Clusters**: a paused cluster shows **Paused** and a **Resume** button. Click **Resume**, wait until the cluster is active again (a few minutes), and rerun your command. Nothing in your data or your settings changes.
- `ServerSelectionTimeoutError` **on EC2 or in Lambda, but not on your computer.** Atlas refuses the address. Check that the **IP Access List** contains `0.0.0.0/0` (Setup step 4). New entries take a minute to become active.
- `ServerSelectionTimeoutError` **everywhere, and the cluster is not paused.** The URL is wrong. Print the parameter with `aws ssm get-parameter --name /lab07/mongodb --with-decryption --query Parameter.Value --output text` and compare it with `echo $MONGODB_ATLAS_URL` and with the connection string in Atlas.
- `Authentication failed`**.** The user or password in `/lab07/mongodb` (or in your environment variables) does not match the database user in Atlas **Database Access**. Fix it and repeat Setup step 5.
- `KeyError: 'MONGODB_ATLAS_USER'` **on your computer.** Only some of the three Lab 05 variables are set in this terminal. Run `source ~/.zshrc` (or `~/.bashrc`) and check all three with `echo`.
- `json.decoder.JSONDecodeError`**.** The value of `/lab07/mongodb` is not valid JSON, usually because of a `"` or `\` in the password. See Setup step 5.

**EC2 (Part 1)**

- `run-instances`**:** `InvalidGroup.NotFound`**.** You have no security group `launch-wizard-1`. See Part 1, Step 2.
- `ssh`**:** `Connection refused`**.** The instance is still booting. Wait 30 seconds and retry.
- `uv: command not found` **on the instance.** The bootstrap has not finished, or your shell started before it did. Run `cloud-init status --wait`, then `exit` and log in again.
- `NoCredentialsError` **on the instance.** The instance was launched without `--iam-instance-profile`. From your computer: `aws ec2 associate-iam-instance-profile --instance-id "$IID" --iam-instance-profile Name=LabInstanceProfile`, wait a minute, and retry.
- **The instance reports `local:ip-...` instead of `ec2:i-...`.** Very unlikely; it means the instance metadata service did not answer. Run the analysis again.

**Lambda and Chalice (Part 2)**

- `chalice deploy`**:** `iam:CreateRole` **or** `ACCOUNT_ID` **in an error message.** `.chalice/config.json` still contains the placeholder. Repeat Part 2, Step 1.
- **The upload does not trigger the function.** See the 10-minute note in Part 2, Step 3. Also check that the key ends in `.txt` and that **S3 → Properties → Event notifications** lists the rule.
- `Task timed out after 60.00 seconds` **in** `chalice logs`**.** The function could not reach Atlas in time. Check that your cluster is not paused and that `0.0.0.0/0` is in the IP Access List (see **MongoDB Atlas** above).

## Limitations of this approach

- EC2 processes the books one after another. A much larger corpus would leave the other CPU cores idle. Lab 08 runs the work in parallel on UVA HPC.
- Lambda analyzes new uploads only. A book you delete from the bucket keeps its document in MongoDB, and `index.html` from Lab 06 does not list new books.
- Atlas accepts connections from any address (`0.0.0.0/0`), so the database password is the only protection. Production systems give their servers fixed addresses or private network connections instead.
- Each Lambda environment opens its own connection to Atlas. Hundreds of uploads at once would mean hundreds of connections to a free cluster.
- The summaries only pick sentences that use the book's most frequent words. They often name the main characters but rarely tell the story. Lab 08 replaces them with summaries written by a transformer model.
