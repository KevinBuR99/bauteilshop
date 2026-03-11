
from PIL import Image

def compress_image(filepath):

    img = Image.open(filepath)

    # maximale Größe
    max_size = (1200, 1200)

    img.thumbnail(max_size)

    img.save(filepath, optimize=True, quality=75)

from flask import Flask
import sqlite3
from flask import Flask, render_template, request, redirect
import sqlite3
import os
from werkzeug.utils import secure_filename
from datetime import datetime
from flask import session
from reportlab.pdfgen import canvas
from flask import send_file
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
def clean_expired_cart():

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    limit = datetime.now() - timedelta(minutes=30)

    cursor.execute("""
        DELETE FROM cart
        WHERE added_at IS NOT NULL AND added_at < ?
    """, (limit,))

    conn.commit()
    conn.close()

import os

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD_HASH = generate_password_hash(
    os.environ.get("ADMIN_PASSWORD", "admin123")
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", os.urandom(24))
# Datenbank erstellen (falls nicht vorhanden)
def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS parts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            description TEXT,
            condition TEXT,
            price REAL,
            quantity INTEGER DEFAULT 1
        )
    """)

    # Falls die Spalte noch nicht existiert
    try:
        cursor.execute("ALTER TABLE parts ADD COLUMN quantity INTEGER DEFAULT 1")
        print("Quantity Spalte hinzugefügt!")
    except:
        pass


    cursor.execute("""
    CREATE TABLE IF NOT EXISTS images (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        part_id INTEGER,
        filename TEXT,
        is_main INTEGER DEFAULT 0,
        position INTEGER DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (part_id) REFERENCES parts(id)
        )
    """)

    # Index für schnelle Bildabfragen
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_images_part_id
    ON images(part_id)
    """)

    cursor.execute("PRAGMA table_info(images)")
    columns = [column[1] for column in cursor.fetchall()]

    if "is_main" not in columns:
        cursor.execute("ALTER TABLE images ADD COLUMN is_main INTEGER DEFAULT 0")

    if "position" not in columns:
        cursor.execute("ALTER TABLE images ADD COLUMN position INTEGER DEFAULT 0")

    if "created_at" not in columns:
        cursor.execute("ALTER TABLE images ADD COLUMN created_at DATETIME")




    cursor.execute("""
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            part_id INTEGER,
            filename TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE,
            firstname TEXT,
            lastname TEXT,
            company TEXT,
            address TEXT,
            password TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cart (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            part_id INTEGER,
            quantity INTEGER,
            added_at DATETIME
        )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        created_at DATETIME
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER,
        part_id INTEGER,
        quantity INTEGER
    )
    """)
# prüfen ob order_id existiert
    cursor.execute("PRAGMA table_info(order_items)")
    columns = [column[1] for column in cursor.fetchall()]

    if "order_id" not in columns:
        cursor.execute("ALTER TABLE order_items ADD COLUMN order_id INTEGER")
        print("order_id Spalte hinzugefügt!")

    conn.commit()
    conn.close()

init_db()

@app.route("/")
def home():

    clean_expired_cart()    
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    search_query = request.args.get("q")
    min_price = request.args.get("min_price")
    max_price = request.args.get("max_price")
    sort = request.args.get("sort")
    page = request.args.get("page", 1, type=int)
    per_page = 6
    offset = (page - 1) * per_page

    query = "SELECT * FROM parts WHERE 1=1"
    params = []

    if search_query:
        query += " AND (name LIKE ? OR description LIKE ?)"
        params.append(f"%{search_query}%")
        params.append(f"%{search_query}%")

    if min_price:
        query += " AND price >= ?"
        params.append(min_price)

    if max_price:
        query += " AND price <= ?"
        params.append(max_price)

    if sort == "price_asc":
        query += " ORDER BY price ASC"
    elif sort == "price_desc":
        query += " ORDER BY price DESC"

    cursor.execute("SELECT COUNT(*) FROM parts")
    total_parts = cursor.fetchone()[0]
    total_pages = (total_parts + per_page - 1) // per_page

    query += " LIMIT ? OFFSET ?"
    params.append(per_page)
    params.append(offset)

    cursor.execute(query, params)
    parts = cursor.fetchall()

    parts_with_images = []

    for part in parts:
        cursor.execute("SELECT filename FROM images WHERE part_id = ?", (part[0],))
        images = cursor.fetchall()
        parts_with_images.append((part, images))

    conn.close()

    return render_template(
        "index.html",
        parts=parts_with_images,
        search_query=search_query,
        min_price=min_price,
        max_price=max_price,
        sort=sort,
        page=page,
        total_pages=total_pages
    )

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        if username == ADMIN_USERNAME and check_password_hash(ADMIN_PASSWORD_HASH, password):
            session["admin"] = True
            return redirect("/")

        return "Login fehlgeschlagen!"

    return render_template("admin_login.html")

@app.route("/logout")
def logout():
    session.pop("admin", None)
    return redirect("/")


@app.route("/admin")
def admin_dashboard():

    if "admin" not in session:
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
    SELECT id, email, firstname, lastname, company
    FROM users
    """)

    users = cursor.fetchall()

    conn.close()

    return render_template("admin_dashboard.html", users=users)

@app.route("/admin/reset_password/<int:user_id>", methods=["POST"])
def reset_password(user_id):

    if "admin" not in session:
        return redirect("/login")

    new_password = request.form["password"]

    password_hash = generate_password_hash(new_password)

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
    UPDATE users
    SET password = ?
    WHERE id = ?
    """, (password_hash, user_id))

    conn.commit()
    conn.close()

    return redirect("/admin")

