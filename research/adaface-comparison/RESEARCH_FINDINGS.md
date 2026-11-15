# AdaFace IR50 isolated CPU preparation

Status: READY for parent comparative evaluation. No full-video recognition was run here. All writes and research dependency installation were confined to this directory; production .venv was unchanged.

## Ready artifacts and use

- `adaface_ir50_ms1mv2.onnx`: author CVLFace AdaFace IR50 MS1MV2 weights, official IR50 backbone, L2-normalized 512-D embedding and raw pre-normalization norm. Float32 input `[N,3,112,112]`, dynamic batch, ONNX opset17. **Input is RGB normalized with `(x/255-0.5)/0.5`**. The graph input is named `bgr_input` for historical script reasons; its semantic channel order is RGB.
- `adaface_adapter.py`: `AdaFaceCPU(model_path=DEFAULT_MODEL, threads=2)`, `.infer(aligned_bgr)` -> `(unit_512_vector, raw_norm)`, `.get_feat(aligned_bgr)` -> embedding. Accepts already aligned OpenCV uint8 BGR `[112,112,3]`, reverses BGR to RGB, normalizes, and uses CPUExecutionProvider only. Alignment is the caller's responsibility; invalid shapes/dtypes raise.
- Shared evaluator: use `--color rgb`, external normalization, embedding output0. Raw norm output1 is optional quality proxy, not a calibrated acceptance threshold.
- `export_validate.py` reproduces export using isolated `.venv/Scripts/python.exe`; `validation.json` contains numerical smoke evidence. `requirements-research.lock.txt` records the separate environment.

## Official provenance

Original author repository: https://github.com/mk-minchul/AdaFace . Source fetched via GitHub contents API because raw.githubusercontent.com failed. Its README calls https://github.com/mk-minchul/CVLface the new official repository. The CVLFace official README explicitly links https://huggingface.co/minchul/cvlface_adaface_ir50_ms1mv2 . The original and new official README copies are `official/README.md` and `cvlface-readme.md`.

The author model repository was obtained through `hf-mirror.com` because direct Hugging Face timed out. Repository revision observed in resolve metadata: `aa35c74e86afb7482cb7859af4c14eab83a8728d`. Download URL: https://hf-mirror.com/minchul/cvlface_adaface_ir50_ms1mv2/resolve/main/model.safetensors?download=true . It redirects to Hugging Face Xet storage. Download SHA256 exactly matches the author's LFS oid reported in repository metadata (`hfmirror-files.txt`). This verifies byte identity against the author repository's model metadata; the mirror is the transport.

Original 2022 author-linked checkpoint: https://drive.google.com/file/d/1eUaSHG4pGlIZK7hBkqjyp2fc2epKoBvI/view?usp=sharing . Both `drive.usercontent.google.com/download` and `drive.google.com/uc` failed with `ConnectTimeout` / WinError10060. A third-party copy was obtained solely for tensor comparison: https://hf-mirror.com/Jaspann/Person-Recognition-for-Pose-Estimation/resolve/main/components/adaface_ir50_ms1mv2.ckpt?download=true . Its hash matches that mirror's LFS metadata but is not independently authenticated to an author-published checksum. The production candidate and exported model use the author safetensors, not this third-party checkpoint.

## RGB/BGR issue resolved at tensor level

Original `official/inference.py::to_input` takes PIL RGB, reverses to BGR, then computes `((array / 255.) - 0.5) / 0.5`, transposes to NCHW and casts float32. Original README lines95-99 and118-159 explicitly require BGR.

New author model `cvlface-author/config.json` and `cvlface-author/pretrained_model/model.yaml` explicitly declare `color_space: RGB`. Official CVLFace BaseModel sets input_color_flip=False for RGB; IResNetModel.forward flips only when that flag is true.

Direct comparison of original mirrored checkpoint vs author safetensors:

- 467 matching state tensor keys after stripping original `model.` and new `model.net.` prefixes.
- **466 tensors are bit-for-bit equal.**
- The only different tensor is `input_layer.0.weight`.
- `torch.equal(original_first_conv[:, [2,1,0]], author_first_conv)` is **True**.
- Thus the new author model deliberately reverses first-convolution input channels, preserving the original BGR model's function when fed RGB. Metadata and weights agree. This is stronger evidence than choosing a color order from model naming.

