# AyurParam 2.9B local GGUF/llama.cpp feasibility

**Investigation date:** 2026-11-17  
**Scope:** read-only feasibility review. No model weights were downloaded, no packages installed, and no application, database, ChromaDB, authentication, or UI files were changed.

## Executive decision

**CONDITIONAL GO for a later development-only experiment with a third-party Q4_K_M GGUF; NO-GO for the official Transformers checkpoint on this laptop.**

The most sufficiently documented candidate found is [A-Aryam/AyurParam-GGUF](https://huggingface.co/A-Aryam/AyurParam-GGUF), specifically its Q4_K_M file (the model card reports approximately 1.7–1.82 GB). This is not an official BharatGen release and is not approved for redistribution: its card claims CC-BY-4.0 while the official model metadata says Apache-2.0 and BharatGen describes non-commercial/open-weight use. Written permission and provenance verification are required before use beyond a private experiment.

## What exists in this project

`models/llm.py` currently loads `bharatgenai/AyurParam` through Transformers with `trust_remote_code=True`, `device_map="auto"`, and FP16 on CUDA/FP32 on CPU. It uses the project’s `<context>`, `<user>`, `<assistant>` JSON prompt and validates structured output. A future adapter should preserve those prompt, validation, and safety boundaries rather than replacing them.

The environment is Python 3.12.10 with Transformers 4.57.6 and Accelerate 1.15.0. PyTorch is `2.15.0+cpu`; `torch.cuda.is_available()` is false and no CUDA build is present. No `llama-cli` or `llama-server` executable is on PATH. Requirements contain no llama.cpp runtime, `llama-cpp-python`, or CUDA-enabled PyTorch dependency.

## Official model facts

The [official AyurParam model card](https://huggingface.co/bharatgenai/AyurParam) describes a domain model fine-tuned from `Param-1-2.9B-Instruct`, with 32 layers, 16 attention heads, 8 KV heads, RoPE/GQA, and a 2048-token maximum position setting. The card’s architecture table contains an internally inconsistent hidden-size value, so exact tensor-level sizing must be confirmed from the downloaded config in a later controlled test.

The current Hugging Face repository is about 11.5 GB and contains three safetensors shards (approximately 4.98 GB, 4.36 GB and 2.1 GB). The card’s official loading path uses Transformers/Accelerate and custom model code. BharatGen’s [models page](https://bharatgen.com/models/) lists AyurParam/Param 2.9B at 8 GB and says the models are free for non-commercial use; commercial use requires checking the applicable license/contacting BharatGen.

The repository history shows that a LICENSE file was later deleted ([commit history](https://huggingface.co/bharatgenai/AyurParam/commits/main)). Therefore the Apache-2.0 metadata should not be treated as a complete redistribution opinion without confirming the current license terms.

## GGUF candidates and provenance

| Candidate | Reported Q4_K_M | Publisher/provenance | Assessment |
|---|---:|---|---|
| [A-Aryam/AyurParam-GGUF](https://huggingface.co/A-Aryam/AyurParam-GGUF) | ~1.7–1.82 GB | Aarya R. Thakar; says converted from `bharatgenai/AyurParam` with llama.cpp | **Preferred technical candidate, not rights-approved.** Card supplies prompt format and conversion claim, but no independently verified conversion manifest/checksum or official tokenizer proof. |
| [Prady029/AyurParam-2.9b-it-gguf](https://huggingface.co/Prady029/AyurParam-2.9b-it-gguf) | ~1.82 GB | Third-party conversion | Alternative only; provenance and license claims need independent verification. |
| [arunmcops/AyurParam-GGUF](https://huggingface.co/arunmcops/AyurParam-GGUF) | ~1.7 GB | Third-party conversion | Multiple quantizations are listed, but conversion evidence is less complete. |

The cards report Q4_K_M, Q8_0 and/or F16 variants, but these are claims by the conversion publishers, not an official BharatGen artifact. A Q4 file is not evidence that tokenizer files, special-token IDs, chat template, or generation behavior exactly match the source. The A-Aryam card documents `<user> ... <assistant>` prompting; exact tokenizer/template preservation still requires a later smoke test against known official outputs.

## Memory and hardware estimates

These are engineering estimates, not measurements on this machine:

| Representation | Approximate weight memory before runtime overhead | RTX 2050 4 GB |
|---|---:|---|
| FP32 official checkpoint | ~11.6 GB | Not feasible in VRAM; exceeds practical 16 GB system budget with runtime overhead. |
| FP16/BF16 | ~5.8 GB | Cannot fully fit; official repository itself is ~11.5 GB on disk. |
| INT8 weight-only | ~2.9 GB plus scales/overhead | Very tight once KV cache and CUDA buffers are included. |
| Q4_K_M GGUF | ~1.5 GB theoretical, ~1.7–1.9 GB reported | Partial or modest offload is plausible; full offload is not guaranteed. |

KV cache, temporary buffers, allocator fragmentation and the application consume additional memory. With 4 GB VRAM, Q4_K_M should be treated as **CPU-first with optional partial GPU offload**, not as a full-GPU model. CPU-only Q4 inference should fit in 16 GB RAM, but generation will be substantially slower and throughput will depend on the laptop CPU, context length and number of generated tokens. A 2048-token context and 300–350 output tokens (the current application defaults) increase latency and cache use.

The current PyTorch installation has no CUDA support, so the existing `models/llm.py` cannot use the RTX 2050 without a separately approved CUDA environment change. This investigation did not make that change.

## llama.cpp and Windows

The official [llama.cpp build documentation](https://github.com/ggml-org/llama.cpp/blob/master/docs/build.md) documents Windows builds and CUDA builds using CMake (`-DGGML_CUDA=ON`), plus non-native builds when the target GPU is not available at build time. Official releases also publish Windows x64 CPU/CUDA artifacts. This establishes technical compatibility, not performance or model correctness on this laptop.

Safest later approach: use a pinned official llama.cpp Windows release (or a separately reviewed `llama-cpp-python` wheel), keep the binary/model outside the production corpus, and expose it only through a localhost process/API. Do not compile or install it as part of this read-only milestone.

## Clean integration boundary (future milestone)

Do not alter `models/llm.py` until the standalone model test passes. Add a separate adapter (for example `models/llm_gguf.py`) behind the same `generate(prompt, max_new_tokens)` contract, or call a pinned local `llama-server` process. Reuse `build_prompt`, `parse_structured_response`, and `validate_generation`; retain mock mode and fail closed when the local server/model is unavailable. Log status and timing, never prompts containing sensitive user data or model secrets.

The first integration test should compare: tokenizer special tokens, the `<user>/<assistant>` template, JSON validity, stop-token behavior, context truncation, and a small set of deterministic prompts against the official Transformers path (on a suitable machine). Only then should it be connected to RAG retrieval.

## Risks and unresolved questions

- No GGUF candidate was downloaded or executed; local inference is **not verified**.
- Third-party conversion licenses conflict with official metadata and BharatGen’s non-commercial guidance. Obtain written permission before redistribution or commercial use.
- No independently verifiable SHA-256, conversion command, tokenizer files, or chat-template equivalence was established for the candidates.
- The official card’s architecture table has an inconsistent hidden-size entry; exact memory/KV estimates require the actual config.
- CPU Q4 latency may be unsuitable for interactive Streamlit requests; use a timeout and a clear unavailable state.
- RTX 2050 CUDA driver/toolkit compatibility and available VRAM under Windows were not tested.

## Later implementation sequence

1. Confirm model rights, source identity, and an approved GGUF checksum.
2. Obtain the model through an authenticated, policy-compliant download; keep it in a development-only directory.
3. Install/pin llama.cpp runtime separately and run a standalone CPU Q4 smoke test.
4. Measure RAM, VRAM, prompt latency, tokens/sec, context limits and JSON failure rate.
5. Try conservative partial CUDA offload only after CPU behavior is correct.
6. Add the adapter boundary and tests; preserve the existing safety validator and mock fallback.
7. Require explicit approval before connecting the adapter to the RAG/UI path.

**Bottom line:** technically plausible for private CPU/partial-GPU development with a Q4_K_M GGUF; not presently verified, not production-ready, and not legally cleared for redistribution.
