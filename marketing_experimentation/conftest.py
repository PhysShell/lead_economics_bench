"""Make `tests/` importable without an externally-set PYTHONPATH.

Until this file existed the suite only ran if the caller happened to have
`marketing_experimentation/src` on the path, which was recorded nowhere. That
is the same defect class this track spent a day auditing in someone else's
repository -- an environment assumption that lives in a shell history rather
than in the project -- so it is fixed here rather than explained.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))
