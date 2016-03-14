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
from datetime import datetime
import time
from collections import namedtuple
import hashlib
import binascii
from uuid import uuid4
import shutil

from flask import Flask, request, render_template, session, redirect, abort, url_for
from htmlmin.minify import html_minify
from passlib.hash import bcrypt
import sqlite3

app = Flask(__name__)

News = namedtuple("News", ["id", "title", "body", "created"])

db_conn = None

if not __debug__:
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
                           title="Home" if template == "index" else kwargs["title"] if "title" in kwargs else template.split("/")[-1].capitalize(),
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


@app.route("/")
def index():
    res = my_render("index", news=get_news(3))
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

    cur.execute("SELECT id, title, created {} FROM news WHERE is_deleted = 0 ORDER BY created DESC{};"
                .format(", body" if include_body else '',
                        " LIMIT {}".format(amount) if amount else "")
                )

    # TODO: this if statement makes it terribly slow
    return [News(rn[0], rn[1],
                 rn[3] if len(rn) > 3 else None,
                 time.strftime(date_format, time.strptime(rn[2], "%Y-%m-%d %H:%M:%S.%f"))) for rn in cur.fetchall()]


@app.route("/news")
def news():
    res = my_render("news", news=get_news(), logged_in=True if "username" in session else False)
    return res


@app.route("/news/<int:news_id>", methods=["GET"])
def news_id(news_id):
    cur = db_conn.cursor()
    cur.execute("SELECT id, title, created, body FROM news WHERE id = ? AND is_deleted = 0;", (news_id,))
    new = cur.fetchone()
    cur.close()

    if new is None:
        return redirect("/news")

    new = News(new[0], new[1], new[3], sqldate_to_human(new[2][0:15]))  # 0:15 -> remove microseconds, and convert

    return my_render("news_item", new=new, title=new.title, is_loggedin=True if "username" in session else False)


@app.route("/news", methods=["PUT"])
def create_news_item():
    if "username" not in session:
        abort(401)

    cur = db_conn.cursor()
    cur.execute("INSERT INTO news (title, body, created, uuid) VALUES (?, ?, ?, ?);", (request.form["title"],
                                                                                       request.form["body"],
                                                                                       datetime.today(),
                                                                                       request.form["news_uuid"]))

    cur.execute("SELECT id FROM news WHERE is_deleted = 0 ORDER BY created DESC;")
    news_id = cur.fetchone()[0]

    cur.close()
    db_conn.commit()

    return "/news/" + str(news_id)


@app.route("/news/<int:news_id>", methods=["PUT"])
def replace_news_item(news_id):
    if "username" not in session:
        abort(401)

    cur = db_conn.cursor()
    cur.execute("UPDATE news SET title = ?, body = ? WHERE id = ?;", (request.form["title"], request.form["body"], news_id))
    cur.close()
    db_conn.commit()

    return "/news/" + str(news_id)


@app.route("/news/<int:news_id>", methods=["DELETE"])
def delete_news(news_id):
    if "username" not in session:
        abort(401)

    cur = db_conn.cursor()
    cur.execute("UPDATE news SET is_deleted = 1 WHERE id = ?", (news_id,))
    cur.execute("SELECT uuid FROM news WHERE id = ?", (news_id,))
    uuid = cur.fetchone()[0]
    cur.close()
    shutil.rmtree("static/news_assets/" + uuid, ignore_errors=True)
    db_conn.commit()

    return "okay"


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


@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "GET":
        if "username" not in session:
            res = render_template("signin/index.html", alerts=admin_login_alerts)
            admin_login_alerts.clear()
            return res
        else:
            res = my_render("admin",
                            change_password_alerts=admin_change_password_alerts,
                            news=get_news(),
                            username=session["username"])

            admin_change_password_alerts.clear()

            return res

    else:
        print("admin", request.form)
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


def sha512(stream):
    engine = hashlib.sha512()
    stream.seek(0)

    if hasattr(stream, "getvalue"):
        value = stream.getvalue()
    elif hasattr(stream, "read"):
        value = stream.read()
    else:
        raise Exception("Couldn't read file stream for SHA512")

    engine.update(value)
    return binascii.hexlify(engine.digest()).upper().decode("ascii")


@app.route("/upload-image", methods=["POST"])
def upload_image():
    if "username" not in session:
        abort(401)

    image = request.files["image"]
    if image:
        directory = request.form["news_uuid"]
        path = os.path.join("static/news_assets", directory)

        filename = str(uuid4()) + "." + image.filename.rsplit('.', 1)[1]

        os.makedirs(path, exist_ok=True)
        image.save(os.path.join(path, filename))

        return "/static/news_assets/" + directory + "/" + filename
    else:
        return abort(500)


@app.route("/editor/<int:news_id>")
def editor_id(news_id):
    cur = db_conn.cursor()
    cur.execute("SELECT id, title, body, uuid FROM news WHERE id=? AND is_deleted=0;", (news_id,))
    res = cur.fetchone()
    cur.close()

    if res is None:
        return "no news found with id " + str(news_id)

    id, title, body, uuid = res

    title = title.replace('"', '\\"')
    body = body.replace('"', '\\"').replace('\n', '\\n')

    return render_template("editor/index.html", id=id, title=title, body=body, uuid=uuid)


@app.route("/editor")
def editor():
    return render_template("editor/index.html", id=0, title='', body='', uuid=uuid4())


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

    # app.jinja_env.globals.update(percent_encode=quote)

    try:
        if not __debug__:
            print("Running in debugging mode!")
            app.run(host='127.0.0.1', debug=True)
        else:
            app.config.update(PROPAGATE_EXCEPTIONS=True)
            app.run(host='0.0.0.0', debug=False)
    finally:
        finalize()
