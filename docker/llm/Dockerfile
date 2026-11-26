# aisuka-pod:<tag>: the pod image with one LLM's weights baked in.
#
#   docker build --build-arg LOCK=qwen3-vl-8b -t aisuka-pod:qwen3-vl-8b docker/llm
#
# On top of aisuka-pod:latest (voice + vLLM). The weights come from the
# repository revision pinned in locks/<LOCK>.json, in layers of at most 4 GB;
# files larger than that are joined when the pod starts (models.py assemble,
# which the hub's start script runs). Ten layers hold up to 40 GB.
ARG POD_IMAGE=ghcr.io/lastdragonb0rn/aisuka-pod:latest
FROM ${POD_IMAGE}

ARG LOCK
COPY models.py /opt/aisuka/models.py
COPY locks/${LOCK}.json /opt/aisuka/model.json

ENV AISUKA_LOCK=/opt/aisuka/model.json \
    AISUKA_LLM_DIR=/models/llm \
    AISUKA_PARTS=/opt/aisuka/parts

RUN /app/.venv/bin/python /opt/aisuka/models.py fits 10
# One RUN per layer; `python3 models.py plan` shows what lands in which.
RUN /app/.venv/bin/python /opt/aisuka/models.py part 0
RUN /app/.venv/bin/python /opt/aisuka/models.py part 1
RUN /app/.venv/bin/python /opt/aisuka/models.py part 2
RUN /app/.venv/bin/python /opt/aisuka/models.py part 3
RUN /app/.venv/bin/python /opt/aisuka/models.py part 4
RUN /app/.venv/bin/python /opt/aisuka/models.py part 5
RUN /app/.venv/bin/python /opt/aisuka/models.py part 6
RUN /app/.venv/bin/python /opt/aisuka/models.py part 7
RUN /app/.venv/bin/python /opt/aisuka/models.py part 8
RUN /app/.venv/bin/python /opt/aisuka/models.py part 9
RUN /app/.venv/bin/python /opt/aisuka/models.py verify && du -sh /models/llm /opt/aisuka/parts
# The image's vLLM must know the model's architecture: a model it cannot
# load fails here, not twenty minutes into a paid pod.
RUN /opt/vllm/bin/python -c "import json; from vllm import ModelRegistry; \
arch = json.load(open('/models/llm/config.json'))['architectures'][0]; \
assert arch in ModelRegistry.get_supported_archs(), 'vLLM does not support ' + arch; \
print('vLLM supports', arch)"

LABEL org.opencontainers.image.description="Aisuka pod: voice services, vLLM and one LLM preinstalled for Runpod"