@app.route("/admin/orders")
def admin_orders():

    if "admin" not in session:
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
    SELECT orders.id, users.email, orders.created_at
    FROM orders
    JOIN users ON orders.user_id = users.id
    ORDER BY orders.created_at DESC
    """)

    orders = cursor.fetchall()

    conn.close()

    return render_template("admin_orders.html", orders=orders)

@app.route("/admin/order/<int:order_id>")
def admin_order_detail(order_id):

    if "admin" not in session:
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    # Bestellinfo
    cursor.execute("""
    SELECT orders.id, users.email, orders.created_at
    FROM orders
    JOIN users ON orders.user_id = users.id
    WHERE orders.id = ?
    """, (order_id,))

    order = cursor.fetchone()

    # Artikel
    cursor.execute("""
    SELECT parts.name, parts.price, order_items.quantity
    FROM order_items
    JOIN parts ON order_items.part_id = parts.id
    WHERE order_items.order_id = ?
    """, (order_id,))

    items = cursor.fetchall()

    # Gesamtpreis berechnen
    total = 0
    for item in items:
        total += item[1] * item[2]

    conn.close()

    return render_template(
        "admin_order_detail.html",
        order=order,
        items=items,
        total=total
    )

@app.route("/admin/edit_user/<int:user_id>", methods=["GET","POST"])
def edit_user(user_id):

    if "admin" not in session:
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    if request.method == "POST":

        email = request.form["email"]
        firstname = request.form["firstname"]
        lastname = request.form["lastname"]
        company = request.form["company"]
        address = request.form["address"]

        cursor.execute("""
        UPDATE users
        SET email=?, firstname=?, lastname=?, company=?, address=?
        WHERE id=?
        """,(email, firstname, lastname, company, address, user_id))

        conn.commit()
        conn.close()

        return redirect("/admin")

    cursor.execute("SELECT * FROM users WHERE id=?", (user_id,))
    user = cursor.fetchone()

    conn.close()

    return render_template("edit_user.html", user=user)


@app.route("/admin/order_pdf/<int:order_id>")
def order_pdf(order_id):

    if "admin" not in session:
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    # Bestellinformationen
    cursor.execute("""
    SELECT orders.id, users.email, orders.created_at
    FROM orders
    JOIN users ON orders.user_id = users.id
    WHERE orders.id = ?
    """, (order_id,))

    order = cursor.fetchone()

    # Artikel laden
    cursor.execute("""
    SELECT parts.name, parts.price, order_items.quantity
    FROM order_items
    JOIN parts ON order_items.part_id = parts.id
    WHERE order_items.order_id = ?
    """, (order_id,))

    items = cursor.fetchall()

    conn.close()

    filename = os.path.join("static", f"invoice_{order_id}.pdf")
    c = canvas.Canvas(filename)

    y = 800

    # Firmenkopf
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y, "Bauteile Shop")

    y -= 30
    c.setFont("Helvetica", 10)
    c.drawString(50, y, "Firma Rauch")
    y -= 15
    c.drawString(50, y, "Nüziders 6714")
    y -= 15
    c.drawString(50, y, "Österreich")

    # Rechnungsinfo rechts
    y = 800
    c.setFont("Helvetica-Bold", 14)
    c.drawRightString(550, y, f"Rechnung #{order_id}")

    y -= 40
    c.setFont("Helvetica", 10)
    c.drawRightString(550, y, f"Kunde: {order[1]}")
    y -= 15
    c.drawRightString(550, y, f"Datum: {order[2].split('.')[0]}")

    # Tabelle Header
    y -= 80
    c.setFont("Helvetica-Bold", 12)

    c.drawString(50, y, "Artikel")
    c.drawString(350, y, "Menge")
    c.drawString(420, y, "Preis")

    y -= 10
    c.line(50, y, 550, y)

    y -= 20

    total = 0

    c.setFont("Helvetica", 11)

    for item in items:

        name = item[0]
        price = item[1]
        qty = item[2]

        line_total = price * qty
        total += line_total

        c.drawString(50, y, name)
        c.drawString(360, y, str(qty))
        c.drawString(420, y, f"{line_total:.2f} €")

        y -= 20

    # Gesamt
    y -= 10
    c.line(350, y, 550, y)

    y -= 20
    c.setFont("Helvetica-Bold", 12)
    c.drawString(350, y, "Gesamt:")
    c.drawString(420, y, f"{total:.2f} €")

    # Footer
    y -= 60
    c.setFont("Helvetica", 9)
    c.drawString(50, y, "Vielen Dank für Ihre Bestellung!")

    c.save()

    return send_file(filename, as_attachment=True)

@app.route("/part/<int:id>")
def part_detail(id):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    # Bauteil holen
    cursor.execute("SELECT * FROM parts WHERE id = ?", (id,))
    part = cursor.fetchone()

    # Bilder holen
    cursor.execute("SELECT filename FROM images WHERE part_id = ?", (id,))
    images = cursor.fetchall()

    cursor.execute(
        "SELECT filename FROM files WHERE part_id=?",
        (id,)
)

    files = cursor.fetchall()

    conn.close()

    return render_template(
    "part.html",
    part=part,
    images=images,
    files=files
)


import re

@app.route("/register", methods=["GET","POST"])
def register():

    if request.method == "POST":

        email = request.form["email"]
        firstname = request.form["firstname"]
        lastname = request.form["lastname"]
        company = request.form["company"]
        address = request.form["address"]
        password = request.form["password"]

        # Passwort prüfen
        if len(password) < 8:
            return "Passwort muss mindestens 8 Zeichen haben."

        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
            return "Passwort muss mindestens ein Sonderzeichen enthalten."

        password_hash = generate_password_hash(password)

        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()

        try:

            cursor.execute("""
            INSERT INTO users (email, firstname, lastname, company, address, password)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (email, firstname, lastname, company, address, password_hash))

            conn.commit()

        except:
            return "Email existiert bereits"

        conn.close()

        return redirect("/user_login")

    return render_template("register.html")
@app.route("/user_login", methods=["GET","POST"])
def user_login():

    if request.method == "POST":

        email = request.form.get("email")
        password = request.form.get("password")

        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id, password FROM users WHERE email=?",
            (email,)
        )

        user = cursor.fetchone()

        conn.close()

        if user and check_password_hash(user[1], password):

            session["user_id"] = user[0]
            session["username"] = email

            return redirect("/")

        return "Login fehlgeschlagen"

    return render_template("user_login.html")

@app.route("/user_logout")
def user_logout():

    session.pop("user_id", None)
    session.pop("username", None)

    return redirect("/")

