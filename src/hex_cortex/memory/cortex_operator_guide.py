"""Operator guide — step-by-step configuration guidance for humans.

HEX-CORTEX must be able to guide its operator (or any user) through real-world
setup work: local models, training, MCP wiring, servers, voice, vision, video
world-model training, GPU admission. This module is the deterministic playbook
library behind that guidance. Every guide is ordered steps with a why, an
advisory action, a verification, and known pitfalls; a troubleshooting table
maps symptoms to likely causes and fixes.

Detail scales with operator experience: beginners get every explanation and a
verification after each step; experts get a condensed checklist. Pure and
cold — advisory text only. Nothing here executes a command, opens a socket,
or mutates configuration.
"""

from __future__ import annotations

_GUIDE_TYPE = "cortex_operator_guide_v1"
_TOPIC_TYPE = "cortex_guide_topic_v1"
_TROUBLESHOOT_TYPE = "cortex_troubleshooting_guide_v1"
_EXPERIENCE_LEVELS = ("beginner", "intermediate", "expert")


def _step(
    step_id: str,
    title: str,
    why: str,
    action: str,
    verify: str,
    pitfall: str | None = None,
) -> dict[str, str]:
    row = {"step_id": step_id, "title": title, "why": why, "action": action, "verify": verify}
    if pitfall:
        row["pitfall"] = pitfall
    return row


def _issue(symptom: str, likely_cause: str, fix: str) -> dict[str, str]:
    return {"symptom": symptom, "likely_cause": likely_cause, "fix": fix}


