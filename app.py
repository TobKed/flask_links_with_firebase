import os
from urllib.parse import quote

from flask import Flask, flash, redirect, url_for, render_template, request
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession


HOST_PORT = int(os.getenv("HOST_PORT", "80"))
HOST = os.getenv("HOST", "0.0.0.0")
SECRET_KEY = os.getenv("SECRET_KEY", "random string")
SQLALCHEMY_DATABASE_URI = os.getenv(
    "SQLALCHEMY_DATABASE_URI", "sqlite:///links.sqlite3"
)
GOOGLE_APPLICATION_CREDENTIALS = os.getenv(
    "GOOGLE_APPLICATION_CREDENTIALS", "service-account-file.json"
)
STATS_DURATION = 365

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = SQLALCHEMY_DATABASE_URI
app.config["SECRET_KEY"] = SECRET_KEY

db = SQLAlchemy(app)
migrate = Migrate(app, db)

scopes = ["https://www.googleapis.com/auth/firebase"]
credentials = service_account.Credentials.from_service_account_file(
    GOOGLE_APPLICATION_CREDENTIALS, scopes=scopes
)


class Links(db.Model):
    id = db.Column("link_id", db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    counter = db.Column(db.Integer(), default=0)
    url = db.Column(db.String(2048), nullable=False)

    def __init__(self, name, url, counter=0):
        self.name = name
        self.counter = counter
        self.url = url

    def __repr__(self):
        return f"Links(name={self.name}, counter={self.counter}, url={self.url})"


@app.route("/")
def show_all():
    return render_template("show_all.html", links=Links.query.all())


@app.route("/visit/<link_id>")
def visit(link_id):
    link = Links.query.filter(Links.id == int(link_id)).first()
    if link is not None:
        url = link.url
        if url.find("http://") != 0 and url.find("https://") != 0:
            url = "http://" + url
        link.counter += 1
        db.session.commit()
        return redirect(url)
    return f"Link {link_id} not found", 404


@app.route("/stats/<link_id>")
def statistics(link_id):
    link = Links.query.filter(Links.id == int(link_id)).first()
    if not link:
        return f"Link {link_id} not found", 404

    url = quote(link.url, safe="")
    authed_session = AuthorizedSession(credentials)
    response = authed_session.get(
        f"https://firebasedynamiclinks.googleapis.com/v1/"
        f"{url}/linkStats?durationDays={STATS_DURATION}"
    )

    try:
        response.raise_for_status()
    except Exception as e:
        return str(e), 400
    response_json = response.json()
    count = sum(int(i["count"]) for i in response_json.get("linkEventStats", []) if i["event"] == "CLICK")
    return {"count": count, "status_code": response.status_code, "response_json": response_json}, response.status_code


@app.route("/new", methods=["GET", "POST"])
def new():
    if request.method == "POST":
        if not request.form["name"] or not request.form["url"]:
            flash("Please enter all the fields", "error")
        else:
            link = Links(
                name=request.form["name"],
                url=request.form["url"],
            )
            db.session.add(link)
            db.session.commit()
            app.logger.info("Record was successfully added: %s", link)
            flash("Record was successfully added")
            return redirect(url_for("show_all"))
    return render_template("new.html")


if __name__ == "__main__":
    db.create_all()
    app.run(host=HOST, port=HOST_PORT)
