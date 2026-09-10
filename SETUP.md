# Setup (Phase 1)

Requires Python 3.10 or newer.

```bash
python -m venv .venv
```

Windows: `.venv\Scripts\activate`

macOS/Linux: `source .venv/bin/activate`

```bash
python -m pip install -e ".[dev]"
cp .env.example .env
pytest
ruff check backend
mypy
```

`make install-dev`, `make test`, `make lint`, and `make typecheck` wrap the same commands if `make` is available.

Do not commit `.env`. Runtime data belongs under `data/` and is gitignored.
