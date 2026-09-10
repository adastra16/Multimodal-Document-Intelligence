# Setup

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

Start the API:

```bash
python -m uvicorn app.main:app --reload --app-dir backend --host 127.0.0.1 --port 8000
```

Then open `http://127.0.0.1:8000/health` and `http://127.0.0.1:8000/docs`.

`make install-dev`, `make test`, `make lint`, `make typecheck`, and `make run` wrap the same commands if `make` is available.

Do not commit `.env`. Runtime data belongs under `data/` and is gitignored.
