import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    userid=session["user_id"]
    user = db.execute("SELECT * FROM users WHERE id = :id", id=userid)
    # Ensure id exists
    if len(user) != 1:
        return apology("invalid userid", 403)

    stonks = db.execute("SELECT * FROM stocks WHERE userid = :id", id=userid)
    #update value of the stonks and sum up value of stocks
    sum = 0
    for stonk in stonks:
        symbol = stonk['symbol']
        price = lookup(symbol)['price']
        db.execute("UPDATE stocks SET price = :price WHERE userid = :usid AND symbol = :symbol",
            usid=userid, symbol=symbol, price = price)
        sum += price * stonk['shares']
    stonks = db.execute("SELECT * FROM stocks WHERE userid = :id", id=userid)
    return render_template("index.html", user=user[0], stonks=stonks, stonk_sum=sum)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        stonk=lookup(request.form.get("symbol"))

        # Ensure symbol was submitted
        if not stonk:
            return apology("must provide valid symbol", 403)

        # Ensure shares was submitted as positive int
        try:
            shares = int(request.form.get("shares"))
            if not shares or shares <= 0:
                return apology("must give a positive integer number of shares", 403)
        except ValueError:
            return apology("must give a positive integer number of shares", 403)

        price = stonk['price']
        userid=session["user_id"]
        query = db.execute("SELECT * FROM users WHERE id = :id",
                    id=userid)
        # Ensure id exists
        if len(query) != 1:
            return apology("invalid userid", 403)

        cash = query[0]['cash']
        #checks that user can afford buy
        if shares * price > cash:
            return apology("price of purchase cannot exceed your current cash balance", 403)

        #records buy in history
        symbol=stonk['symbol']
        db.execute("INSERT INTO history (userid, symbol, shares, price) VALUES(:uid, :symbol, :shares, :price)",
            uid=userid, symbol=stonk['symbol'], shares=shares, price=price)
        #records buy in index (i.e. stocks db)
        holdings = db.execute("SElECT * FROM stocks WHERE userid = :id AND symbol = :symbol",
            id=userid, symbol=symbol)
        if (len(holdings) == 0):
            db.execute("INSERT INTO stocks (userid, symbol, shares) VALUES(:id, :sym, :shares)",
                id=userid, sym=symbol, shares=shares)
        elif (len(holdings) == 1):
            db.execute("UPDATE stocks SET shares = :updated WHERE userid = :usid AND symbol = :symbol",
                usid=userid, updated=holdings[0]['shares'] + shares, symbol=symbol)
        else:
            apology("repeat stocks in index", 403)

        left = cash - shares * price
        db.execute("UPDATE users SET cash = :left WHERE id = :usid", left=left, usid=userid)
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("buy.html")


@app.route("/check", methods=["GET"])
def check():
    """Return true if username available, else false, in JSON format"""
    username = request.args.get("username")
    matches = db.execute("SELECT * FROM users WHERE username = :uname", uname=username)
    if (len(username) > 0) and (len(matches) == 0):
        return jsonify(True)
    else:
        return jsonify(False)


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    histories=db.execute("SELECT * FROM history WHERE userid=:userid", userid=session["user_id"])
    return render_template("history.html", stonks=histories)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":

        # Ensure stock was submitted
        stock = request.form.get("stock")
        if not stock:
            return apology("must provide stock symbol", 403)
        res=lookup(stock)
        #return quote
        return render_template("quoted.html", result=res, name=res['name'],
            price=res['price'], symbol=res['symbol'])

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("quote.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # Forget any user_id (not sure if necessary)
    # session.clear()

    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        password = request.form.get("password")
        if not password:
            return apology("must provide password", 403)

        # Ensure password was confirmed
        confirmation = request.form.get("confirmation")
        if not confirmation or (confirmation != password):
            return apology("must provide a valid confirmation", 403)

        db.execute("INSERT INTO users (username, hash) VALUES(:un, :h)",
            un=request.form.get("username"), h=generate_password_hash(password))

        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    userid=session["user_id"]
    if request.method == "POST":
        # Ensure symbol was submitted
        symbol = request.form.get("symbol")
        stonks = db.execute("SELECT * FROM stocks WHERE userid = :id AND symbol = :symbol",
            id=userid, symbol=symbol)
        if not symbol or not stonks:
            return apology("must provide valid symbol", 403)
        if (len(stonks) > 1):
            return apology("index repeat error", 403)

        # Ensure shares was submitted as positive int
        try:
            shares = int(request.form.get("shares"))
            if not shares or shares <= 0:
                return apology("must give a positive integer number of shares", 403)
        except ValueError:
            return apology("must give a positive integer number of shares", 403)
        #checks user owns enough shares to sell
        if (shares > stonks[0]['shares']):
            return apology("you do not own that many shares of stock", 403)

        query = db.execute("SELECT * FROM users WHERE id = :id",
                    id=userid)
        # Ensure id exists
        if len(query) != 1:
            return apology("invalid userid", 403)

        #update history with sale (type = 1 for sale)
        price = lookup(symbol)['price']
        db.execute("INSERT INTO history (userid, symbol, shares, price, type)"
            "VALUES(:uid, :symbol, :shares, :price, :type)",
            uid=userid, symbol=symbol, shares=shares, price=price, type=1)

        #update stock holdings with sale
        holdings = db.execute("SELECT * FROM stocks WHERE userid = :id AND symbol =:symbol",
            id=userid, symbol=symbol)
        if (holdings[0]['shares'] > shares):
            db.execute("UPDATE stocks SET shares = :updated WHERE userid = :usid",
                updated=holdings[0]['shares'] - shares, usid=userid)
        if (holdings[0]['shares'] == shares):
            db.execute("DELETE FROM stocks WHERE userid = :usid AND symbol =:symbol", symbol=symbol, usid=userid)
        #update user cash
        payday= query[0]['cash'] + shares*price
        db.execute("UPDATE users SET cash = :updated WHERE id = :usid", updated=payday, usid=userid)
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        stonks = db.execute("SELECT * FROM stocks WHERE userid = :id", id=userid)
        return render_template("sell.html", stonks=stonks)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
