FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# The repository includes a small deterministic sample of the real public
# snapshot. Mount data/staylens.duckdb and set DUCKDB_PATH for full-data use.
EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501"]
