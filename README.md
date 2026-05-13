# SafeYield

Welcome to the SafeYield project repository.

## Resources

- **Deployed App**: [safeyield.streamlit.app/](https://safeyield.streamlit.app/)
- **Report**: [github.com/dufourlorenzo/safeyield/report.pdf](https://github.com/dufourlorenzo/safeyield/blob/main/report.pdf)
- **AI logs**:
  - [Conversation 1](https://chatgpt.com/share/6a043930-a564-832b-be0a-45c3a3c4e2a0)
  - [Conversation 2](https://chatgpt.com/share/6a0438f7-6798-832f-a946-628ca8d22099)

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