@app.route("/account")
def account():

    if "user_id" not in session:
        return redirect("/user_login")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    user_id = session["user_id"]

    # User Daten
    cursor.execute("""
    SELECT email, firstname, lastname, company, address
    FROM users
    WHERE id = ?
    """, (user_id,))

    user = cursor.fetchone()

    # Bestellungen laden
    cursor.execute("""
    SELECT id, created_at
    FROM orders
    WHERE user_id = ?
    ORDER BY created_at DESC
    """, (user_id,))

    orders = cursor.fetchall()

    conn.close()

    return render_template("account.html", user=user, orders=orders)

@app.route("/invoice/<int:order_id>")
def user_invoice(order_id):

    if "user_id" not in session:
        return redirect("/user_login")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    # Prüfen ob Bestellung dem User gehört
    cursor.execute("""
    SELECT id FROM orders
    WHERE id = ? AND user_id = ?
    """, (order_id, session["user_id"]))

    order = cursor.fetchone()

    if not order:
        conn.close()
        return "Keine Berechtigung für diese Rechnung."

    # Bestellpositionen holen
    cursor.execute("""
    SELECT parts.name, parts.price, order_items.quantity
    FROM order_items
    JOIN parts ON order_items.part_id = parts.id
    WHERE order_items.order_id = ?
    """, (order_id,))

    items = cursor.fetchall()

    conn.close()

    filename = os.path.join("static", f"invoice_user_{order_id}.pdf")

    c = canvas.Canvas(filename)

    y = 800

    c.drawString(100, y, f"Rechnung Bestellung #{order_id}")
    y -= 40

    total = 0

    for item in items:

        name = item[0]
        price = item[1]
        qty = item[2]

        line_total = price * qty
        total += line_total

        c.drawString(100, y, f"{name}  x{qty}  = {line_total} €")

        y -= 20

    y -= 20
    c.drawString(100, y, f"Gesamt: {total} €")

    c.save()

    return send_file(filename, as_attachment=True)

@app.route("/add", methods=["GET", "POST"])
def add_part():
    if "admin" not in session:
        return redirect("/login")

    if request.method == "POST":
        name = request.form["name"]
        description = request.form["description"]
        condition = request.form["condition"]
        price = request.form["price"]
        quantity = request.form["quantity"]

        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()

        # Bauteil speichern
        cursor.execute("""
            INSERT INTO parts (name, description, condition, price, quantity)
            VALUES (?, ?, ?, ?, ?)
        """, (name, description, condition, price, quantity))

        part_id = cursor.lastrowid

        # 🔥 Mehrere Bilder holen
        images = request.files.getlist("images")

        print("Anzahl Bilder:", len(images))

        for image in images:
            if image and image.filename != "":
                filename = secure_filename(image.filename)

                path = os.path.join("static/images", filename)

                image.save(path)

                compress_image(path)

                cursor.execute("""
                     INSERT INTO images (part_id, filename)
                     VALUES (?, ?)
                """, (part_id, filename))

        # 🔥 PDFs speichern
        files = request.files.getlist("files")

        for file in files:
            if file.filename != "":
                filename = secure_filename(file.filename)

                file.save(os.path.join("static/files", filename))

                cursor.execute(
                    "INSERT INTO files (part_id, filename) VALUES (?, ?)",
                    (part_id, filename)
                )

        conn.commit()
        conn.close()

        return redirect("/")

    return render_template("add.html")

@app.route("/delete_image/<int:image_id>/<int:part_id>")
def delete_image(image_id, part_id):

    if "admin" not in session:
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    # Dateiname holen
    cursor.execute("SELECT filename FROM images WHERE id = ?", (image_id,))
    result = cursor.fetchone()

    if result:
        filename = result[0]
        image_path = os.path.join("static/images", filename)

        if os.path.exists(image_path):
            os.remove(image_path)

        cursor.execute("DELETE FROM images WHERE id = ?", (image_id,))
        conn.commit()

    conn.close()

    return redirect(f"/edit/{part_id}")

@app.route("/delete/<int:id>")
def delete_part(id):

    if "admin" not in session:
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    # 🔹 Alle Bilder zu diesem Bauteil holen
    cursor.execute("SELECT filename FROM images WHERE part_id = ?", (id,))
    images = cursor.fetchall()

    # 🔹 Bilder aus Ordner löschen
    for image in images:
        image_path = os.path.join("static/images", image[0])
        if os.path.exists(image_path):
            os.remove(image_path)

    # 🔹 Bilder aus DB löschen
    cursor.execute("DELETE FROM images WHERE part_id = ?", (id,))

    # 🔹 Bauteil löschen
    cursor.execute("DELETE FROM parts WHERE id = ?", (id,))

    conn.commit()
    conn.close()

    return redirect("/")

@app.route("/delete_file/<int:file_id>")
def delete_file(file_id):

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("SELECT filename, part_id FROM files WHERE id=?", (file_id,))
    file = cursor.fetchone()

    if file:

        filename = file[0]
        part_id = file[1]

        path = os.path.join("static/files", filename)

        if os.path.exists(path):
            os.remove(path)

        cursor.execute("DELETE FROM files WHERE id=?", (file_id,))
        conn.commit()

    conn.close()

    return redirect(f"/edit/{part_id}")

@app.route("/add_to_cart/<int:part_id>")
def add_to_cart(part_id):

    clean_expired_cart()

    if "user_id" not in session:
        return redirect("/user_login")

    user_id = session["user_id"]

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    # Prüfen ob Produkt schon im Warenkorb ist
    cursor.execute(
        "SELECT id, quantity FROM cart WHERE user_id=? AND part_id=?",
        (user_id, part_id)
    )

    existing = cursor.fetchone()

    if existing:

        # Menge erhöhen
        cursor.execute(
            "UPDATE cart SET quantity = quantity + 1 WHERE id=?",
            (existing[0],)
        )

    else:

    # Neues Produkt hinzufügen mit Zeit
        cursor.execute(
            "INSERT INTO cart (user_id, part_id, quantity, added_at) VALUES (?, ?, 1, ?)",
            (user_id, part_id, datetime.now())
    )

    conn.commit()
    conn.close()

    return redirect("/cart")

