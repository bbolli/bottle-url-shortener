# encoding: utf-8

import os
import sqlite3
import re

from bottle import (
    abort,
    default_app,
    redirect,
    request,
    response,
    route,
    run,
    template,
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

    def urls(self):
        self.cur.execute('select * from urls order by id')
        return self.cur.fetchall()


OFFSET = 0xbea0

BASE_TEMPLATE = """<!DOCTYPE html>
<meta charset=utf-8>
<title>URL shortener</title>
<h1>2b’s URL shortener</h1>"""

INDEX_TEMPLATE = BASE_TEMPLATE + """
<p>Use the {{!bm}} bookmarklet to shorten an URL,
or make a HTTP GET request to <tt>{{!add}}</tt>.
<p><a href='{{show}}'>Show</a> all shortened URLs.
"""

ADD_TEMPLATE = BASE_TEMPLATE + """
<p>The URL <i>{{url}}</i> was shortened to
<a href='{{short_url}}'>{{short_url}}</a>.
"""

SHOW_TEMPLATE = BASE_TEMPLATE + """
% if urls:
<table>
  <tr><th>ID<th>URL<th>dups<th>gets<th>created on</tr>
  % for u in urls:
  <tr><td>{{u[0]}}<td>{{u[1]}}<td>{{u[3]}}<td>{{u[4]}}<td>{{u[2]}}</tr>
  % end
</table>
% else:
<p>No URLs saved yet.
% end
"""


def make_url(name, **args):
    return default_app().get_url(name, **args)


def make_abs_url(name, **args):
    return '%s://%s' % request.urlparts[:2] + make_url(name, **args)


@route('/')
def index():
    script = 'window.location="' + make_abs_url('add', url='') + \
        '"+encodeURIComponent(window.location);'
    bm = '''<a href='javascript:%s'>%s</a>''' % (script, "Shorten!")
    add = make_abs_url('add', url='<i>&lt;URL></i>')
    show = make_url('show')
    return template(INDEX_TEMPLATE, locals())


@route('/add/<url:path>', name='add')
def add(url):
    if not re.match(r'^(f|ht)tps?://', url):
        abort(400, "Invalid URL format")
    s = Storage()
    rowid = s.add(url)
    urlid = '%x' % (rowid + OFFSET)
    short_url = make_abs_url('get', urlid=urlid)
    return template(ADD_TEMPLATE, locals())


@route('/<urlid:re:[0-9a-f]+>', name='get')
def get(urlid):
    s = Storage()
    rowid = int(urlid, 16) - OFFSET
    url = s.get(rowid)
    if url is None:
        abort(404, "No such URL ID")
    redirect(tob(url))


@route('/show', name='show')
def show_page():
    s = Storage()
    urls = s.urls()
    return template(SHOW_TEMPLATE, locals())


application = default_app()


if __name__ == '__main__':
    run(host='0.0.0.0', port=8080, debug=True)
