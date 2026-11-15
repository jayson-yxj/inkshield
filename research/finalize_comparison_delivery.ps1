$ErrorActionPreference = 'Stop'
& .\.venv\Scripts\python.exe research\finalize_recognition_provenance.py
if ($LASTEXITCODE -ne 0) { throw 'Comparison provenance verification failed' }
& .\.venv\Scripts\python.exe research\create_identity_review_html.py --cache runtime\recognition-comparison-cache-v2 --output runtime\recognition-three-model-review\人物核对.html runtime\recognition-mobileface runtime\recognition-arcface-r50 runtime\recognition-adaface-ir50
if ($LASTEXITCODE -ne 0) { throw 'Human review page generation failed' }
& .\.venv\Scripts\python.exe research\write_recognition_report.py
if ($LASTEXITCODE -ne 0) { throw 'Measured report generation failed' }
& .\.venv\Scripts\python.exe research\verify_recognition_delivery.py
if ($LASTEXITCODE -ne 0) { throw 'Comparison delivery verification failed' }
