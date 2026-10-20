#!/bin/bash
# EC2 user data: runs once, as root, the first time the instance boots.
# Installs git and uv for the ubuntu user, clones this repository, and installs
# the Python packages. uv also downloads the Python version in .python-version.
# Pass it to aws ec2 run-instances with --user-data file://bootstrap.sh

# -x prints every command to /var/log/cloud-init-output.log for debugging
set -euxo pipefail
export DEBIAN_FRONTEND=noninteractive

REPO=https://github.com/ksiller/lab-07-ec2-lambda.git

# System packages need root; -y because nobody is there to answer prompts
apt-get update -y
apt-get install -y git curl ca-certificates

# Everything else as ubuntu, the user you log in as: tools installed as root
# would land in /root and be invisible to ubuntu
runuser -u ubuntu -- bash -lc 'curl -LsSf https://astral.sh/uv/install.sh | sh'
runuser -u ubuntu -- bash -lc "git clone $REPO \"\$HOME/lab-07-ec2-lambda\""
# --no-dev: the instance does not need Chalice
runuser -u ubuntu -- bash -lc 'cd "$HOME/lab-07-ec2-lambda" && "$HOME/.local/bin/uv" sync --no-dev'

echo "bootstrap finished $(date -u)" > /home/ubuntu/bootstrap-finished.txt
