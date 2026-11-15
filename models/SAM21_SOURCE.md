# SAM 2.1 tiny

- Official source: https://github.com/facebookresearch/sam2
- Pinned source commit: 2b90b9f5ceec907a1c18123530e92e794ad901a4
- Checkpoint: sam2.1_hiera_tiny.pt, 156008466 bytes
- SHA256: 7402e0d864fa82708a20fbd15bc84245c2f26dff0eb43a4b5b93452deb34be69
- Official download: https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_tiny.pt
- Independent published LFS digest: https://huggingface.co/facebook/sam2.1-hiera-tiny/blob/main/sam2.1_hiera_tiny.pt
- Source and checkpoints: Apache License 2.0, confirmed by official README license section. License retained as SAM21_LICENSE.txt. Acquisition evidence SAM21_PROVENANCE.json.

SAM2.1 segments one user-selected object with positive/negative points. Pixel coordinates refer to original video dimensions. CPU is default. CUDA is offered only when the installed runtime and NVIDIA GPU report availability; unavailable explicit GPU selection fails rather than silently changing device. The optional CUDA hole-fill extension is disabled; official PyTorch inference still operates on CPU or CUDA.

A click can select a larger object than intended. A valid nonempty mask does not establish privacy coverage or semantic accuracy. Inspect the overlay and rendered video. Editing prompt frames rebuilds video memory; every prompted frame requires a positive point.

This SAM asset license does not change the separate noncommercial research restrictions on the application's InsightFace face-recognition weights.
