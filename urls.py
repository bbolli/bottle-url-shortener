# encoding: utf-8

import os
import sqlite3
import re

from flask import (
    Flask,
    abort,
    redirect,
    render_template_string,
    request,
    url_for,
)

app = Flask(__name__)


class Storage:
    db_file = os.path.join(os.path.split(os.path.abspath(__file__))[0], 'urls.db')

    def __init__(self):
        self.conn = sqlite3.connect(self.db_file, detect_types=sqlite3.PARSE_DECLTYPES)
        self.conn.row_factory = sqlite3.Row
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
            rowid = self.cur.fetchone()['id']
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
        return result['url']

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
<p>Use the <a href='javascript:{{ script | safe }}'>Shorten!</a> bookmarklet to shorten an URL,
or make a HTTP GET request to <tt>{{add}}<i>&lt;URL></i></tt>.
<p><a href='{{show}}'>Show</a> all shortened URLs.
"""

ADD_TEMPLATE = BASE_TEMPLATE + """
<p>The URL <i>{{url}}</i> was shortened to
<a href='{{short_url}}'>{{short_url}}</a>.
"""

SHOW_TEMPLATE = BASE_TEMPLATE + """
{% if urls: %}
<table>
  <tr><th>ID<th>URL<th>dups<th>gets<th>created on<th>rm!</tr>
  {% for u in urls: %}
  <tr><td>{{ link('get', u.id) }}<td><a href={{ link('get', u.id) }}>{{u.url}}</a><td>{{u.dups}}<td>{{u.gets}}<td>{{u.added_on}}<td><a href={{ link('rm', u.id) }}>⌫</a></tr>
  {% endfor %}
</table>
{% else: %}
<p>No URLs saved yet.
{% endif %}
<p><a href={{ link('index') }}>Home</a>
"""


@app.route('/')
def index():
    add = url_for('add', _external=True, url='')
    script = 'window.location="' + add + \
        '"+encodeURIComponent(window.location);'
    show = url_for('show')
    return render_template_string(INDEX_TEMPLATE, **locals())


@app.route('/add/<path:url>')
def add(url):
    if not re.match(r'^(f|ht)tps?://', url):
        abort(400, "Invalid URL format")
    s = Storage()
    rowid = s.add(url)
    short_url = url_for('get', _external=True, urlid=ConvertID.to_urlid(rowid))
    return render_template_string(ADD_TEMPLATE, **locals())


@app.route('/rm/<urlid>')
def rm(urlid):
    s = Storage()
    result = s.rm(ConvertID.to_rowid(urlid))
    if not result:
        abort(404, "No such URL")
    return redirect(request.referrer or url_for('show'))


@app.route('/<urlid>')
def get(urlid):
    s = Storage()
    url = s.get(ConvertID.to_rowid(urlid))
    if url is None:
        abort(404, "No such URL ID")
    return redirect(url)


def link(fn, rowid=None):
    if rowid is not None:
        return url_for(fn, urlid=ConvertID.to_urlid(rowid))
    return url_for(fn)


@app.route('/show')
def show():
    urls = Storage().urls()
    return render_template_string(SHOW_TEMPLATE, link=link, urls=urls)
