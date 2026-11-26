# aisuka-pod:latest: everything a Runpod pod for Aisuka needs except the LLM's weights.
#
#   docker build -t aisuka-pod docker/pod
#
# - the voice server (Whisper + TeraTTS) from the aisuka-services image;
# - vLLM in /opt/vllm, the version the hub asks for, so the pod does not
#   spend minutes installing it on every start;
# - transformers held below 5: vLLM 0.11 asks for `>=4.56` with no upper
#   bound, and 5.x dropped `all_special_tokens_extended`, which its
#   tokenizer cache reads, so vLLM died loading any model's tokenizer;
# - gcc, which Triton needs to compile its launchers at run time;
# - the Whisper, TeraTTS and voiceprint weights, in HF_HOME.
#
# A model that is not baked into an aisuka-pod:<tag> image is downloaded by
# vLLM when the pod starts, as before.
ARG SERVICES_IMAGE=ghcr.io/lastdragonb0rn/aisuka-services:latest
FROM ${SERVICES_IMAGE}

ARG VLLM_VERSION=0.11.0

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libc6-dev \
    && rm -rf /var/lib/apt/lists/*

RUN uv venv -q --python 3.13 /opt/vllm \
    && uv pip install --no-cache --python /opt/vllm/bin/python "vllm==${VLLM_VERSION}" "transformers>=4.57,<5" \
    && /opt/vllm/bin/python -c "import importlib.metadata as m; print('vllm', m.version('vllm'))"

COPY prefetch.py /opt/aisuka/prefetch.py
RUN cd /app && PYTHONPATH=/app /app/.venv/bin/python /opt/aisuka/prefetch.py && du -sh "$HF_HOME"

ENV AISUKA_POD_IMAGE=1 \
    AISUKA_VLLM_VERSION=${VLLM_VERSION} \
    HF_HOME=/models \
    HF_XET_HIGH_PERFORMANCE=1

LABEL org.opencontainers.image.description="Aisuka pod: voice services and vLLM preinstalled for Runpod"
