"""テンプレート・静的ファイルのパス（`web` パッケージ直下を指す）。"""

from pathlib import Path

from fastapi.templating import Jinja2Templates

PACKAGE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=PACKAGE_DIR / "templates")
FAVICON_PNG = PACKAGE_DIR / "static" / "favicon.png"
