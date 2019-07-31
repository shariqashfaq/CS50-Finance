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
    """Show portfolio of stocks"""

    #Group all same stocks together given user id
    rows = db.execute("SELECT symbol, SUM(quantity) FROM transactions WHERE id= :id GROUP BY symbol", id = session["user_id"])

    #check is shares held are 0, if so delete from list
    #for i in range(len(rows)):
        #if rows[i]["SUM(quantity)"]==0 :
            #rows.remove(rows[i])




    #Get values of the different stock holdings and add it as a column in rows
    for row in rows:
        row["value"] = float(lookup(row["symbol"])["price"])*float(row["SUM(quantity)"])

    #total value of all stock

    def stocksum():
        stockval = 0
        for row in rows:
            stockval += row["value"]

        return stockval


    #Get users funds
    cash_rows = db.execute("SELECT * FROM users WHERE id = :id", id = session["user_id"])
    cash = cash_rows[0]["cash"]


    return render_template("index.html", rows=rows, cash=cash, total_stock_value = stocksum(), portfolio = stocksum() + cash)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    rows = db.execute("SELECT * FROM users WHERE id = :id",
                          id = session["user_id"])

    if request.method == "GET":

        return render_template("buy.html", funds = rows[0]["cash"])

    #request is made through POST request
    else:

        #Check if stock symbol and quantity fields are filled
        if not request.form.get("stk-symbol"):
            return apology("must provide stock symbol", 403)

        elif not request.form.get("num-shares"):
            return apology("must provide quantity", 403)

        #Check to see if user has enough funds
        elif rows[0]["cash"] < float(lookup(request.form.get("stk-symbol"))["price"])*float(request.form.get("num-shares")):
            return apology("ride slow homie", 403)

        #Enter into transactions database
        else:
            trans_id = db.execute("INSERT INTO transactions (id, type, symbol, company, price, quantity, tranvalue) VALUES (:id, :type, :symbol, :company, :price, :quantity, :tranvalue)",
                        id = session["user_id"] ,type = "buy", symbol = lookup(request.form.get("stk-symbol"))["symbol"], company = lookup(request.form.get("stk-symbol"))["name"],
                        price = lookup(request.form.get("stk-symbol"))["price"], quantity = request.form.get("num-shares"), tranvalue = float(lookup(request.form.get("stk-symbol"))["price"])*float(request.form.get("num-shares")))

            #update cash
            tran_rows = db.execute("SELECT * FROM transactions WHERE transid= :transid", transid = trans_id)
            newcash = rows[0]["cash"] - tran_rows[0]["tranvalue"]
            db.execute("UPDATE users SET cash = :newcash  WHERE id= :id", newcash = newcash, id = session["user_id"])

            return redirect("/history")

@app.route("/check", methods=["GET"])
def check():
    """Return true if username available, else false, in JSON format"""
    #check if username is available
    rows = db.execute("SELECT * FROM users WHERE username = :username",
                         username=request.args.get("username"))
    if len(rows) > 0:
        return jsonify(False)
    else:
        return jsonify(True)


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    #Group transaction for user together given user id and reverse list
    rows = db.execute("SELECT * FROM transactions WHERE id= :id", id = session["user_id"])
    rows.reverse()


    return render_template("transaction.html", rows=rows)


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

    #User accesses route via GET method from index
    if request.method == "GET":
        return render_template("quote.html")

    else:
        return render_template("price.html", price = lookup(request.form.get("symbol"))["price"])



@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    #User clicks /register route via GET method from login.html
    if request.method == "GET":

        return render_template("register.html")

    #User accesses /register via POST method from register.html
    if request.method == "POST":

        #Check if username and password fields are filled
        if not request.form.get("username"):
            return apology("must provide username", 403)

        elif not request.form.get("password"):
            return apology("must provide password", 403)

        #check if username is available
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                         username=request.form.get("username"))
        if len(rows) > 0:
            return apology("Username not available", 403)

        #Check if password matches confirmation

        if not request.form.get("password") == request.form.get("ConfirmPassword"):
            return apology("Passwords do not match", 403)

        #Insert user into database if above conditions met
        db.execute("INSERT INTO users (username, hash) VALUES (:username , :hash)" ,
        username = request.form.get("username"), hash = generate_password_hash(request.form.get("password")))

        #store id and login user
        rows0 = db.execute("SELECT * FROM users WHERE username = :username", username = request.form.get("username"))
        session["user_id"] = rows0[0]["id"]
        return redirect("/")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    rows = db.execute("SELECT * FROM users WHERE id = :id",
                          id = session["user_id"])

    rows1 = db.execute("SELECT symbol, SUM(quantity) FROM transactions WHERE id= :id AND symbol= :symbol GROUP BY symbol", id = session["user_id"], symbol=request.form.get("symbol"))


    if request.method == "GET":

        sym_rows = db.execute("SELECT symbol, SUM(quantity) FROM transactions WHERE id= :id GROUP BY symbol", id = session["user_id"])

        return render_template("sell.html", sym_rows=sym_rows)

    #request is made through POST request
    else:

        #Check if stock symbol and quantity fields are filled
        if not request.form.get("symbol"):
            return apology("must provide stock symbol", 403)

        elif not request.form.get("shares"):
            return apology("must provide quantity", 403)

        #Check to see if user has enough shares
        elif float(rows1[0]["SUM(quantity)"]) < float(request.form.get("shares")):
            return apology("you aint got nuff shares homes", 403)

        #Enter into transactions database
        else:
            trans_id = db.execute("INSERT INTO transactions (id, type, symbol, company, price, quantity, tranvalue) VALUES (:id, :type, :symbol, :company, :price, :quantity, :tranvalue)",
                        id = session["user_id"] ,type = "sell", symbol = lookup(request.form.get("symbol"))["symbol"], company = lookup(request.form.get("symbol"))["name"],
                        price = lookup(request.form.get("symbol"))["price"], quantity = float(request.form.get("shares"))*(-1), tranvalue = float(lookup(request.form.get("symbol"))["price"])*float(request.form.get("shares")))

            #update cash
            tran_rows = db.execute("SELECT * FROM transactions WHERE transid= :transid", transid = trans_id)
            newcash = rows[0]["cash"] + tran_rows[0]["tranvalue"]
            db.execute("UPDATE users SET cash = :newcash  WHERE id= :id", newcash = newcash, id = session["user_id"])

            return render_template("transaction.html")



def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