@app.route("/cart")
def cart():

    clean_expired_cart()
    if "user_id" not in session:
        return redirect("/user_login")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
    SELECT parts.id, parts.name, parts.price, cart.quantity, cart.added_at,
       (SELECT filename FROM images WHERE part_id = parts.id LIMIT 1)
    FROM cart
    JOIN parts ON cart.part_id = parts.id
    WHERE cart.user_id = ?
    """, (session["user_id"],))

    items = cursor.fetchall()

    items_with_timer = []

    total_price = 0

    for item in items:
        if item[4]:
            added_time = datetime.fromisoformat(item[4])
        else:
            added_time = datetime.now()

        remaining = (added_time + timedelta(minutes=30)) - datetime.now()

        seconds = int(remaining.total_seconds())

        if seconds < 0:
            minutes = 0
            seconds = 0
        else:
            minutes = seconds // 60
            seconds = seconds % 60

        total_price += item[2] * item[3]

        items_with_timer.append({
            "id": item[0],
            "name": item[1],
            "price": item[2],
            "quantity": item[3],
            "image": item[5],
            "minutes": minutes,
            "seconds": seconds
        })

    conn.close()

    return render_template(
    "cart.html",
    items=items_with_timer,
    total_price=total_price
    )

@app.route("/checkout")
def checkout():

    if "user_id" not in session:
        return redirect("/user_login")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    user_id = session["user_id"]

    # Warenkorb laden
    cursor.execute("""
    SELECT part_id, quantity
    FROM cart
    WHERE user_id = ?
    """, (user_id,))

    cart_items = cursor.fetchall()

    if not cart_items:
        return redirect("/cart")

    # Bestellung erstellen
    cursor.execute("""
    INSERT INTO orders (user_id, created_at)
    VALUES (?, ?)
    """, (user_id, datetime.now()))

    order_id = cursor.lastrowid

    for item in cart_items:

        part_id = item[0]
        quantity = item[1]

        # Bestellung speichern
        cursor.execute("""
        INSERT INTO order_items (order_id, part_id, quantity)
        VALUES (?, ?, ?)
        """, (order_id, part_id, quantity))

        # Lager reduzieren
        cursor.execute("""
        UPDATE parts
        SET quantity = MAX(quantity - ?,0)
        WHERE id = ?
        """, (quantity, part_id))

    # Warenkorb leeren
    cursor.execute("""
    DELETE FROM cart WHERE user_id = ?
    """, (user_id,))

    conn.commit()
    conn.close()

    return redirect(f"/order_success/{order_id}")

@app.route("/order_success/<int:order_id>")
def order_success(order_id):

    if "user_id" not in session:
        return redirect("/")

    return render_template("order_success.html", order_id=order_id)

@app.route("/cart_increase/<int:part_id>")
def cart_increase(part_id):

    clean_expired_cart()

    if "user_id" not in session:
        return redirect("/user_login")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    # aktuelle Menge im Warenkorb
    cursor.execute("""
    SELECT quantity FROM cart
    WHERE user_id = ? AND part_id = ?
    """, (session["user_id"], part_id))

    cart_item = cursor.fetchone()

    # Lagerbestand
    cursor.execute("""
    SELECT quantity FROM parts
    WHERE id = ?
    """, (part_id,))

    stock = cursor.fetchone()

    if cart_item and stock:

        if cart_item[0] < stock[0]:

            cursor.execute("""
            UPDATE cart
            SET quantity = quantity + 1
            WHERE user_id = ? AND part_id = ?
            """, (session["user_id"], part_id))

    conn.commit()
    conn.close()

    return redirect("/cart")
@app.route("/cart_decrease/<int:part_id>")
def cart_decrease(part_id):

    clean_expired_cart()

    if "user_id" not in session:
        return redirect("/user_login")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
    UPDATE cart
    SET quantity = quantity - 1
    WHERE user_id = ? AND part_id = ? AND quantity > 1
    """, (session["user_id"], part_id))

    conn.commit()
    conn.close()

    return redirect("/cart")

