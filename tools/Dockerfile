# NomadHub toolbox: every one-off command runs here instead of on the host.
#   docker compose run --rm tools <command>
# e.g. dbt build, python ai/enrich_reviews.py, python data/download_sources.py all,
#      terraform -chdir=terraform plan, aws s3 ls --profile nomadhub
# The repo is mounted at /workspace; ~/.aws and ~/.nomadhub/keys are mounted read-only.
FROM python:3.12-slim

ARG TERRAFORM_VERSION=1.16.5

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl unzip ca-certificates git openssl \
 && curl -fsSL "https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_amd64.zip" -o /tmp/tf.zip \
 && unzip -q /tmp/tf.zip -d /usr/local/bin \
 && curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o /tmp/aws.zip \
 && unzip -q /tmp/aws.zip -d /tmp && /tmp/aws/install \
 && rm -rf /tmp/tf.zip /tmp/aws.zip /tmp/aws /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Same home layout as the host user, so default paths (~/.aws, ~/.nomadhub/keys) just work.
ENV HOME=/home/nomad
RUN mkdir -p /home/nomad && chmod 777 /home/nomad
WORKDIR /workspace
