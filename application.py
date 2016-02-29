"""Copyright 2016 Mert Bora Alper <bora@boramalper.org>

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import os
from datetime import datetime, time as dttime
import time
from urllib.parse import quote
from collections import namedtuple

from flask import Flask, request, render_template, session, redirect, abort
from htmlmin.minify import html_minify
from passlib.hash import bcrypt
import sqlite3

app = Flask(__name__)

News = namedtuple("News", ["id", "title", "body", "created"])

time_slice = namedtuple("TimeSlice", ["begin", "end"])
librarian = namedtuple("Librarian", ["name", "surname", "e_mail"])
tt_entry = namedtuple("TimetableEntry", ["isoweekday", "shift", "librarians"])
interrupt_t = namedtuple("Interrupt", ["isoweekday", "shift", "explanation"])

db_conn = None

if __debug__:
    @app.after_request
    def minify(response):
        if response.content_type == "text/html; charset=utf-8":
            response.direct_passthrough = False
            response.set_data(html_minify(response.get_data(as_text=True)))

        return response


def my_render(template, **kwargs):
    return render_template("skeleton/skeleton.html",
                           username=session["username"] if "username" in session else None,
                           current="home" if template == "index" else template,
                           title="Home" if template == "index" else template.split("/")[-1].capitalize(),
                           content=render_template(template + "/index.html", **kwargs),
                           template=template,
                           scripts=list(filter(None, ["/static/scripts/{}/{}".format(template, scriptname)
                                                      # Check for non files, just in case...
                                                      if os.path.isfile(
                               "static/scripts/{}/{}".format(template, scriptname))
                                                      else None
                                                      for scriptname in os.listdir("static/scripts/" + template)]))
                           if os.path.isdir("static/scripts/" + template) else [],
                           styles=list(filter(None, ["/static/styles/{}/{}".format(template, stylename)
                                                     # Check for non files, just in case...
                                                     if os.path.isfile(
                               "static/styles/{}/{}".format(template, stylename))
                                                     else None
                                                     for stylename in os.listdir("static/styles/" + template)]))
                           if os.path.isdir("static/styles/" + template) else [])


index_wishbox_alerts = []
@app.route("/")
def index():
    res = my_render("index", news=get_news(3))
    index_wishbox_alerts.clear()
    return res


# convert it into SQLite format
def human_to_sqldate(dt):
    return time.strftime("%Y-%m-%d %H:%M", time.strptime(dt, "%d/%m/%Y %H:%M"))


# convert from SQLite to human
def sqldate_to_human(dt):
    return time.strftime("%d/%m/%Y %H:%M", time.strptime(dt, "%Y-%m-%d %H:%M"))


@app.route("/logout")
def logout():
    session.pop("username", None)
    return redirect("/")


def get_news(amount=0, date_format="%d %b, %A", include_body=False):
    cur = db_conn.cursor()

    cur.execute("SELECT id, title, created {} FROM news WHERE deleted = 0 ORDER BY created DESC{};"
                .format(", body" if include_body else '',
                        " LIMIT {}".format(amount) if amount else "")
                )

    # TODO: this if statement makes it terribly slow
    return [News(rn[0], rn[1],
                 rn[3] if len(rn) > 3 else None,
                 time.strftime(date_format, time.strptime(rn[2], "%Y-%m-%d %H:%M:%S.%f"))) for rn in cur.fetchall()]


news_add_news_alerts = []


@app.route("/news")
@app.route("/news/<news_id>")
def news(news_id=None):
    cur = db_conn.cursor()

    if news_id:
        cur.execute("SELECT id, title, created, body FROM news WHERE id=?;", (news_id,))
        new = cur.fetchone()
        new = News(new[0], new[1], new[3], sqldate_to_human(new[2][0:15]))  # 0:15 -> remove microseconds, and convert

        return my_render("news", new=new)
    else:
        res = my_render("news", news=get_news(), logged_in=True if "username" in session else False,
                        add_new_alerts=news_add_news_alerts)
        news_add_news_alerts.clear()
        return res


@app.route("/add-news", methods=["POST"])
def add_news():
    if "username" not in session:
        abort(401)

    print("REQ", request.form)

    title = request.form["title"]
    body = request.form["body"]
    created = datetime.today()

    cur = db_conn.cursor()
    cur.execute("INSERT INTO news (title, body, created) VALUES (?, ?, ?);", (title, body, created))

    db_conn.commit()

    news_add_news_alerts.append(("success", "Successfully added!"))

    return redirect("/news")


@app.route("/delete-news", methods=["POST"])
def delete_news():
    if "username" not in session:
        abort(401)

    cur = db_conn.cursor()
    cur.execute("DELETE FROM news WHERE id=?;", (request.form["id"],))
    db_conn.commit()

    news_add_news_alerts.append(("success", "Successfully deleted!"))
    return redirect("/news")


@app.route("/change-password", methods=["POST"])
def change_password():
    cur = db_conn.cursor()

    cur.execute("SELECT password FROM admins WHERE username=?", (session["username"],))
    current_password = cur.fetchone()[0]

    if not bcrypt.verify(request.form["password"], current_password):
        admin_change_password_alerts.append(("danger", "You entered your current password wrong."))
        return redirect("/admin")

    if request.form["new_password"] != request.form["confirm_new_password"]:
        admin_change_password_alerts.append(("danger", "Passwords don't match."))
        return redirect("/admin")

    new_password = bcrypt.encrypt(request.form["new_password"])
    cur.execute("UPDATE admins SET password=? WHERE username=?", (new_password, session["username"]))
    db_conn.commit()

    admin_change_password_alerts.append(("success", "Password successfully changed."))
    return redirect("/admin")


admin_login_alerts = []
admin_change_password_alerts = []
admin_interrupt_alerts = []


@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "GET":
        if "username" not in session:
            res = render_template("signin/index.html", alerts=admin_login_alerts)
            admin_login_alerts.clear()
            return res
        else:
            cur = db_conn.cursor()

            cur.execute(
                "SELECT name, student_id, author, title, \"e-mail\", comments, id FROM wishes ORDER BY created DESC;")
            wishes = cur.fetchall()

            res = my_render("admin",
                            change_password_alerts=admin_change_password_alerts,
                            interrupt_alerts=admin_interrupt_alerts,
                            news=get_news(),
                            wishes=wishes,
                            username=session["username"])

            admin_change_password_alerts.clear()
            admin_interrupt_alerts.clear()

            return res

    else:
        if "username" not in session:
            username = request.form["username"].lower()
            password = request.form["password"]

            cur = db_conn.cursor()

            cur.execute("SELECT password FROM admins WHERE username=?", (username,))
            result = cur.fetchone()

            if not result:
                admin_login_alerts.append("User doesn't exist.")
            elif not bcrypt.verify(password, result[0]):
                admin_login_alerts.append("Password is wrong.")
            else:
                session["username"] = username
        else:
            admin_login_alerts.append("You're already logged in as {}".format(session["username"]))

        return redirect("/admin")


@app.route("/about/mission")
def about_mission():
    return my_render("about/mission")


@app.route("/about/contact")
def about_contact():
    return my_render("about/contact")


def initialize():
    global db_conn

    db_conn = sqlite3.connect("data/database.sqlite3", check_same_thread=False)

    with open("secret_key", "rb") as f:
        app.secret_key = f.read()


def finalize():
    db_conn.close()


if __name__ == "__main__":
    initialize()

    app.jinja_env.globals.update(percent_encode=quote)

    try:
        if __debug__:
            print("Running in debugging mode!")
            app.run(host='127.0.0.1', debug=True)
        else:
            app.config.update(PROPAGATE_EXCEPTIONS=True)
            app.run(host='0.0.0.0', debug=False)
    finally:
        finalize()