@app.route("/cart_remove/<int:part_id>")
def cart_remove(part_id):

    if "user_id" not in session:
        return redirect("/user_login")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
    DELETE FROM cart
    WHERE user_id = ? AND part_id = ?
    """, (session["user_id"], part_id))

    conn.commit()
    conn.close()

    return redirect("/cart")

@app.route("/edit/<int:id>", methods=["GET", "POST"])
def edit_part(id):
    if "admin" not in session:
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    if request.method == "POST":
        name = request.form["name"]
        description = request.form["description"]
        condition = request.form["condition"]
        price = request.form["price"]
        quantity = request.form["quantity"]

        # 🔹 Bauteil-Daten updaten
        cursor.execute("""
            UPDATE parts
            SET name = ?, description = ?, condition = ?, price = ?, quantity = ?
            WHERE id = ?
        """, (name, description, condition, price, quantity, id))

        # 🔹 Neue Bilder holen (Mehrfach!)
        images = request.files.getlist("images")

        for image in images:
            if image and image.filename != "":
                filename = secure_filename(image.filename)
                image.save(os.path.join("static/images", filename))

                cursor.execute("""
                    INSERT INTO images (part_id, filename)
                    VALUES (?, ?)
                """, (id, filename))

        files = request.files.getlist("files")

        for file in files:

              if file.filename != "":

                   filename = secure_filename(file.filename)

                   file.save(os.path.join("static/files", filename))

                   cursor.execute(
                    "INSERT INTO files (part_id, filename) VALUES (?, ?)",
                    (id, filename)
                    )

        conn.commit()
        conn.close()

        return redirect("/")

    # GET
    cursor.execute("SELECT * FROM parts WHERE id = ?", (id,))
    part = cursor.fetchone()

    cursor.execute("SELECT id, filename FROM images WHERE part_id = ?", (id,))
    images = cursor.fetchall()

    cursor.execute("SELECT id, filename FROM files WHERE part_id = ?", (id,))
    files = cursor.fetchall()

    conn.close()

    return render_template("edit.html", part=part, images=images, files=files)
if __name__ == "__main__":

 def compress_image(filepath):
    from PIL import Image
    import pillow_heif
    import os

    pillow_heif.register_heif_opener()

    img = Image.open(filepath)

    # maximale Größe
    max_size = (1200, 1200)
    img.thumbnail(max_size)

    # HEIC → JPG konvertieren
    if filepath.lower().endswith(".heic"):
        new_path = filepath.rsplit(".", 1)[0] + ".jpg"

        img = img.convert("RGB")
        img.save(new_path, "JPEG", optimize=True, quality=75)

        os.remove(filepath)
        return new_path

    # normale Bilder komprimieren
    img.save(filepath, optimize=True, quality=75)
    return filepath

from flask import Flask, render_template, request, redirect
import sqlite3
import os
from werkzeug.utils import secure_filename
from datetime import datetime
from flask import session
from reportlab.pdfgen import canvas
from flask import send_file
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
def clean_expired_cart():

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    limit = datetime.now() - timedelta(minutes=30)

    cursor.execute("""
        DELETE FROM cart
        WHERE added_at IS NOT NULL AND added_at < ?
    """, (limit,))

    conn.commit()
    conn.close()

import os

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD_HASH = generate_password_hash(
    os.environ.get("ADMIN_PASSWORD", "admin123")
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", os.urandom(24))
# Datenbank erstellen (falls nicht vorhanden)
def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS parts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            description TEXT,
            condition TEXT,
            price REAL,
            quantity INTEGER DEFAULT 1
        )
    """)

    # Falls die Spalte noch nicht existiert
    try:
        cursor.execute("ALTER TABLE parts ADD COLUMN quantity INTEGER DEFAULT 1")
        print("Quantity Spalte hinzugefügt!")
    except:
        pass


    cursor.execute("""
    CREATE TABLE IF NOT EXISTS images (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        part_id INTEGER,
        filename TEXT,
        is_main INTEGER DEFAULT 0,
        position INTEGER DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (part_id) REFERENCES parts(id)
        )
    """)

    # Index für schnelle Bildabfragen
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_images_part_id
    ON images(part_id)
    """)

    cursor.execute("PRAGMA table_info(images)")
    columns = [column[1] for column in cursor.fetchall()]

    if "is_main" not in columns:
        cursor.execute("ALTER TABLE images ADD COLUMN is_main INTEGER DEFAULT 0")

    if "position" not in columns:
        cursor.execute("ALTER TABLE images ADD COLUMN position INTEGER DEFAULT 0")

    if "created_at" not in columns:
        cursor.execute("ALTER TABLE images ADD COLUMN created_at DATETIME")




    cursor.execute("""
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            part_id INTEGER,
            filename TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE,
            firstname TEXT,
            lastname TEXT,
            company TEXT,
            address TEXT,
            password TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cart (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            part_id INTEGER,
            quantity INTEGER,
            added_at DATETIME
        )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        created_at DATETIME
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER,
        part_id INTEGER,
        quantity INTEGER
    )
    """)
# prüfen ob order_id existiert
    cursor.execute("PRAGMA table_info(order_items)")
    columns = [column[1] for column in cursor.fetchall()]

    if "order_id" not in columns:
        cursor.execute("ALTER TABLE order_items ADD COLUMN order_id INTEGER")
        print("order_id Spalte hinzugefügt!")

    conn.commit()
    conn.close()

init_db()

@app.route("/")
def home():

    clean_expired_cart()    
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    search_query = request.args.get("q")
    min_price = request.args.get("min_price")
    max_price = request.args.get("max_price")
    sort = request.args.get("sort")
    page = request.args.get("page", 1, type=int)
    per_page = 6
    offset = (page - 1) * per_page

    query = "SELECT * FROM parts WHERE 1=1"
    params = []

    if search_query:
        query += " AND (name LIKE ? OR description LIKE ?)"
        params.append(f"%{search_query}%")
        params.append(f"%{search_query}%")

    if min_price:
        query += " AND price >= ?"
        params.append(min_price)

    if max_price:
        query += " AND price <= ?"
        params.append(max_price)

    if sort == "price_asc":
        query += " ORDER BY price ASC"
    elif sort == "price_desc":
        query += " ORDER BY price DESC"

    cursor.execute("SELECT COUNT(*) FROM parts")
    total_parts = cursor.fetchone()[0]
    total_pages = (total_parts + per_page - 1) // per_page

    query += " LIMIT ? OFFSET ?"
    params.append(per_page)
    params.append(offset)

    cursor.execute(query, params)
    parts = cursor.fetchall()

    parts_with_images = []

    for part in parts:
        cursor.execute("SELECT filename FROM images WHERE part_id = ?", (part[0],))
        images = cursor.fetchall()
        parts_with_images.append((part, images))

    conn.close()

    return render_template(
        "index.html",
        parts=parts_with_images,
        search_query=search_query,
        min_price=min_price,
        max_price=max_price,
        sort=sort,
        page=page,
        total_pages=total_pages
    )

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        if username == ADMIN_USERNAME and check_password_hash(ADMIN_PASSWORD_HASH, password):
            session["admin"] = True
            return redirect("/")

        return "Login fehlgeschlagen!"

    return render_template("admin_login.html")

@app.route("/logout")
def logout():
    session.pop("admin", None)
    return redirect("/")


@app.route("/admin")
def admin_dashboard():

    if "admin" not in session:
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
    SELECT id, email, firstname, lastname, company
    FROM users
    """)

    users = cursor.fetchall()

    conn.close()

    return render_template("admin_dashboard.html", users=users)

@app.route("/admin/reset_password/<int:user_id>", methods=["POST"])
def reset_password(user_id):

    if "admin" not in session:
        return redirect("/login")

    new_password = request.form["password"]

    password_hash = generate_password_hash(new_password)

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
    UPDATE users
    SET password = ?
    WHERE id = ?
    """, (password_hash, user_id))

    conn.commit()
    conn.close()

    return redirect("/admin")

@app.route("/admin/orders")
def admin_orders():

    if "admin" not in session:
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
    SELECT orders.id, users.email, orders.created_at
    FROM orders
    JOIN users ON orders.user_id = users.id
    ORDER BY orders.created_at DESC
    """)

    orders = cursor.fetchall()

    conn.close()

    return render_template("admin_orders.html", orders=orders)