GUIDE_TOPICS: dict[str, dict[str, object]] = {
    "local_model_setup": {
        "title": "Local model setup (Ollama)",
        "summary": "Install a local runtime, pick a model that fits your VRAM, verify it answers.",
        "prerequisites": ["A GPU or 16GB+ RAM for CPU inference", "~10GB free disk per model"],
        "steps": [
            _step(
                "install_runtime",
                "Install the Ollama runtime",
                "One runtime serves every local model behind one API, so the rest of HEX-CORTEX stays model-agnostic.",
                "Download from https://ollama.com and install; on Windows it runs as a background service.",
                "Run `ollama --version` in a terminal; a version number must print.",
            ),
            _step(
                "pick_model_size",
                "Pick a model that fits your hardware",
                "A model that overflows VRAM falls back to CPU and becomes 10-50x slower.",
                "Rule of thumb: 4-bit quantization needs ~0.6GB VRAM per billion parameters. 8GB VRAM -> 7-8B models (qwen2.5-coder:7b); 12-16GB -> 14B; 24GB+ -> 32B.",
                "Check VRAM with `nvidia-smi` and compare against the model card size.",
                "Do not pull the largest model first; start small and escalate only if quality is insufficient.",
            ),
            _step(
                "pull_model",
                "Pull the model",
                "Local weights mean no network dependency at inference time.",
                "Run `ollama pull qwen2.5-coder:7b` (or your chosen model).",
                "Run `ollama list`; the model must appear with its size.",
            ),
            _step(
                "smoke_test",
                "Smoke-test one completion",
                "A first real answer proves the whole chain: weights, runtime, GPU offload.",
                "Run `ollama run qwen2.5-coder:7b \"Write a Python function that reverses a string\"`.",
                "The answer arrives in seconds (GPU) and the code is coherent.",
                "First token slow on first call is normal (model load), not a misconfiguration.",
            ),
            _step(
                "structured_output",
                "Verify structured output support",
                "HEX-CORTEX consensus and grounded execution rely on JSON-schema constrained responses.",
                "POST to http://localhost:11434/api/chat with a `format` JSON schema and check the reply parses.",
                "The response body is valid JSON that matches your schema.",
            ),
            _step(
                "wire_armor",
                "Request the model armor plan",
                "The armor scales discipline to the model size so a small model still works safely.",
                "Call the MCP tool `hex_cortex_model_armor` with action=plan and your model's parameter_scale and context window.",
                "The plan returns discipline and step budgets matching your model scale.",
            ),
        ],
        "troubleshooting": [
            _issue(
                "Answers are extremely slow",
                "Model too big for VRAM; layers offloaded to CPU.",
                "Pull a smaller or more quantized variant; confirm with `ollama ps` that the model shows 100% GPU.",
            ),
            _issue(
                "`ollama` not recognized in terminal",
                "Installer did not update PATH or the service is not running.",
                "Restart the terminal; on Windows check the Ollama tray icon / service is started.",
            ),
            _issue(
                "Out-of-memory error on load",
                "Context window setting multiplies KV-cache memory.",
                "Lower `num_ctx` in the request or Modelfile; each doubling of context roughly doubles KV-cache VRAM.",
            ),
        ],
    },
    "model_training": {
        "title": "Model fine-tuning (LoRA/QLoRA)",
        "summary": "Fine-tune a small model on governed data with evaluation and rollback.",
        "prerequisites": [
            "A licensed, provenance-tracked dataset",
            "GPU with 12GB+ VRAM for QLoRA on 7-8B models",
            "Operator approval: training is offline and never autonomous",
        ],
        "steps": [
            _step(
                "define_objective",
                "Write the training objective and success metric first",
                "Without a measurable target you cannot tell improvement from regression.",
                "State: task, baseline score of the untuned model on a held-out set, and the score that would justify promotion.",
                "The objective fits in three sentences and names one primary metric.",
            ),
            _step(
                "prepare_dataset",
                "Prepare train/dev/test splits with provenance",
                "Leakage between splits fakes improvement; provenance is required by the cognitive genome for any promotion.",
                "Deduplicate, then split (e.g. 90/5/5) before any inspection of test data; record source and license per example.",
                "No example appears in two splits (hash check); a provenance field exists on every record.",
                "Never train on data whose license you have not read.",
            ),
            _step(
                "choose_method",
                "Choose QLoRA for consumer GPUs",
                "QLoRA trains adapters on a 4-bit frozen base, cutting VRAM ~4x versus full fine-tuning.",
                "Use Unsloth or Axolotl with a 7-8B base; rank 16-32 adapters are a solid default.",
                "The framework's dry-run/config check passes before real training.",
            ),
            _step(
                "train_and_watch",
                "Train while watching eval loss, not train loss",
                "Falling train loss with rising dev loss is overfitting, the most common small-dataset failure.",
                "Evaluate on the dev split every N steps; keep the checkpoint with the best dev score, not the last one.",
                "Dev-loss curve is saved and the best checkpoint id is recorded.",
            ),
            _step(
                "evaluate_and_gate",
                "Evaluate on the untouched test split, then gate",
                "Promotion needs evidence, and the test split is only honest if used once.",
                "Compare tuned vs baseline on the test split; write the result as an evaluation receipt.",
                "Tuned model beats the promotion threshold defined in step 1; receipt stored.",
            ),
            _step(
                "rollback_plan",
                "Keep the rollback path",
                "The genome forbids promotion without rollback; adapters make rollback trivial.",
                "Keep the base model untouched and version the adapter files; promotion = loading the adapter, rollback = not loading it.",
                "You can serve both baseline and tuned model side by side and diff answers.",
            ),
        ],
        "troubleshooting": [
            _issue(
                "CUDA out of memory during training",
                "Batch size or sequence length too large for QLoRA budget.",
                "Halve micro-batch size, enable gradient accumulation, or cap max sequence length.",
            ),
            _issue(
                "Model got worse at everything else",
                "Catastrophic forgetting from narrow data or too many epochs.",
                "Mix ~10-20% general instruction data into training, lower epochs, or lower adapter rank.",
            ),
            _issue(
                "Great dev score, bad real usage",
                "Dev set too similar to train set (leakage or near-duplicates).",
                "Rebuild splits with stricter dedup (fuzzy match), re-run baseline comparison.",
            ),
        ],
    },
    "mcp_connection": {
        "title": "MCP server connection",
        "summary": "Wire an MCP server (including HEX-CORTEX's own) into a client over stdio.",
        "prerequisites": ["A client that speaks MCP (Claude Code, Claude Desktop, or custom)"],
        "steps": [
            _step(
                "declare_server",
                "Declare the server in the client config",
                "MCP stdio servers are child processes; the client needs the exact launch command.",
                "Add to `.mcp.json`: {\"mcpServers\": {\"hex-cortex\": {\"command\": \"python\", \"args\": [\"-m\", \"hex_cortex.memory.cortex_operational_stdio\"]}}} (adapt command to your venv path).",
                "The client lists the server after restart.",
                "A wrong working directory is the most common failure: use absolute paths.",
            ),
            _step(
                "handshake",
                "Verify the initialize handshake",
                "Until `initialize` succeeds and the client sends `notifications/initialized`, every tool call is rejected.",
                "In the client, check server status; manually you can pipe an initialize JSON-RPC line into the process.",
                "Response contains serverInfo.name = hex-cortex and instructions text.",
            ),
            _step(
                "list_tools",
                "List tools and read their schemas",
                "Tool inputSchema tells the model exactly which arguments are legal; guessing causes blocked calls.",
                "Send `tools/list`; for HEX-CORTEX expect wiring, operational audit, cognitive genome, model armor, operator guide, cognitive loop, repo intelligence and unit tools.",
                "Every tool row has name, description and inputSchema.",
            ),
            _step(
                "first_call",
                "Make one read-only call",
                "A first successful round-trip proves serialization both ways.",
                "Call `hex_cortex_manifest` or `hex_cortex_model_armor` with action=protocols (no side effects).",
                "isError is false and content[0].text parses as JSON.",
            ),
        ],
        "troubleshooting": [
            _issue(
                "Server shows as failed/disconnected in client",
                "Launch command wrong (python not on PATH, venv not used, module not installed).",
                "Point command at the venv python executable with an absolute path; test the command alone in a terminal first.",
            ),
            _issue(
                "Error -32002 on every tool call",
                "Client skipped or failed the initialize handshake.",
                "Restart the client; if custom, send initialize then notifications/initialized before tools/call.",
            ),
            _issue(
                "Tool returns status blocked with *_arguments_invalid",
                "An argument outside the tool's schema was sent.",
                "Re-read inputSchema from tools/list; remove unknown keys — HEX-CORTEX rejects extras by design.",
            ),
        ],
    },
    "server_setup": {
        "title": "Local inference server (OpenAI-compatible)",
        "summary": "Expose a local model behind an OpenAI-compatible endpoint for agents and tools.",
        "prerequisites": ["A working local model (see local_model_setup)"],
        "steps": [
            _step(
                "choose_endpoint",
                "Choose the serving layer",
                "Most agent frameworks speak the OpenAI API shape; serving that shape locally makes every tool compatible.",
                "Ollama already serves http://localhost:11434/v1 (OpenAI-compatible). Alternatives: llama.cpp `llama-server`, vLLM for multi-user throughput.",
                "GET http://localhost:11434/v1/models returns your pulled models.",
            ),
            _step(
                "bind_localhost",
                "Keep the bind on localhost",
                "An open LAN/WAN bind exposes an unauthenticated model endpoint — a real security hole.",
                "Leave the default 127.0.0.1 bind; if remote access is truly needed, put a reverse proxy with auth in front.",
                "From another machine the port is unreachable; locally it answers.",
                "Never set OLLAMA_HOST=0.0.0.0 casually.",
            ),
            _step(
                "client_config",
                "Point clients at the local endpoint",
                "One env var usually switches a whole framework to local inference.",
                "Set base_url=http://localhost:11434/v1 and api_key=ollama (any non-empty string) in the client.",
                "A chat completion request returns a normal OpenAI-shaped response.",
            ),
            _step(
                "health_and_limits",
                "Add a health check and know your concurrency",
                "Agents retry forever against a dead server unless health is observable.",
                "Use /api/version as liveness; note that one consumer GPU handles roughly one generation at a time — queue accordingly.",
                "Health endpoint answers in <100ms while a generation runs.",
            ),
        ],
        "troubleshooting": [
            _issue(
                "Connection refused on port 11434",
                "Runtime not running or bound elsewhere.",
                "Start Ollama; check `OLLAMA_HOST` env; on Windows verify the service in the tray.",
            ),
            _issue(
                "404 on /v1/chat/completions",
                "Serving layer without OpenAI compatibility or wrong path.",
                "Use the /v1 prefix with a recent Ollama; for llama.cpp use llama-server which exposes /v1 natively.",
            ),
            _issue(
                "Second request hangs until the first finishes",
                "Single-GPU serialization of generations.",
                "Expected on consumer hardware; add client-side queueing or set OLLAMA_NUM_PARALLEL only with spare VRAM.",
            ),
        ],
    },
    "voice_setup": {
        "title": "Voice pipeline (local STT + TTS)",
        "summary": "Give HEX-CORTEX ears and a voice, fully local: whisper for input, Piper for output.",
        "prerequisites": ["A microphone", "~2GB disk for voice models"],
        "steps": [
            _step(
                "stt_engine",
                "Install faster-whisper for speech-to-text",
                "faster-whisper runs Whisper 4x faster via CTranslate2 and stays fully local.",
                "`pip install faster-whisper`; start with the `small` model (multilingual, good French) or `distil-small.en` for English only.",
                "Transcribing a 10s WAV yields correct text.",
                "The `tiny` model mishears technical vocabulary; `small` is the honest minimum.",
            ),
            _step(
                "tts_engine",
                "Install Piper for text-to-speech",
                "Piper is offline, fast on CPU, with good French voices (e.g. fr_FR-siwis-medium).",
                "Download a Piper release and one voice .onnx + .json; pipe text to the binary to get a WAV.",
                "`echo bonjour | piper --model fr_FR-siwis-medium.onnx --output_file out.wav` produces audible speech.",
            ),
            _step(
                "capture_loop",
                "Wire capture -> STT -> model -> TTS",
                "The loop is four small pieces; keeping them separate makes each debuggable alone.",
                "Record mic audio (sounddevice/pyaudio) -> transcribe -> send text to the local model -> synthesize the answer.",
                "A spoken question comes back as a spoken answer end to end.",
            ),
            _step(
                "activation_policy",
                "Decide the activation policy",
                "Always-on transcription is a privacy decision the operator must make explicitly, per HEX-CORTEX governance.",
                "Start with push-to-talk; add a wake word (openWakeWord) only after deciding retention policy for audio.",
                "Nothing is recorded outside explicit activation; no raw audio is persisted by default.",
            ),
        ],
        "troubleshooting": [
            _issue(
                "Transcription is gibberish",
                "Wrong sample rate fed to whisper (expects 16kHz mono).",
                "Resample the capture to 16kHz mono 16-bit before transcribing.",
            ),
            _issue(
                "High latency between speech and answer",
                "Whole-utterance processing instead of streaming, or model too large.",
                "Use VAD to cut on silence, transcribe chunks, and keep the LLM small for voice interactions.",
            ),
            _issue(
                "Piper voice sounds robotic/wrong language",
                "Voice model mismatched to language.",
                "Pick a native voice for the language (fr_FR-* for French); medium quality over low.",
            ),
        ],
    },
    "vision_setup": {
        "title": "Vision (local multimodal model)",
        "summary": "Let a local model see: screenshots, diagrams, photos — via an Ollama vision model.",
        "prerequisites": ["Local runtime working (see local_model_setup)", "8GB+ VRAM recommended"],
        "steps": [
            _step(
                "pull_vision_model",
                "Pull a vision-language model",
                "Vision requires a model trained with an image encoder; text models cannot see.",
                "`ollama pull qwen2.5vl:7b` (strong OCR/UI understanding) or `llama3.2-vision:11b`.",
                "`ollama list` shows the model; its card mentions vision.",
            ),
            _step(
                "first_image",
                "Send a first image",
                "The API takes base64 images alongside the prompt; one round-trip validates the whole path.",
                "POST /api/chat with messages=[{role: user, content: \"Describe this image\", images: [\"<base64>\"]}].",
                "The description matches the image content.",
                "Oversized images waste tokens: downscale to ~1024px longest side first.",
            ),
            _step(
                "screen_understanding",
                "Test screen/document understanding",
                "HEX-CORTEX's screen-lab work needs UI and document reading, which is harder than photo captioning.",
                "Send a screenshot and ask for specific text or the location of a button; send a table photo and ask for values.",
                "Extracted text matches ground truth on a screenshot you control.",
            ),
            _step(
                "governance",
                "Set image retention policy",
                "Screenshots can contain secrets (tokens, emails); the cold-mode rule of no-secret-persistence applies to pixels too.",
                "Process images in memory; if persisting, store hashes and derived text, not raw screenshots, unless the operator opts in.",
                "No raw screenshot lands in a receipt or JSONL store by default.",
            ),
        ],
        "troubleshooting": [
            _issue(
                "Model ignores the image and answers generically",
                "Image not actually attached (wrong field name or invalid base64).",
                "Use the `images` array field; strip data:image/png;base64, prefixes; validate the base64 decodes.",
            ),
            _issue(
                "OCR-style questions come back wrong",
                "Model too small for dense text, or image downscaled too far.",
                "Keep text regions >= ~28px height after resize; prefer qwen2.5vl for document work.",
            ),
            _issue(
                "VRAM overflow with vision model",
                "Image tokens add thousands of tokens to context.",
                "Downscale images, send one image per request, or drop to the smaller vision variant.",
            ),
        ],
    },
    "video_training": {
        "title": "Video world-model training",
        "summary": "Turn screen/video recordings into training data for the compact world model.",
        "prerequisites": [
            "Vision pipeline working (see vision_setup)",
            "Operator approval: training runs are step-3+ on the autonomy ladder",
        ],
        "steps": [
            _step(
                "capture_corpus",
                "Capture a balanced frame corpus",
                "A world model learns transitions; unbalanced corpora (one app, one theme) learn shortcuts instead of dynamics.",
                "Record sessions across distinct apps/tasks; extract frames at a fixed rate (e.g. 2fps) and log the action between consecutive frames.",
                "Corpus stats show multiple sources and no class over ~30%.",
                "Rendering diffs (cursor blink, animations) are noise: filter near-identical frame pairs.",
            ),
            _step(
                "encode_frames",
                "Encode frames with the frozen encoder",
                "Training in pixel space is wasteful; the repo's approach trains transitions in latent space over a frozen encoder.",
                "Run the ComfyUI frozen-encoder path to produce latents per frame; store (latent_t, action_t, latent_t+1) triples.",
                "Each triple has finite latents of the expected dimension.",
            ),
            _step(
                "train_transition",
                "Train the compact transition model",
                "The compact world model predicts latent_t+1 from (latent_t, action); the discriminative head scores which action explains an observed transition.",
                "Use cortex_compact_world_model with the observed-transition dataset; keep the action-discriminative objective on.",
                "Top-1 action discrimination on held-out transitions beats the configured minimum accuracy.",
            ),
            _step(
                "evaluate_receipts",
                "Write evaluation receipts and gate promotion",
                "Governance: a trained artifact is a candidate until evidence and operator approval promote it.",
                "Store metrics as receipts; route the promotion decision through the standard gate with a rollback plan (previous checkpoint).",
                "Receipt exists with metrics, dataset hash, and rollback checkpoint id.",
            ),
        ],
        "troubleshooting": [
            _issue(
                "World model predicts the current frame as the next frame",
                "Trivial identity shortcut: transitions dominated by no-op pairs.",
                "Filter static pairs from the corpus and rebalance toward frames where an action changed the screen.",
            ),
            _issue(
                "Great training accuracy, useless routing decisions",
                "Corpus mismatch with real usage distribution.",
                "Capture new sessions from the actual target workflows; retrain and compare via receipts.",
            ),
            _issue(
                "Latent dimensions mismatch between runs",
                "Encoder version drift between capture batches.",
                "Pin the encoder version/hash in every triple; re-encode old batches rather than mixing encoders.",
            ),
        ],
    },
    "gpu_setup": {
        "title": "GPU setup and admission",
        "summary": "Verify CUDA, measure VRAM headroom, and size workloads so nothing thrashes.",
        "prerequisites": ["An NVIDIA GPU (or accept CPU-only mode)"],
        "steps": [
            _step(
                "driver_check",
                "Verify driver and CUDA visibility",
                "Every downstream tool depends on the driver exposing the GPU correctly.",
                "Run `nvidia-smi`; note driver version, CUDA version, total VRAM.",
                "The table lists your GPU with 0% baseline utilization.",
            ),
            _step(
                "measure_headroom",
                "Measure real VRAM headroom",
                "Windows/desktop compositing already consumes VRAM; plan against free VRAM, not total.",
                "Read the memory line of `nvidia-smi` with your normal desktop running.",
                "You know your free VRAM number within ~200MB.",
            ),
            _step(
                "admission_rule",
                "Apply the admission rule before loading anything",
                "Loading a model plus KV-cache beyond free VRAM silently degrades to CPU speeds.",
                "Estimate: weights (GB) + KV-cache (grows with context) + ~1GB margin must fit free VRAM; the repo's GPU guard scripts encode this check.",
                "The planned model + context fits with margin, or you deliberately chose a smaller one.",
            ),
            _step(
                "monitor_under_load",
                "Watch utilization under a real generation",
                "Sustained 100% GPU and stable VRAM means healthy; sawtooth VRAM means paging trouble.",
                "Run `nvidia-smi -l 1` during a long generation.",
                "GPU utilization high and steady; no VRAM growth over consecutive requests.",
            ),
        ],
        "troubleshooting": [
            _issue(
                "nvidia-smi not found",
                "Driver not installed or PATH broken.",
                "Install the current NVIDIA driver; reboot; retry from a fresh terminal.",
            ),
            _issue(
                "Model loads but generation is CPU-slow",
                "Partial GPU offload due to insufficient free VRAM.",
                "Check layer offload in runtime logs (`ollama ps`); use a smaller quant or free VRAM by closing apps.",
            ),
            _issue(
                "VRAM grows across requests until OOM",
                "Multiple models or contexts kept resident.",
                "Limit loaded models (OLLAMA_MAX_LOADED_MODELS=1) and cap num_ctx to what you actually need.",
            ),
        ],
    },
}


