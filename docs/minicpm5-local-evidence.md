# MiniCPM5-2B local registration evidence

Evidence captured on 2026-09-10 for `data/local-models.json`. The URLs below are immutable because
each includes the upstream Git revision.

## Ollama / GGUF Q4_K_M

- Revision metadata:
  <https://huggingface.co/api/models/openbmb/MiniCPM5-2B-GGUF/revision/c451f4d674096e6e6f1cc5d0abb6794bda638304?blobs=true>
- The response identifies revision `c451f4d674096e6e6f1cc5d0abb6794bda638304` and
  `MiniCPM5-2B-Q4_K_M.gguf` with 1,561,318,368 bytes and LFS SHA-256
  `ec2d5801640099e97d8d7e8003ad4d81f336e757811f03a26173dddf386602fd`.
- The benchmark record identifies that GGUF hash, Ollama 0.33.3, an 8,192-token configured
  context, Apple M1 Max hardware, temperature 0, a 256-token generation cap, and three initial
  measurements: <https://github.com/HiQS-Labs/MiniCPM-fork/issues/1>.

## MLX 4-bit

- Revision metadata:
  <https://huggingface.co/api/models/openbmb/MiniCPM5-2B-MLX/revision/3d00c3da500debfe345e60e25a87ed2669f5b1ee?blobs=true>
- The response identifies revision `3d00c3da500debfe345e60e25a87ed2669f5b1ee` and
  `model.safetensors` with 1,416,035,216 bytes and LFS SHA-256
  `c207798696a4a454e7ac211b25227625466c693335941cee8904fb922f295cc1`.
- The pinned
  [`config.json`](https://huggingface.co/openbmb/MiniCPM5-2B-MLX/resolve/3d00c3da500debfe345e60e25a87ed2669f5b1ee/config.json)
  declares 4-bit affine quantization with group size 64 and `max_position_embeddings` 131,072.
- The same benchmark record identifies this MLX revision, mlx-lm 0.31.3, Apple M1 Max hardware,
  temperature 0, a 256-token generation cap, and three initial measurements:
  <https://github.com/HiQS-Labs/MiniCPM-fork/issues/1>.

These citations establish artifact identity and the preliminary comparison setup. They do not turn
the preliminary three-run result into a completed benchmark; the issue's unchecked acceptance
criteria remain the authoritative statement of work still required.