@app.route("/admin/order/<int:order_id>")
def admin_order_detail(order_id):

    if "admin" not in session:
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    # Bestellinfo
    cursor.execute("""
    SELECT orders.id, users.email, orders.created_at
    FROM orders
    JOIN users ON orders.user_id = users.id
    WHERE orders.id = ?
    """, (order_id,))

    order = cursor.fetchone()

    # Artikel
    cursor.execute("""
    SELECT parts.name, parts.price, order_items.quantity
    FROM order_items
    JOIN parts ON order_items.part_id = parts.id
    WHERE order_items.order_id = ?
    """, (order_id,))

    items = cursor.fetchall()

    # Gesamtpreis berechnen
    total = 0
    for item in items:
        total += item[1] * item[2]

    conn.close()

    return render_template(
        "admin_order_detail.html",
        order=order,
        items=items,
        total=total
    )

@app.route("/admin/edit_user/<int:user_id>", methods=["GET","POST"])
def edit_user(user_id):

    if "admin" not in session:
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    if request.method == "POST":

        email = request.form["email"]
        firstname = request.form["firstname"]
        lastname = request.form["lastname"]
        company = request.form["company"]
        address = request.form["address"]

        cursor.execute("""
        UPDATE users
        SET email=?, firstname=?, lastname=?, company=?, address=?
        WHERE id=?
        """,(email, firstname, lastname, company, address, user_id))

        conn.commit()
        conn.close()

        return redirect("/admin")

    cursor.execute("SELECT * FROM users WHERE id=?", (user_id,))
    user = cursor.fetchone()

    conn.close()

    return render_template("edit_user.html", user=user)


@app.route("/admin/order_pdf/<int:order_id>")
def order_pdf(order_id):

    if "admin" not in session:
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    # Bestellinformationen
    cursor.execute("""
    SELECT orders.id, users.email, orders.created_at
    FROM orders
    JOIN users ON orders.user_id = users.id
    WHERE orders.id = ?
    """, (order_id,))

    order = cursor.fetchone()

    # Artikel laden
    cursor.execute("""
    SELECT parts.name, parts.price, order_items.quantity
    FROM order_items
    JOIN parts ON order_items.part_id = parts.id
    WHERE order_items.order_id = ?
    """, (order_id,))

    items = cursor.fetchall()

    conn.close()

    filename = os.path.join("static", f"invoice_{order_id}.pdf")
    c = canvas.Canvas(filename)

    y = 800

    # Firmenkopf
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y, "Bauteile Shop")

    y -= 30
    c.setFont("Helvetica", 10)
    c.drawString(50, y, "Firma Rauch")
    y -= 15
    c.drawString(50, y, "Nüziders 6714")
    y -= 15
    c.drawString(50, y, "Österreich")

    # Rechnungsinfo rechts
    y = 800
    c.setFont("Helvetica-Bold", 14)
    c.drawRightString(550, y, f"Rechnung #{order_id}")

    y -= 40
    c.setFont("Helvetica", 10)
    c.drawRightString(550, y, f"Kunde: {order[1]}")
    y -= 15
    c.drawRightString(550, y, f"Datum: {order[2].split('.')[0]}")

    # Tabelle Header
    y -= 80
    c.setFont("Helvetica-Bold", 12)

    c.drawString(50, y, "Artikel")
    c.drawString(350, y, "Menge")
    c.drawString(420, y, "Preis")

    y -= 10
    c.line(50, y, 550, y)

    y -= 20

    total = 0

    c.setFont("Helvetica", 11)

    for item in items:

        name = item[0]
        price = item[1]
        qty = item[2]

        line_total = price * qty
        total += line_total

        c.drawString(50, y, name)
        c.drawString(360, y, str(qty))
        c.drawString(420, y, f"{line_total:.2f} €")

        y -= 20

    # Gesamt
    y -= 10
    c.line(350, y, 550, y)

    y -= 20
    c.setFont("Helvetica-Bold", 12)
    c.drawString(350, y, "Gesamt:")
    c.drawString(420, y, f"{total:.2f} €")

    # Footer
    y -= 60
    c.setFont("Helvetica", 9)
    c.drawString(50, y, "Vielen Dank für Ihre Bestellung!")

    c.save()

    return send_file(filename, as_attachment=True)

@app.route("/part/<int:id>")
def part_detail(id):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    # Bauteil holen
    cursor.execute("SELECT * FROM parts WHERE id = ?", (id,))
    part = cursor.fetchone()

    # Bilder holen
    cursor.execute("SELECT filename FROM images WHERE part_id = ?", (id,))
    images = cursor.fetchall()

    cursor.execute(
        "SELECT filename FROM files WHERE part_id=?",
        (id,)
)

    files = cursor.fetchall()

    conn.close()

    return render_template(
    "part.html",
    part=part,
    images=images,
    files=files
)


import re

