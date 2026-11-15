"""CPU scheduling presets; models, precision and per-frame coverage are unchanged."""
import os

# The parallel preset was measured on an 8-core/16-logical Ryzen 7 7435H.
# Keep the existing serial preset on smaller CPUs; opt-out permits comparison
# on other hosts without changing models or cached results.
CPU_MODE = os.environ.get('INKSHIELD_CPU_MODE', 'auto').strip().lower()
if CPU_MODE not in ('auto', 'serial', 'parallel'):
    raise ValueError('INKSHIELD_CPU_MODE must be auto, serial or parallel')
PARALLEL_MODELS = CPU_MODE == 'parallel' or (CPU_MODE == 'auto' and (os.cpu_count() or 1) >= 12)


def session_options(role):
    import onnxruntime as ort
    options = ort.SessionOptions()
    threads = (8 if role == 'human' else 2) if PARALLEL_MODELS else 4
    options.intra_op_num_threads = min(threads, os.cpu_count() or 1)
    options.inter_op_num_threads = 1
    if PARALLEL_MODELS:
        options.add_session_config_entry('session.intra_op.allow_spinning', '0')
    return options
