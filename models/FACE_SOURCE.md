# Local noncommercial research model assets

This authorized local personal research build integrates official InsightFace buffalo_sc weights. Their use here does not establish commercial clearance. Do not upload, publish, or redistribute this local build on the basis of this integration.

Source: https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_sc.zip
Official model policy: https://github.com/deepinsight/insightface/tree/master/python-package (pretrained models are available for noncommercial research purposes only; contact upstream for other licensing).

Copied unchanged from the already downloaded and validated research/insightface-source/models/buffalo_sc directory:

- det_500m.onnx (SCRFD500m): SHA256 5e4447f50245bbd7966bd6c0fa52938c61474a04ec7def48753668a9d8b4ea3a
- w600k_mbf.onnx (MobileFaceNet): SHA256 9cc6e4a75f0e2bf0b1aed94578f144d15175f357bdc05e815e5c4a02b319eb4f

Root scrfd.py is a direct-import copy of research/insightface-source/scrfd.py, the saved official InsightFace v0.7 implementation by Jia Guo, with its unused `import onnx` removed. Source code uses the upstream MIT license; model weights have separate usage restrictions. Alignment and recognition preprocessing follow validated research/insightface_cpu.py; association follows research/identity_gallery.py. CPU-only, 640x640 detection, 112x112 aligned RGB recognition normalized by 127.5.

Association IDs are local appearance groups, not verified real identities. Gallery is new per analysis. Threshold .50; person margin .10; enrollment exclusion .40; five quality confirmations; quality score >= .70 and minimum face side >= 40 pixels. Pending detections remain pending in frozen earlier frames. Thumbnail is a JPEG of the aligned face at enrollment; count is assigned detections, not distinct people accuracy.
