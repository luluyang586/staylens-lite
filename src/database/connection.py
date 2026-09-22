"""Read-only snapshot access; external access and extension autoload disabled."""
from pathlib import Path
import duckdb
from src.config import settings
CONFIG={"enable_external_access":"false","autoload_known_extensions":"false",
        "autoinstall_known_extensions":"false","threads":"2","memory_limit":"512MB"}
def database_exists(path=None):
    return Path(path or settings.db_path).exists()
def connect(read_only=True,path=None):
    if not read_only: raise ValueError("Application connections must be read-only")
    return duckdb.connect(str(path or settings.db_path),read_only=True,config=CONFIG)
def metadata():
    with connect() as c:
        try: return dict(c.execute("SELECT key,value FROM metadata").fetchall())
        except duckdb.Error: return {"data_kind":"unknown","snapshot":"unknown"}
def schema_map():
    allowed={"listings_clean","calendar_clean","reviews_clean","poi"}
    with connect() as c:
        return {t:{r[0]:r[1] for r in c.execute("DESCRIBE "+t).fetchall()} for t in allowed}
