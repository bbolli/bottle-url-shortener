# encoding: utf-8

import os
import sqlite3

from bottle import (
    abort,
    redirect,
    request,
    response,
    route,
    run,
    tob
)


class Storage(object):
    db_file = os.path.join(os.path.split(os.path.abspath(__file__))[0], 'urls.db')

    def __init__(self):
        self.conn = sqlite3.connect(self.db_file, detect_types=sqlite3.PARSE_DECLTYPES)
        self.cur = self.conn.cursor()
        self.cur.execute('''create table if not exists urls (
            id integer primary key not null,
            url text unique not null,
            added_on timestamp not null,
            dups int not null,
            gets int not null
        )''')

    def add(self, url):
        try:
            self.cur.execute('insert into urls (url, added_on, dups, gets)'
                ' values (?, datetime("now"), 0, 0);', (url,)
            )
            rowid = self.cur.lastrowid
        except sqlite3.IntegrityError:
            self.cur.execute('select id from urls where url = ?', (url,))
            rowid = self.cur.fetchone()[0]
            self.cur.execute('update urls set dups = dups + 1 where id = ?', (rowid,))
        self.conn.commit()
        return rowid

    def get(self, rowid):
        self.cur.execute('select url from urls where id = ?', (rowid,))
        result = self.cur.fetchone()
        if result is None:
            return None
        self.cur.execute('update urls set gets = gets + 1 where id = ?', (rowid,))
        self.conn.commit()
        return result[0]


OFFSET = 0xbea0


@route('/add/<url:path>')
def add(url):
    s = Storage()
    rowid = s.add(url)
    urlid = '%x' % (rowid + OFFSET)
    response.content_type = 'text/plain'
    return '%s://%s%s%s\n' % (request.urlparts[0], request.urlparts[1],
        request.script_name, urlid
    )


@route('/<urlid:re:[0-9a-f]+>')
def get(urlid):
    s = Storage()
    rowid = int(urlid, 16) - OFFSET
    url = s.get(rowid)
    if url is None:
        abort(404, "No such URL ID")
    redirect(tob(url))


if __name__ == '__main__':
    run(host='0.0.0.0', port=8080, debug=True)
