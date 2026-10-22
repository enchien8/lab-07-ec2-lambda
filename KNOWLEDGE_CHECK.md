# Lab 07: Knowledge check

Answer each question below it, in your own words, in one to three sentences. Replace the `...` after **Your answer:** with your text, and fill in the measured times in question 4. Your screenshots and reports go into the folder `results/` (see [Submit your work](README.md#submit-your-work) in the README).

Questions 1 to 3 describe **hypothetical** problems: they may not have happened to you, but they are common, and you should know where to look when they do.

## 1. EC2: you cannot log in via `ssh`

You launch your EC2 instance. AWS reports that it has been provisioned and gives you its public IP address, but you cannot log in via `ssh`. You suspect that the security group does not allow SSH access on port 22 (the default) from all IP addresses. Where in the AWS Console would you check?

Screenshot: `results/security-group.png`, the inbound rules of your instance's security group, showing what they should look like when properly configured for this project (Part 1, Step 5).

*Hint:* the lecture slides, and [class/07-ec2](https://github.com/ksiller/DS2022/blob/main/class/07-ec2/README.md), part [3. Launch an EC2 instance in the AWS Console + SSH](https://github.com/ksiller/DS2022/blob/main/class/07-ec2/README.md#3-launch-an-ec2-instance-in-the-aws-console--ssh-15-min) and [Troubleshooting](https://github.com/ksiller/DS2022/blob/main/class/07-ec2/README.md#troubleshooting).

**Your answer:** ...

## 2. Lambda: the function did not trigger

You deployed the Chalice app and uploaded a new book to S3. Several minutes later, you query MongoDB and still do not see a document for the book. You suspect the Lambda function did not trigger. Where in the AWS Console would you check the function's configuration and its trigger?

Screenshot: `results/lambda-trigger.png`, your function's S3 trigger, showing your bucket, the event type, and the `.txt` suffix (Part 2, Step 6).

*Hint:* the class demo [A Lambda function in the AWS Console](https://github.com/ksiller/DS2022/blob/main/demos/07-lambda/README.md), steps [5. Add the S3 trigger](https://github.com/ksiller/DS2022/blob/main/demos/07-lambda/README.md#5-add-the-s3-trigger) and [8. Preview: the same steps with Chalice](https://github.com/ksiller/DS2022/blob/main/demos/07-lambda/README.md#8-preview-the-same-steps-with-chalice).

**Your answer:** ...

## 3. Lambda logs: the function failed while it ran

You uploaded a new book, and the function's **Monitor** tab shows that it was invoked, but MongoDB still has no document for the book. You suspect the function failed while it ran. Where would you find its error message?

Screenshot: `results/lambda-cloudwatch-log.png`, your function's CloudWatch log, showing the line `pg74.txt: ... words` (Part 2, Step 7).

*Hint:* [Part 2, Step 7](README.md#step-7-upload-a-new-book) in the README, and the class demo [A Lambda function in the AWS Console](https://github.com/ksiller/DS2022/blob/main/demos/07-lambda/README.md), step [7. Check the CloudWatch logs](https://github.com/ksiller/DS2022/blob/main/demos/07-lambda/README.md#7-check-the-cloudwatch-logs).

**Your answer:** ...

## 4. EC2 or Lambda?

Would you use EC2 or Lambda to analyze 100 books at once? Which would you use to analyze one new book a day? Explain your choices with the two times you measured.

- EC2 run time for 100 books, from the last line of `analyze.py` on the instance (Part 1, Step 4): ... s
- Lambda `Duration` for one book, from the `REPORT` line of `chalice logs` (Part 2, Step 7): ... ms

**Your answer:** ...

## 5. Only if you did the optional Part 3: your query

How does your query function in `src/book_analysis/query.py` work? Which PyMongo methods does it call (`find`, `sort`, `limit`, `distinct`, `count_documents`), what does each one return, and what does your function return?

Output: `results/query.json`

**Your answer:** ...