Detailed evidence: `weight-and-graph-inspection.json`. The original checkpoint was loaded with weights_only=True, with only an inert stand-in for the serialized Lightning ModelCheckpoint metadata type; no imported third-party checkpoint code was executed.

Numerical sentinel: OpenCV BGR `[0,127,255]` becomes RGB tensor `[1.0,-0.003921568859368563,-1.0]`. Float64 numpy normalization followed by float32 conversion exactly matches the source arithmetic. Parent's float32 `(x-127.5)/127.5` is mathematically equivalent with possible last-bit rounding differences.

## Architecture and validation

Official IR50 backbone has residual stage counts `[3,4,14,3]`, output512, 43,585,600 parameters, input112x112. All467 author checkpoint tensors load with strict=True into the official architecture. Original official network normalizes raw output by its L2 norm and returns `(unit_embedding, norm)`; the export preserves this. CVLFace backbone itself returns raw embeddings, so this export adds the original official L2 convention for cosine-based matching.

Isolated versions: torch2.15.0+cpu, numpy2.4.6, onnx1.23.2, onnxruntime1.31.1, safetensors0.8.0. ONNX checker passes. Deterministic synthetic uint8 crop seed42 gives max absolute PT/ORT embedding error3.0919909477233887e-7, PyTorch raw norm12.253058433532715, ORT raw norm12.253056526184082, unit vector norm0.9999998211860657. CPUExecutionProvider only. Single cold inference0.1196s at2threads was measured while parent baseline work may overlap; it is a smoke result, not a comparative performance benchmark. No more CPU inference followed this smoke.

Additional requested ArcFace graph inspection: `research/arcface-comparison/w600k_r50.onnx` input float32 `[N,3,112,112]`, first node Conv(input.1,...); op types only Add/BatchNormalization/Conv/Flatten/Gemm/PRelu. No input normalization or channel transform is embedded. Use official external RGB normalization. Full details in `weight-and-graph-inspection.json`.

## Exact hashes

| Artifact | Bytes | SHA256 |
|---|---:|---|
| author-model.safetensors | 174544600 | 6c5e2efce4a9715fdf715db46ac159f5bd30d07c8e18f2daf148abd64afcf490 |
| adaface_ir50_ms1mv2.onnx | 174391904 | 0959b7f37514a41e58c90d443c20ace6d9db0f94b69fccea8be234a53913cc44 |
| original mirrored adaface_ir50_ms1mv2.ckpt | 700286703 | 234da6ce931f821e0a8e920063dc2091d8122ea46285c159d2f25d3f762fecb3 |
| official/net.py | 12787 | b4db4eb0174a385fd29e5f616391b50d443f455990c8b88dcab1f8021af8ba4c |
| official/inference.py | 1380 | 5c0758cb3218ccf8c5ebfcaea71aca59da7332e94c0c2a57dbe87bc21b4f8cfa |
| official/LICENSE | 1067 | 95b6e493eb9dba27f2150304e790ae254bab18d1611f4d6e2ade28fa3a271583 |

Source blob IDs, URLs, additional hashes and explicit download failures are in `official-provenance.json`, `source-provenance.json`, `alternate-provenance.json`, `weights-provenance.json`, `mirror-download-provenance.json`, `original-mirror-provenance.json`, and `author-code-provenance.json`. The bulk author-source attempt encountered timeout/HTTP521/525 on some mirror small-file cache routes; essential configuration was subsequently fetched at the pinned revision and code verified against official GitHub source.

## License boundary

Original author code `official/LICENSE` is MIT, Copyright(c)2022 Minchul Kim; retain notice when using the code. The author model card explicitly says: "Please cite the orignal paper and follow the license of the training dataset." No separate explicit commercial redistribution grant for MS1MV2 trained weights was established. This preparation supports the authorized isolated research comparison; it does not establish commercial redistribution clearance. Keep model-weight license/dataset clearance separate from MIT source-code permission.
