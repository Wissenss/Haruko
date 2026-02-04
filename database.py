import datetime

import sqlite3

import environment

# utility class / functions to connect with sqlite database

# pool object should be used by the application to obtain connections
# remember to always release back the connection to the pool 

def create_connection() -> sqlite3.Connection:
    return sqlite3.connect(environment.DATABASE_PATH)

DB_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S" 

def format_db_date(date : datetime.datetime) -> str:
    if date == None:
        return None
    
    return date.strftime(DB_TIMESTAMP_FORMAT)

def parse_db_date(date_str : str) -> datetime.datetime:
    if date_str == None:
        return None 

    return datetime.datetime.strptime(date_str, DB_TIMESTAMP_FORMAT)

class ConnectionPool:
    pool_min_size : int = 10
    pool : list[(bool, sqlite3.Connection)] = []

    @classmethod
    def init(cls):
        for _ in range(cls.pool_min_size):
            cls.pool.append((True, create_connection()))
 
    @classmethod
    def finish(cls):
        for i, t in enumerate(cls.pool):
            t[1].close()

        cls.pool.clear()

    @classmethod
    def get(cls) -> sqlite3.Connection:
        for i, t in enumerate(cls.pool):
            if t[0] == True:
                cls.pool[i] = (False, t[1])
                return t[1]
            
        new_conn = create_connection()

        cls.pool.append((False, new_conn))

        return new_conn

    @classmethod
    def release(cls, connection : sqlite3.Connection):
        for i, t in enumerate(cls.pool):
            if t[1] == connection:
                if connection.in_transaction:
                    connection.rollback()

                cls.pool[i] = (True, t[1]) 

                if len(cls.pool) >= cls.pool_min_size:
                    t[1].close()
                    cls.pool.pop(i)

    @classmethod
    def get_pool_size(cls) -> int:
        return len(cls.pool)
    
    @classmethod
    def get_pool_available_connections(cls) -> int:
        return len([c for c in cls.pool if c[0] == True])
    
    @classmethod
    def get_pool_occupied_connections(cls) -> int:
        return len([c for c in cls.pool if c[0] == False])

    @classmethod
    def dump_status(cls):
        print(f"---------------------------------")
        print(f"connection pool status")
        print(f"pool size: {cls.get_pool_size()}")
        print(f"occupied connections: {cls.get_pool_occupied_connections}")
        print(f"available connections: {cls.get_pool_available_connections}")
        print(f"---------------------------------")

if __name__ == "__main__":
    ConnectionPool.dump_status()
    ConnectionPool.init()
    ConnectionPool.dump_status()
    con1 = ConnectionPool.get()
    con2 = ConnectionPool.get()
    con3 = ConnectionPool.get()
    con4 = ConnectionPool.get()
    con5 = ConnectionPool.get()
    con6 = ConnectionPool.get()
    con7 = ConnectionPool.get()
    con8 = ConnectionPool.get()
    con9 = ConnectionPool.get()
    con10 = ConnectionPool.get()
    con11 = ConnectionPool.get()
    ConnectionPool.dump_status()
    ConnectionPool.release(con2)
    ConnectionPool.dump_status()