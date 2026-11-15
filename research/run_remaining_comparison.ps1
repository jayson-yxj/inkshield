$ErrorActionPreference = 'Stop'
& .\.venv\Scripts\python.exe research\recognition_comparison.py evaluate --cache runtime\recognition-comparison-cache-v2 --model research\arcface-comparison\w600k_r50.onnx --output runtime\recognition-arcface-r50 --label ArcFace-ResNet50
if ($LASTEXITCODE -ne 0) { throw 'ArcFace evaluation failed' }
& .\.venv\Scripts\python.exe research\recognition_comparison.py evaluate --cache runtime\recognition-comparison-cache-v2 --model research\adaface-comparison\adaface_ir50_ms1mv2.onnx --output runtime\recognition-adaface-ir50 --label AdaFace-IR50
if ($LASTEXITCODE -ne 0) { throw 'AdaFace evaluation failed' }
& .\.venv\Scripts\python.exe research\benchmark_recognition_sample.py --cache runtime\recognition-comparison-cache-v2 --models research\insightface-models\models\buffalo_sc\w600k_mbf.onnx research\arcface-comparison\w600k_r50.onnx research\adaface-comparison\adaface_ir50_ms1mv2.onnx --colors rgb rgb rgb --output runtime\recognition-benchmark.json
if ($LASTEXITCODE -ne 0) { throw 'Standalone benchmark failed' }
& .\.venv\Scripts\python.exe research\recognition_pair_diagnostics.py --cache runtime\recognition-comparison-cache-v2 runtime\recognition-mobileface runtime\recognition-arcface-r50 runtime\recognition-adaface-ir50
if ($LASTEXITCODE -ne 0) { throw 'Pair diagnostics failed' }
& .\.venv\Scripts\python.exe research\recognition_threshold_sweep.py --cache runtime\recognition-comparison-cache-v2 runtime\recognition-mobileface runtime\recognition-arcface-r50 runtime\recognition-adaface-ir50
if ($LASTEXITCODE -ne 0) { throw 'Threshold sensitivity failed' }
& .\.venv\Scripts\python.exe research\render_recognition_comparison.py "$env:USERPROFILE\Desktop\5.mp4" runtime\recognition-mobileface runtime\recognition-arcface-r50 runtime\recognition-adaface-ir50 --output runtime\recognition-three-model-review
if ($LASTEXITCODE -ne 0) { throw 'Comparison video failed' }