@app.route("/register", methods=["GET","POST"])
def register():

    if request.method == "POST":

        email = request.form["email"]
        firstname = request.form["firstname"]
        lastname = request.form["lastname"]
        company = request.form["company"]
        address = request.form["address"]
        password = request.form["password"]

        # Passwort prüfen
        if len(password) < 8:
            return "Passwort muss mindestens 8 Zeichen haben."

        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
            return "Passwort muss mindestens ein Sonderzeichen enthalten."

        password_hash = generate_password_hash(password)

        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()

        try:

            cursor.execute("""
            INSERT INTO users (email, firstname, lastname, company, address, password)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (email, firstname, lastname, company, address, password_hash))

            conn.commit()

        except:
            return "Email existiert bereits"

        conn.close()

        return redirect("/user_login")

    return render_template("register.html")
@app.route("/user_login", methods=["GET","POST"])
def user_login():

    if request.method == "POST":

        email = request.form.get("email")
        password = request.form.get("password")

        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id, password FROM users WHERE email=?",
            (email,)
        )

        user = cursor.fetchone()

        conn.close()

        if user and check_password_hash(user[1], password):

            session["user_id"] = user[0]
            session["username"] = email

            return redirect("/")

        return "Login fehlgeschlagen"

    return render_template("user_login.html")

@app.route("/user_logout")
def user_logout():

    session.pop("user_id", None)
    session.pop("username", None)

    return redirect("/")

@app.route("/account")
def account():

    if "user_id" not in session:
        return redirect("/user_login")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    user_id = session["user_id"]

    # User Daten
    cursor.execute("""
    SELECT email, firstname, lastname, company, address
    FROM users
    WHERE id = ?
    """, (user_id,))

    user = cursor.fetchone()

    # Bestellungen laden
    cursor.execute("""
    SELECT id, created_at
    FROM orders
    WHERE user_id = ?
    ORDER BY created_at DESC
    """, (user_id,))

    orders = cursor.fetchall()

    conn.close()

    return render_template("account.html", user=user, orders=orders)

@app.route("/invoice/<int:order_id>")
def user_invoice(order_id):

    if "user_id" not in session:
        return redirect("/user_login")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    # Prüfen ob Bestellung dem User gehört
    cursor.execute("""
    SELECT id FROM orders
    WHERE id = ? AND user_id = ?
    """, (order_id, session["user_id"]))

    order = cursor.fetchone()

    if not order:
        conn.close()
        return "Keine Berechtigung für diese Rechnung."

    # Bestellpositionen holen
    cursor.execute("""
    SELECT parts.name, parts.price, order_items.quantity
    FROM order_items
    JOIN parts ON order_items.part_id = parts.id
    WHERE order_items.order_id = ?
    """, (order_id,))

    items = cursor.fetchall()

    conn.close()

    filename = os.path.join("static", f"invoice_user_{order_id}.pdf")

    c = canvas.Canvas(filename)

    y = 800

    c.drawString(100, y, f"Rechnung Bestellung #{order_id}")
    y -= 40

    total = 0

    for item in items:

        name = item[0]
        price = item[1]
        qty = item[2]

        line_total = price * qty
        total += line_total

        c.drawString(100, y, f"{name}  x{qty}  = {line_total} €")

        y -= 20

    y -= 20
    c.drawString(100, y, f"Gesamt: {total} €")

    c.save()

    return send_file(filename, as_attachment=True)

@app.route("/add", methods=["GET", "POST"])
def add_part():
    if "admin" not in session:
        return redirect("/login")

    if request.method == "POST":
        name = request.form["name"]
        description = request.form["description"]
        condition = request.form["condition"]
        price = request.form["price"]
        quantity = request.form["quantity"]

        conn = sqlite3.connect("database.db", timeout=10)
        cursor = conn.cursor()

        cursor.execute("""
        INSERT INTO parts (name, description, condition, price, quantity)
        VALUES (?, ?, ?, ?, ?)
        """, (name, description, condition, price, quantity))

        conn.commit()
        conn.close()

        part_id = cursor.lastrowid

        # 🔥 Mehrere Bilder holen
        images = request.files.getlist("images")

        print("Anzahl Bilder:", len(images))

        for image in images:
            if image and image.filename != "":
                filename = secure_filename(image.filename)

                path = os.path.join("static/images", filename)

                image.save(path)

                compress_image(path)

                cursor.execute("""
                     INSERT INTO images (part_id, filename)
                     VALUES (?, ?)
                """, (part_id, filename))

        # 🔥 PDFs speichern
        files = request.files.getlist("files")

        for file in files:
            if file.filename != "":
                filename = secure_filename(file.filename)

                file.save(os.path.join("static/files", filename))

                cursor.execute(
                    "INSERT INTO files (part_id, filename) VALUES (?, ?)",
                    (part_id, filename)
                )

        conn.commit()
        conn.close()

        return redirect("/")

    return render_template("add.html")

@app.route("/delete_image/<int:image_id>/<int:part_id>")
def delete_image(image_id, part_id):

    if "admin" not in session:
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    # Dateiname holen
    cursor.execute("SELECT filename FROM images WHERE id = ?", (image_id,))
    result = cursor.fetchone()

    if result:
        filename = result[0]
        image_path = os.path.join("static/images", filename)

        if os.path.exists(image_path):
            os.remove(image_path)

        cursor.execute("DELETE FROM images WHERE id = ?", (image_id,))
        conn.commit()

    conn.close()

    return redirect(f"/edit/{part_id}")

@app.route("/delete/<int:id>")
def delete_part(id):

    if "admin" not in session:
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    # 🔹 Alle Bilder zu diesem Bauteil holen
    cursor.execute("SELECT filename FROM images WHERE part_id = ?", (id,))
    images = cursor.fetchall()

    # 🔹 Bilder aus Ordner löschen
    for image in images:
        image_path = os.path.join("static/images", image[0])
        if os.path.exists(image_path):
            os.remove(image_path)

    # 🔹 Bilder aus DB löschen
    cursor.execute("DELETE FROM images WHERE part_id = ?", (id,))

    # 🔹 Bauteil löschen
    cursor.execute("DELETE FROM parts WHERE id = ?", (id,))

    conn.commit()
    conn.close()

    return redirect("/")

@app.route("/delete_file/<int:file_id>")
def delete_file(file_id):

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("SELECT filename, part_id FROM files WHERE id=?", (file_id,))
    file = cursor.fetchone()

    if file:

        filename = file[0]
        part_id = file[1]

        path = os.path.join("static/files", filename)

        if os.path.exists(path):
            os.remove(path)

        cursor.execute("DELETE FROM files WHERE id=?", (file_id,))
        conn.commit()

    conn.close()

    return redirect(f"/edit/{part_id}")

@app.route("/add_to_cart/<int:part_id>")
def add_to_cart(part_id):

    clean_expired_cart()

    if "user_id" not in session:
        return redirect("/user_login")

    user_id = session["user_id"]

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    # Prüfen ob Produkt schon im Warenkorb ist
    cursor.execute(
        "SELECT id, quantity FROM cart WHERE user_id=? AND part_id=?",
        (user_id, part_id)
    )

    existing = cursor.fetchone()

    if existing:

        # Menge erhöhen
        cursor.execute(
            "UPDATE cart SET quantity = quantity + 1 WHERE id=?",
            (existing[0],)
        )

    else:

    # Neues Produkt hinzufügen mit Zeit
        cursor.execute(
            "INSERT INTO cart (user_id, part_id, quantity, added_at) VALUES (?, ?, 1, ?)",
            (user_id, part_id, datetime.now())
    )

    conn.commit()
    conn.close()

    return redirect("/cart")

@app.route("/cart")
def cart():

    clean_expired_cart()
    if "user_id" not in session:
        return redirect("/user_login")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
    SELECT parts.id, parts.name, parts.price, cart.quantity, cart.added_at,
       (SELECT filename FROM images WHERE part_id = parts.id LIMIT 1)
    FROM cart
    JOIN parts ON cart.part_id = parts.id
    WHERE cart.user_id = ?
    """, (session["user_id"],))

    items = cursor.fetchall()

    items_with_timer = []

    total_price = 0

    for item in items:
        if item[4]:
            added_time = datetime.fromisoformat(item[4])
        else:
            added_time = datetime.now()

        remaining = (added_time + timedelta(minutes=30)) - datetime.now()

        seconds = int(remaining.total_seconds())

        if seconds < 0:
            minutes = 0
            seconds = 0
        else:
            minutes = seconds // 60
            seconds = seconds % 60

        total_price += item[2] * item[3]

        items_with_timer.append({
            "id": item[0],
            "name": item[1],
            "price": item[2],
            "quantity": item[3],
            "image": item[5],
            "minutes": minutes,
            "seconds": seconds
        })

    conn.close()

    return render_template(
    "cart.html",
    items=items_with_timer,
    total_price=total_price
    )