def list_guide_topics() -> list[dict[str, object]]:
    """Return the guide catalog: one row per topic, no step bodies."""

    return [
        {
            "topic_type": _TOPIC_TYPE,
            "topic": topic,
            "title": str(spec["title"]),
            "summary": str(spec["summary"]),
            "step_count": len(spec["steps"]),  # type: ignore[arg-type]
        }
        for topic, spec in GUIDE_TOPICS.items()
    ]


def build_operator_guide(
    *,
    topic: str,
    experience_level: str = "beginner",
) -> dict[str, object]:
    """Build one step-by-step guide, detail scaled to operator experience."""

    if topic not in GUIDE_TOPICS:
        raise ValueError(f"unknown guide topic: {topic}")
    if experience_level not in _EXPERIENCE_LEVELS:
        raise ValueError("experience_level must be beginner/intermediate/expert")

    spec = GUIDE_TOPICS[topic]
    steps = []
    for raw in spec["steps"]:  # type: ignore[union-attr]
        step = dict(raw)
        if experience_level == "expert":
            step.pop("why", None)
            step.pop("pitfall", None)
        elif experience_level == "intermediate":
            step.pop("pitfall", None)
        steps.append(step)

    return {
        "guide_type": _GUIDE_TYPE,
        "topic": topic,
        "title": str(spec["title"]),
        "summary": str(spec["summary"]),
        "experience_level": experience_level,
        "prerequisites": list(spec["prerequisites"]),  # type: ignore[arg-type]
        "steps": steps,
        "verify_each_step_before_next": experience_level == "beginner",
        "advisory_only": True,
        "commands_executed": 0,
        "next_action": "follow_steps_in_order",
    }


def build_troubleshooting_guide(
    *,
    topic: str,
    symptom: str | None = None,
) -> dict[str, object]:
    """Return symptom -> likely cause -> fix rows for one topic.

    When a symptom fragment is given, rows are filtered to those whose symptom
    or cause mentions it (case-insensitive); an empty match returns all rows so
    the operator still sees the known failure modes.
    """

    if topic not in GUIDE_TOPICS:
        raise ValueError(f"unknown guide topic: {topic}")

    rows = [dict(row) for row in GUIDE_TOPICS[topic]["troubleshooting"]]  # type: ignore[union-attr]
    matched = True
    if symptom is not None and symptom.strip():
        needle = symptom.strip().lower()
        filtered = [
            row
            for row in rows
            if needle in row["symptom"].lower() or needle in row["likely_cause"].lower()
        ]
        matched = bool(filtered)
        if filtered:
            rows = filtered

    return {
        "guide_type": _TROUBLESHOOT_TYPE,
        "topic": topic,
        "symptom_query": symptom,
        "symptom_matched": matched,
        "issues": rows,
        "advisory_only": True,
        "next_action": "apply_first_matching_fix_then_reverify",
    }
