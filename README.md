## Replication

### 1. Install uv

**macOS / Linux:**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh

```

**Windows:**

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

```

*Alternatively, if you already have Python and pip:*

```bash
pip install uv

```

---

### 2. Run the Project

Once `uv` is installed, run the following to sync the environment and render the report. `uv` will automatically download the correct Python version and all dependencies into a local virtual environment.

```bash
uv sync
uv run quarto render report.qmd
uv run streamlit run app.py

```