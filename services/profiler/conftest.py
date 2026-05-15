"""pytest が services/profiler/ 以下を rootdir なしで実行できるよう sys.path を調整する。

classifier/commentator と同名の run.py を持つため、profiler の run は
importlib で明示的に "profiler_run" としてロードしてモジュールキャッシュに登録する。
"""

import importlib.util
import sys
from pathlib import Path

_service_root = Path(__file__).parent
_shared_root = _service_root.parent / "shared"

for p in [str(_service_root), str(_shared_root)]:
    if p not in sys.path:
        sys.path.insert(0, p)

# "run" として登録されてしまう前に profiler_run としてロードしておく
_run_path = _service_root / "run.py"
if "profiler_run" not in sys.modules:
    spec = importlib.util.spec_from_file_location("profiler_run", _run_path)
    if spec and spec.loader:
        mod = importlib.util.module_from_spec(spec)
        sys.modules["profiler_run"] = mod
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
