param([ValidateSet('dashboard','experiment','test','probe','gemini','openrouter','free-models','benchmark','latency','simulator','figures','all')][string]$Mode='dashboard',[int]$Port=8765)
$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
$localPython=Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$bundledPython=Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
if (-not (Test-Path -LiteralPath $localPython)) { throw 'Run .\setup.ps1 first to create the project-local .venv' }
$taskPython=$localPython
Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
switch($Mode) {
    'dashboard' { & $taskPython app.py --port $Port }
    'experiment' { & $taskPython -m eval.run_simulation }
    'test' { & $taskPython -m pytest tests eval/tests -q }
    'probe' { & $taskPython -m scripts.probe_providers }
    'gemini' { & $taskPython -m eval.run_simulation --provider gemini --conditions A0 A4 --cycles 12 --seeds 1930 --out-dir output/experiments/gemini_v4 }
    'openrouter' { & $taskPython -m eval.run_simulation --provider openrouter --conditions A0 A4 --cycles 12 --seeds 1930 --out-dir output/experiments/openrouter_v4 }
    'free-models' { & $taskPython -m scripts.sweep_free_models --profile compact --out output/benchmarks/v4/free_model_checks.json }
    'benchmark' { & $taskPython -m eval.run_v4_benchmarks }
    'latency' { & $taskPython -m eval.run_v4_latency --provider gemini --realtime --seeds 1980 1981 --out-dir output/benchmarks/v4/latency_gemini_pooled }
    'simulator' { & $taskPython -m live }
    'figures' { & $taskPython -m scripts.explainer_figures }
    'all' { & $taskPython -m scripts.validate_runtime }
}
exit $LASTEXITCODE
