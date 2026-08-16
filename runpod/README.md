# Runpod LLM deployment boundary

Runpod infrastructure is intentionally not created yet. The model, model license,
context length, and required VRAM must be selected before an endpoint can be sized
correctly.

When those decisions are made:

1. Deploy a version-pinned official `runpod/worker-v1-vllm` image.
2. Configure `MODEL_NAME`, `MAX_MODEL_LEN`, and any model-specific parser settings.
3. Use an OpenAI-compatible streaming endpoint with flex workers set to minimum 0
   and maximum 1 for the MVP.
4. Put the Runpod API key in the existing
   `influence/prod/runpod-api-key` Secrets Manager secret. Do not store it in Git
   or expose it through a `NEXT_PUBLIC_` variable.
5. Add authenticated FastAPI proxy endpoints before allowing browser clients to
   submit inference requests.
6. If a custom worker is later added to this repository, place it under
   `influence-runpod/`, test it on `main`, and create a `runpod-<commit-sha>` GitHub
   release so the Runpod GitHub integration activates the new build.

Generated files or future chat attachments belong in the private S3 artifact
bucket. Chat messages and job metadata belong in PostgreSQL.

