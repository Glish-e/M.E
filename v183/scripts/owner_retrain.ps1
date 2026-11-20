# owner_retrain.ps1 — W6 (v1.8.0): retrain the ML heads on the OWNER's
# machine (re-pins the sidecars to YOUR sklearn — the shipped heads were
# trained on sklearn 1.5.2 and a different loader version marks them
# UNAVAILABLE). OWNER-RUN ONLY. Heads stay SHADOW; --activate is manual.
$ErrorActionPreference = "Continue"
Set-Location (Join-Path $PSScriptRoot "..")
"[owner_retrain] python/sklearn on THIS machine:"
python3 -c "import sklearn, sys; print('  sklearn', sklearn.__version__, chr(183), 'python', sys.version.split()[0])"
"[owner_retrain] retraining all heads on ml_data/dataset_v1.npz ..."
python3 ml_train.py @args
$rc = $LASTEXITCODE
"[owner_retrain] ml_train exit $rc — models land in ml_data/models/"
"  (heads stay SHADOW; activation is manual: ml_train --activate <head>)"
exit $rc
