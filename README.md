# aisuka-runpod-images

Docker images for [Aisuka](https://github.com/LastDragonb0rn/aisuka)'s Runpod
pods, with everything preinstalled, so a pod only has to start. The hub picks
the image by itself (`launch_image_repo`, `companion/launch.py`).

| Image | What is inside | Size |
|---|---|---|
| `ghcr.io/lastdragonb0rn/aisuka-pod:latest` | the voice server (Whisper + TeraTTS + voiceprints) with its models, vLLM, gcc | 30 GB unpacked |
| `ghcr.io/lastdragonb0rn/aisuka-pod:qwen3-vl-8b` | the above + `Qwen/Qwen3-VL-8B-Instruct-FP8` (chat and screen vision in one model) | +10 GB |
| `ghcr.io/lastdragonb0rn/aisuka-pod:qwen2.5-7b` | the above + `Qwen/Qwen2.5-7B-Instruct` | +14 GB |

Without these, every pod installed vLLM (several GB with torch) and then
downloaded its model before it could answer: 10 to 20 minutes.

## Which models go into an image

- **Up to ~15 GB of weights: baked in.** Pulling the image is about as fast
  as downloading the model, and the pod needs no network for it.
- **Larger (the 30B-A3B and 32B presets, ~61-65 GB in bf16): not baked.**
  An image that size is slow to pull on every new host and barely fits a
  GitHub runner. They run on `aisuka-pod:latest`, and vLLM downloads them on
  the first start into a Runpod volume (`launch_network_volume` in the hub),
  where they stay for the next pod.

## Building

Actions -> workflow -> Run workflow:

1. `aisuka-pod` builds `:latest` from the current `aisuka-services` image.
2. `aisuka-llm` builds one model image on top of it; pick the model.

Run `aisuka-pod` again when the voice server changes, then `aisuka-llm` for
each model. A new ghcr.io package is private: make `aisuka-pod` public once
(Package settings -> Change visibility), or Runpod cannot pull it.

## How a model is baked in

`docker/llm/locks/<tag>.json` pins one Hugging Face revision: every file,
its size and its hash. `docker/llm/models.py` downloads it in layers of at
most 4 GB (the registry and Runpod handle huge layers badly); files larger
than that are stored in 4 GB pieces and joined when the pod starts (about a
minute, no network). The build checks every hash, and checks that the
image's vLLM knows the model's architecture, so a model it cannot serve
fails the build instead of a paid pod.

Adding a model:

```bash
python3 docker/llm/models.py lock <hf-repo> <tag>   # writes docker/llm/locks/<tag>.json
AISUKA_LOCK=docker/llm/locks/<tag>.json python3 docker/llm/models.py plan
```

Then add `<tag>` to the choices in `.github/workflows/aisuka-llm.yml`, and the
model to `BAKED_MODELS` in aisuka's `server/companion/launch.py`.
