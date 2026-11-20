#!/usr/bin/env bash
# owner_retrain.sh — W6 (v1.8.0): retrain the ML heads in the OWNER's
# environment (fixes the sklearn version mismatch: the shipped heads
# were trained on sklearn 1.5.2; retraining on YOUR sklearn re-pins the
# sidecars to it and the loader accepts them again). OWNER-RUN ONLY
# (R11: real ML retraining). Heads stay SHADOW; --activate stays manual.
set -u
cd "$(dirname "$0")/.."
echo "[owner_retrain] python/sklearn on THIS machine:"
python3 -c "import sklearn, sys; print('  sklearn', sklearn.__version__, '· python', sys.version.split()[0])"
echo "[owner_retrain] retraining all heads on ml_data/dataset_v1.npz ..."
python3 ml_train.py "$@"
rc=$?
echo "[owner_retrain] ml_train exit $rc — models land in ml_data/models/"
echo "  (heads stay SHADOW; activation is manual: ml_train --activate <head>)"
exit $rc
