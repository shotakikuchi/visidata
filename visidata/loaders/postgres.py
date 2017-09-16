from visidata import *

import psycopg2


option('dbname', 'data_store_api', '')
option('dbuser', 'jenkins', '')
option('dbpasswd', '', '')


def codeToType(type_code):
    tname = psycopg2._psycopg.string_types[type_code].name
    if 'INTEGER' in tname:
        return int
    if 'STRING' in tname:
        return str
    return anytype


def openurl_postgres(url):
    conn = psycopg2.connect(
                user=options.dbuser,
                dbname=options.dbname,
                host=url.hostname,
                port=url.port,
                password=options.dbpasswd)

#    conn.autocommit = True

    return PgTablesSheet(options.dbname+"_tables", sql=SQL(conn))


class SQL:
    def __init__(self, conn):
        self.conn = conn

    def cur(self, qstr):
        randomname = ''.join(random.choice(string.ascii_uppercase) for _ in range(6))
        cur = self.conn.cursor(randomname)
        cur.execute(qstr)
        return cur

    @async
    def query_async(self, qstr, callback=None):
        with self.cur(qstr) as cur:
            callback(cur)
            cur.close()


def cursorToColumns(cur):
    cols = []
    for i, coldesc in enumerate(cur.description):
        c = ColumnItem(coldesc.name, i, type=codeToType(coldesc.type_code))
        cols.append(c)
    return cols


# rowdef: (table_name, ncols)
class PgTablesSheet(Sheet):
    nKeys = 1
    commands = [
        Command(ENTER, 'vd.push(PgTable(name+"."+cursorRow[0], cursorRow[0], sql=sql))', 'open this table'),
    ]

    def reload(self):
        qstr = "SELECT table_name, COUNT(column_name) AS ncols FROM information_schema.columns WHERE table_schema = 'public' GROUP BY table_name"

        with self.sql.cur(qstr) as cur:
            self.nrowsPerTable = {}

            self.rows = [cur.fetchone()]
            self.columns = cursorToColumns(cur)
            self.addColumn(Column('nrows', type=int, getter=lambda r,self=self: self.getRowCount(r[0])))

            for r in cur:
                self.addRow(r)

    def setRowCount(self, cur):
        result = cur.fetchall()
        tablename = result[0][0]
        self.nrowsPerTable[tablename] = result[0][1]

    def getRowCount(self, tablename):
        if tablename not in self.nrowsPerTable:
            thread = self.sql.query_async("SELECT '%s', COUNT(*) FROM %s" % (tablename, tablename), callback=self.setRowCount)
            self.nrowsPerTable[tablename] = thread

        return self.nrowsPerTable[tablename]


# rowdef: tuple(all columns in table)
class PgTable(Sheet):
    @async
    def reload(self):
        with self.sql.cur("SELECT * FROM " + self.source) as cur:
            self.rows = [cur.fetchone()]
            self.columns = cursorToColumns(cur)
            for r in cur:
                self.addRow(r)


addGlobals(globals())