import sqlite3
from contextlib import closing
import os

db_name = r"db\airibotdb.db"

def insert(table: str, key: tuple = (), value: tuple = ()):
    query = f"INSERT INTO {table} "
    if len(key) > 0:
        if not len(key) == len(value):
            raise Exception("key and value length not same")
        query += f"({','.join(key)  if isinstance(key, tuple) else key}) "
    query += f"VALUES ({__create_param(count=len(value))}) "
    __query(query, value)

def select(table, columns: tuple[str] | str = ("*"), where: dict[str:str] = None, operator: tuple = None, conditions: tuple = None):
    query = f"SELECT {','.join(columns) if isinstance(columns, tuple) else columns} FROM {table}" + __create_where(where, operator)
    return __query(query, conditions)

def update(table, columns: dict[str, any], where: dict[str:str] = None, operator: tuple = None, conditions: tuple = None):
    query = f"UPDATE {table} SET " + (' '.join(f'{key} = ?, ' for key in columns.keys()))[:-2] + __create_where(where, operator)
    params = tuple(columns.values()) + conditions
    return __query(query, params)

def delete(table, where: dict[str:str] = None, operator: tuple = None, conditions: tuple = None):
    query = f"DELETE FROM {table} " + __create_where(where, operator)
    return __query(query, conditions)

def raw(sql):
    return __query(sql)

def __create_param(count: int = 0):
    t = (f"?, " * count)
    return t[:-2]

def __create_where(where: dict[str:str] = None, operator: tuple = None) -> str | None:
    if where is None:
        return ""
    return " WHERE " + ''.join([f"{key}{where[key]}? {value} " for key, value in zip(where.keys(), ('',) if operator is None else operator + ('',))])

def __query(sql, args: tuple = None):
    with closing(sqlite3.connect(db_name)) as con, con,  \
            closing(con.cursor()) as cur:
        print(f"================================")
        print(f"query  :: {sql}\nparams :: {args}")
        if args is None:
            cur.execute(sql)
        else:
            cur.execute(sql, args if isinstance(args, tuple) else (args,))
        print(f"affected rows :: {cur.rowcount}")

        result = cur.fetchall()
        if cur.description is not None:
            columns = [item[0] for item in cur.description]
            result = [{k: v for k, v in zip(columns, r)} for r in result]
        print(f"rows count    :: {len(result)}")
        print(f"================================")

        return (cur.rowcount, len(result), result)
    
def execute_script(script: str) -> tuple:
    sql_script = ''
    if not os.path.exists(os.path.dirname(script)):
        sql_script = script
    else:
        with open(script, 'r') as sql_file:
            sql_script = sql_file.read()

    with closing(sqlite3.connect(db_name)) as con, con,  \
            closing(con.cursor()) as cur:
        cur.executescript(sql_script)
        result = cur.fetchall()

        return (cur.rowcount, len(result), result)