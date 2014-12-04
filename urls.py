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

    def rm(self, rowid):
        self.cur.execute('delete from urls where id = ?', (rowid,))
        count = self.cur.rowcount
        self.conn.commit()
        return count

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


class ConvertID:
    """Convert between URL IDs and database row IDs"""

    ROUTE_RULE = 're:[0-9a-f]+'
    OFFSET = 0xbea0

    @staticmethod
    def to_urlid(rowid):
        return '%x' % (rowid + ConvertID.OFFSET)

    @staticmethod
    def to_rowid(urlid):
        return int(urlid, 16) - ConvertID.OFFSET


BASE_TEMPLATE = """<!DOCTYPE html>
<meta charset=utf-8>
<title>URL shortener</title>
<h1>2b’s URL shortener</h1>"""

INDEX_TEMPLATE = BASE_TEMPLATE + """
<p>Use the <a href='javascript:{{!script}}'>Shorten!</a> bookmarklet to shorten an URL,
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
  <tr><th>ID<th>URL<th>dups<th>gets<th>created on<th>rm!</tr>
  % for u in urls:
  <tr><td>{{u[0]}}<td><a href={{short(u[0])}}>{{u[1]}}</a><td>{{u[3]}}<td>{{u[4]}}<td>{{u[2]}}<td><a href={{rm(u[0])}}>✗</a></tr>
  % end
</table>
% else:
<p>No URLs saved yet.
% end
<p><a href={{index}}>Home</a>
"""


def make_url(name, **args):
    return default_app().get_url(name, **args)


def make_abs_url(name, **args):
    return '%s://%s' % request.urlparts[:2] + make_url(name, **args)


@route('/', name='index')
def index():
    script = 'window.location="' + make_abs_url('add', url='') + \
        '"+encodeURIComponent(window.location);'
    add = make_abs_url('add', url='<i>&lt;URL></i>')
    show = make_url('show')
    return template(INDEX_TEMPLATE, locals())


@route('/add/<url:path>', name='add')
def add(url):
    if not re.match(r'^(f|ht)tps?://', url):
        abort(400, "Invalid URL format")
    s = Storage()
    rowid = s.add(url)
    short_url = make_abs_url('get', urlid=ConvertID.to_urlid(rowid))
    return template(ADD_TEMPLATE, locals())


@route('/rm/<rowid:int>', name='rm')
def rm(rowid):
    s = Storage()
    result = s.rm(rowid)
    if not result:
        abort(404, "No such URL")
    ref = request.environ.get('HTTP_REFERER')
    redirect(ref or make_url('show'))


@route('/<urlid:%s>' % ConvertID.ROUTE_RULE, name='get')
def get(urlid):
    s = Storage()
    url = s.get(ConvertID.to_rowid(urlid))
    if url is None:
        abort(404, "No such URL ID")
    redirect(tob(url))


@route('/show', name='show')
def show_page():
    s = Storage()
    urls = s.urls()
    rm = lambda rowid: make_url('rm', rowid=rowid)
    short = lambda rowid: make_url('get', urlid=ConvertID.to_urlid(rowid))
    index = make_url('index')
    return template(SHOW_TEMPLATE, locals())


application = default_app()


if __name__ == '__main__':
    run(host='0.0.0.0', port=8080, debug=True)
