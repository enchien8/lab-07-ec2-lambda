#!/bin/bash
# EC2 user data: runs once, as root, the first time the instance boots.
# Pass it to aws ec2 run-instances with --user-data file://bootstrap.sh

# 1. Update the package list
apt-get update -y

# 2. Install Git, cURL, and Python 3 without asking for confirmation
apt-get install -y git curl python3

# 3. Install uv
curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="/usr/local/bin" sh

# 4. Clone this repository into the home directory of the ubuntu user
git clone https://github.com/ksiller/lab-07-ec2-lambda.git /home/ubuntu/lab-07-ec2-lambda

# 5. Fix permissions so the 'ubuntu' user owns the cloned files
chown -R ubuntu:ubuntu /home/ubuntu/lab-07-ec2-lambda