@app.route("/checkout")
def checkout():

    if "user_id" not in session:
        return redirect("/user_login")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    user_id = session["user_id"]

    # Warenkorb laden
    cursor.execute("""
    SELECT part_id, quantity
    FROM cart
    WHERE user_id = ?
    """, (user_id,))

    cart_items = cursor.fetchall()

    if not cart_items:
        return redirect("/cart")

    # Bestellung erstellen
    cursor.execute("""
    INSERT INTO orders (user_id, created_at)
    VALUES (?, ?)
    """, (user_id, datetime.now()))

    order_id = cursor.lastrowid

    for item in cart_items:

        part_id = item[0]
        quantity = item[1]

        # Bestellung speichern
        cursor.execute("""
        INSERT INTO order_items (order_id, part_id, quantity)
        VALUES (?, ?, ?)
        """, (order_id, part_id, quantity))

        # Lager reduzieren
        cursor.execute("""
        UPDATE parts
        SET quantity = MAX(quantity - ?,0)
        WHERE id = ?
        """, (quantity, part_id))

    # Warenkorb leeren
    cursor.execute("""
    DELETE FROM cart WHERE user_id = ?
    """, (user_id,))

    conn.commit()
    conn.close()

    return redirect(f"/order_success/{order_id}")

@app.route("/order_success/<int:order_id>")
def order_success(order_id):

    if "user_id" not in session:
        return redirect("/")

    return render_template("order_success.html", order_id=order_id)

@app.route("/cart_increase/<int:part_id>")
def cart_increase(part_id):

    clean_expired_cart()

    if "user_id" not in session:
        return redirect("/user_login")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    # aktuelle Menge im Warenkorb
    cursor.execute("""
    SELECT quantity FROM cart
    WHERE user_id = ? AND part_id = ?
    """, (session["user_id"], part_id))

    cart_item = cursor.fetchone()

    # Lagerbestand
    cursor.execute("""
    SELECT quantity FROM parts
    WHERE id = ?
    """, (part_id,))

    stock = cursor.fetchone()

    if cart_item and stock:

        if cart_item[0] < stock[0]:

            cursor.execute("""
            UPDATE cart
            SET quantity = quantity + 1
            WHERE user_id = ? AND part_id = ?
            """, (session["user_id"], part_id))

    conn.commit()
    conn.close()

    return redirect("/cart")
@app.route("/cart_decrease/<int:part_id>")
def cart_decrease(part_id):

    clean_expired_cart()

    if "user_id" not in session:
        return redirect("/user_login")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
    UPDATE cart
    SET quantity = quantity - 1
    WHERE user_id = ? AND part_id = ? AND quantity > 1
    """, (session["user_id"], part_id))

    conn.commit()
    conn.close()

    return redirect("/cart")

@app.route("/cart_remove/<int:part_id>")
def cart_remove(part_id):

    if "user_id" not in session:
        return redirect("/user_login")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
    DELETE FROM cart
    WHERE user_id = ? AND part_id = ?
    """, (session["user_id"], part_id))

    conn.commit()
    conn.close()

    return redirect("/cart")

@app.route("/edit/<int:id>", methods=["GET", "POST"])
def edit_part(id):
    if "admin" not in session:
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    if request.method == "POST":
        name = request.form["name"]
        description = request.form["description"]
        condition = request.form["condition"]
        price = request.form["price"]
        quantity = request.form["quantity"]

        # 🔹 Bauteil-Daten updaten
        cursor.execute("""
            UPDATE parts
            SET name = ?, description = ?, condition = ?, price = ?, quantity = ?
            WHERE id = ?
        """, (name, description, condition, price, quantity, id))

        # 🔹 Neue Bilder holen (Mehrfach!)
        images = request.files.getlist("images")

        for image in images:
            if image and image.filename != "":
                filename = secure_filename(image.filename)
                image.save(os.path.join("static/images", filename))

                cursor.execute("""
                    INSERT INTO images (part_id, filename)
                    VALUES (?, ?)
                """, (id, filename))

        files = request.files.getlist("files")

        for file in files:

              if file.filename != "":

                   filename = secure_filename(file.filename)

                   file.save(os.path.join("static/files", filename))

                   cursor.execute(
                    "INSERT INTO files (part_id, filename) VALUES (?, ?)",
                    (id, filename)
                    )

        conn.commit()
        conn.close()

        return redirect("/")

    # GET
    cursor.execute("SELECT * FROM parts WHERE id = ?", (id,))
    part = cursor.fetchone()

    cursor.execute("SELECT id, filename FROM images WHERE part_id = ?", (id,))
    images = cursor.fetchall()

    cursor.execute("SELECT id, filename FROM files WHERE part_id = ?", (id,))
    files = cursor.fetchall()

    conn.close()

    return render_template("edit.html", part=part, images=images, files=files)
if __name__ == "__main__":

    app.run()