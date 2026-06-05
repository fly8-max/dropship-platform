import os, json, random, string
from datetime import datetime
from flask import Flask, jsonify, request, render_template, redirect, url_for, session
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-in-prod")

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)

def _path(name): return os.path.join(DATA_DIR, f"{name}.json")
def load(name):
    try:
        with open(_path(name)) as f: return json.load(f)
    except FileNotFoundError: return []
def save(name, data):
    with open(_path(name), "w") as f: json.dump(data, f, indent=2, default=str)
def find_by_id(collection, id_): return next((x for x in collection if x["id"] == id_), None)

def seed_defaults():
    stores = load("stores")
    if not stores:
        stores = [
            {"id":"store_001","name":"VitalEdge Health","niche":"Health & Wellness","status":"active","owner":"demo@demo.com","created":str(datetime.utcnow().date()),"revenue":0,"orders":0},
            {"id":"store_002","name":"HomeStyle Co","niche":"Home & Kitchen","status":"active","owner":"demo@demo.com","created":str(datetime.utcnow().date()),"revenue":0,"orders":0},
        ]
        save("stores", stores)
    products = load("products")
    if not products:
        products = [
            {"id":"p001","store_id":"store_001","name":"Premium Resistance Bands","price":24.99,"cogs":8.50},
            {"id":"p002","store_id":"store_001","name":"Foam Roller Pro","price":34.99,"cogs":11.00},
            {"id":"p003","store_id":"store_001","name":"Yoga Mat Ultra","price":39.99,"cogs":14.00},
            {"id":"p004","store_id":"store_001","name":"Protein Shaker Bottle","price":19.99,"cogs":6.00},
            {"id":"p005","store_id":"store_002","name":"Bamboo Spice Rack","price":29.99,"cogs":9.50},
            {"id":"p006","store_id":"store_002","name":"Electric Kettle 1.7L","price":44.99,"cogs":16.00},
            {"id":"p007","store_id":"store_002","name":"Stackable Storage Bins","price":22.99,"cogs":7.50},
        ]
        save("products", products)
    if not load("orders"): save("orders", [])

seed_defaults()

USERS = {"demo@demo.com": "demo1234", "admin@vitaledge.com": "admin123"}

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session: return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return decorated

@app.route("/")
@login_required
def index(): return render_template("dashboard.html", user=session["user"])

@app.route("/login", methods=["GET","POST"])
def login_page():
    error = None
    if request.method == "POST":
        email = request.form.get("email","")
        pwd = request.form.get("password","")
        if USERS.get(email) == pwd:
            session["user"] = email
            return redirect(url_for("index"))
        error = "Invalid email or password."
    return render_template("login.html", error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login_page"))

@app.route("/api/stores")
@login_required
def get_stores(): return jsonify(load("stores"))

@app.route("/api/stores/<store_id>")
@login_required
def get_store(store_id):
    store = find_by_id(load("stores"), store_id)
    return jsonify(store) if store else (jsonify({"error":"not found"}), 404)

@app.route("/api/stores/<store_id>/products")
@login_required
def get_products(store_id): return jsonify([p for p in load("products") if p["store_id"] == store_id])

@app.route("/api/orders")
@login_required
def get_orders():
    orders = load("orders")
    orders.sort(key=lambda x: x["created"], reverse=True)
    return jsonify(orders[:20])

@app.route("/api/simulate-sale", methods=["POST"])
@login_required
def simulate_sale():
    data = request.get_json(silent=True) or {}
    store_id = data.get("store_id")
    stores = load("stores")
    products = load("products")
    if store_id:
        store = find_by_id(stores, store_id)
    else:
        active = [s for s in stores if s["status"] == "active"]
        store = random.choice(active) if active else None
    if not store: return jsonify({"error":"no active store"}), 400
    store_products = [p for p in products if p["store_id"] == store["id"]]
    if not store_products: return jsonify({"error":"no products"}), 400
    product = random.choice(store_products)
    qty = random.randint(1,3)
    revenue = round(product["price"]*qty, 2)
    cogs = round(product["cogs"]*qty, 2)
    commission = round(revenue*0.10, 2)
    profit = round(revenue-cogs-commission, 2)
    order_id = "ORD-" + "".join(random.choices(string.ascii_uppercase+string.digits, k=6))
    order = {"id":order_id,"store_id":store["id"],"store_name":store["name"],"product":product["name"],"qty":qty,"revenue":revenue,"cogs":cogs,"commission":commission,"profit":profit,"created":datetime.utcnow().isoformat(),"simulated":True}
    orders = load("orders")
    orders.append(order)
    save("orders", orders)
    for s in stores:
        if s["id"] == store["id"]:
            s["revenue"] = round(s.get("revenue",0)+revenue, 2)
            s["orders"] = s.get("orders",0)+1
    save("stores", stores)
    return jsonify({"success":True,"order":order})

@app.route("/api/summary")
@login_required
def summary():
    stores = load("stores")
    orders = load("orders")
    return jsonify({"total_stores":len(stores),"active_stores":sum(1 for s in stores if s["status"]=="active"),"total_orders":len(orders),"total_revenue":round(sum(o["revenue"] for o in orders),2),"total_commission":round(sum(o["commission"] for o in orders),2)})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
