"""Positive allowlists, resolved columns, bounded read-only execution."""
import threading
import sqlglot
from sqlglot import exp
from sqlglot.optimizer.qualify import qualify
from src.database.connection import connect,schema_map
ALLOWED_FUNCTIONS={"COUNT","SUM","AVG","MIN","MAX","MEDIAN","ROUND","COALESCE","NULLIF",
 "CAST","TRY_CAST","ABS","LOWER","UPPER","LENGTH","TRIM","ROW_NUMBER","RANK","DENSE_RANK",
 "LAG","LEAD","DATE_TRUNC","EXTRACT","DATE_DIFF","STDDEV","STDDEV_SAMP","VARIANCE",
 "TIMESTAMP_TRUNC","PERCENTILE_CONT","QUANTILE_CONT","ARRAY_AGG","CASE","IF","AND","OR",
 "GREATEST","LEAST"}
class SQLValidationError(ValueError):pass
def validate_select_sql(sql,max_rows=200,schema=None):
    if not isinstance(sql,str) or len(sql)>20000:raise SQLValidationError("Invalid or oversized SQL")
    try:
        nodes=sqlglot.parse(sql,read="duckdb")
        if len(nodes)!=1 or not isinstance(nodes[0],exp.Select):raise SQLValidationError("One SELECT statement required")
        tree=nodes[0]
        for node in tree.walk():
            if node.key in {"command","insert","update","delete","create","drop","alter","copy",
                            "attach","detach","pragma","into","transaction","grant","set","use"}:
                raise SQLValidationError("Forbidden operation")
            if isinstance(node,exp.Func):
                name=node.name.upper() if isinstance(node,exp.Anonymous) else node.sql_name().upper()
                if name not in ALLOWED_FUNCTIONS:raise SQLValidationError("Function not allowed: "+name)
            if isinstance(node,exp.Table):
                if not isinstance(node.this,exp.Identifier) or node.db or node.catalog:
                    raise SQLValidationError("External or qualified tables are forbidden")
        schema=schema or schema_map()
        ctes={n.alias_or_name for n in tree.find_all(exp.CTE)}
        for t in tree.find_all(exp.Table):
            if t.name not in schema and t.name not in ctes:raise SQLValidationError("Unknown table: "+t.name)
        qualified=qualify(tree.copy(),dialect="duckdb",schema=schema,infer_schema=False,
                          validate_qualify_columns=True,allow_partial_qualification=False)
        # An outer cap also limits grouped and already-limited queries.
        return "SELECT * FROM ("+qualified.sql(dialect="duckdb")+") AS bounded_result LIMIT "+str(int(max_rows))
    except SQLValidationError:raise
    except Exception as e:raise SQLValidationError("SQL could not be resolved against the approved schema") from e
def execute_sql(sql,timeout_seconds=5):
    safe=validate_select_sql(sql)
    with connect() as c:
        timer=threading.Timer(timeout_seconds,c.interrupt)
        timer.daemon=True;timer.start()
        try:return safe,c.execute(safe).fetchdf()
        finally:timer.cancel()
