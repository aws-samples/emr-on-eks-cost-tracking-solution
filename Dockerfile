# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

FROM public.ecr.aws/amazonlinux/amazonlinux:latest

RUN dnf upgrade -y

RUN dnf install shadow-utils shadow-utils-subid shadow-utils-subid-devel -y

RUN useradd -u 10001 worker -m
USER worker
WORKDIR /home/worker
ENV PATH="/home/worker/.local/bin:${PATH}"

RUN python3 -m ensurepip --user
RUN pip3 install --user --upgrade pip==23.0.1

RUN pip3 install --upgrade setuptools

COPY --chown=worker:worker ./scrap/requirements.txt .

RUN pip3 install --user -r requirements.txt

COPY --chown=worker:worker ./scrap/ .

CMD ["python3", "scrap.py"]