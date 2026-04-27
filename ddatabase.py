import sqlite3

DB_NAME = "toko_susu.db"

def get_connection():
    return sqlite3.connect(DB_NAME)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS brands (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            nama    TEXT NOT NULL UNIQUE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS produk (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            brand_id  INTEGER NOT NULL,
            nama      TEXT NOT NULL,
            ukuran    TEXT NOT NULL,
            harga     INTEGER NOT NULL,
            stok      INTEGER DEFAULT 0,
            FOREIGN KEY (brand_id) REFERENCES brands(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            username   TEXT,
            nama       TEXT NOT NULL,
            produk_id  INTEGER NOT NULL,
            qty        INTEGER NOT NULL,
            total      INTEGER NOT NULL,
            alamat     TEXT NOT NULL,
            status     TEXT DEFAULT 'pending',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (produk_id) REFERENCES produk(id)
        )
    """)

    # Seed data contoh jika tabel produk masih kosong
    cursor.execute("SELECT COUNT(*) FROM brands")
    if cursor.fetchone()[0] == 0:
        brands_data = [
            ("Bear Brand",),
            ("SGM",),
            ("Dancow",),
            ("Frisian Flag",),
            ("Indomilk",),
        ]
        cursor.executemany("INSERT INTO brands (nama) VALUES (?)", brands_data)

        produk_data = [
            (1, "Full Cream",    "300ml",  5000,  50),
            (1, "Full Cream",    "600ml",  9500,  30),
            (2, "Eksplor 1+",   "400g",   85000, 20),
            (2, "Eksplor 1+",   "700g",   140000,15),
            (3, "Full Cream",   "800g",   95000, 25),
            (3, "Instant",      "400g",   55000, 40),
            (4, "Full Cream",   "1kg",    120000,18),
            (4, "Gold",         "400g",   90000, 22),
            (5, "Full Cream",   "1kg",    110000,35),
            (5, "Coklat",       "500ml",  7000,  60),
        ]
        cursor.executemany(
            "INSERT INTO produk (brand_id, nama, ukuran, harga, stok) VALUES (?,?,?,?,?)",
            produk_data
        )

    conn.commit()
    conn.close()
    print("Database siap.")

# ─────────────────────────────────────────
# FUNGSI PRODUK
# ─────────────────────────────────────────

def get_semua_produk():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.id, b.nama as brand, p.nama, p.ukuran, p.harga, p.stok
        FROM produk p
        JOIN brands b ON p.brand_id = b.id
        ORDER BY b.nama, p.nama
    """)
    hasil = cursor.fetchall()
    conn.close()
    return hasil

def get_produk_by_id(produk_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.id, b.nama, p.nama, p.ukuran, p.harga, p.stok
        FROM produk p
        JOIN brands b ON p.brand_id = b.id
        WHERE p.id = ?
    """, (produk_id,))
    hasil = cursor.fetchone()
    conn.close()
    return hasil

def tambah_brand(nama_brand):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO brands (nama) VALUES (?)", (nama_brand,))
        conn.commit()
        brand_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        cursor.execute("SELECT id FROM brands WHERE nama=?", (nama_brand,))
        brand_id = cursor.fetchone()[0]
    conn.close()
    return brand_id

def tambah_produk(nama_brand, nama_produk, ukuran, harga, stok):
    brand_id = tambah_brand(nama_brand)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO produk (brand_id, nama, ukuran, harga, stok) VALUES (?,?,?,?,?)",
        (brand_id, nama_produk, ukuran, int(harga), int(stok))
    )
    produk_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return produk_id

def edit_produk(produk_id, field, nilai):
    field_boleh = {"harga", "stok", "nama", "ukuran"}
    if field not in field_boleh:
        return False
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"UPDATE produk SET {field}=? WHERE id=?", (nilai, produk_id))
    conn.commit()
    conn.close()
    return True

def hapus_produk(produk_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM produk WHERE id=?", (produk_id,))
    conn.commit()
    conn.close()

def kurangi_stok(produk_id, qty):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE produk SET stok = stok - ? WHERE id=?", (qty, produk_id))
    conn.commit()
    conn.close()

# ─────────────────────────────────────────
# FUNGSI ORDER
# ─────────────────────────────────────────

def simpan_order(user_id, username, nama, produk_id, qty, total, alamat):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO orders (user_id, username, nama, produk_id, qty, total, alamat)
        VALUES (?,?,?,?,?,?,?)
    """, (user_id, username, nama, produk_id, qty, total, alamat))
    order_id = cursor.lastrowid
    conn.commit()
    conn.close()
    kurangi_stok(produk_id, qty)
    return order_id

def get_semua_orders(status=None):
    conn = get_connection()
    cursor = conn.cursor()
    if status:
        cursor.execute("""
            SELECT o.id, o.nama, b.nama, p.nama, p.ukuran, o.qty, o.total, o.alamat, o.status, o.created_at
            FROM orders o
            JOIN produk p ON o.produk_id = p.id
            JOIN brands b ON p.brand_id = b.id
            WHERE o.status = ?
            ORDER BY o.created_at DESC
        """, (status,))
    else:
        cursor.execute("""
            SELECT o.id, o.nama, b.nama, p.nama, p.ukuran, o.qty, o.total, o.alamat, o.status, o.created_at
            FROM orders o
            JOIN produk p ON o.produk_id = p.id
            JOIN brands b ON p.brand_id = b.id
            ORDER BY o.created_at DESC
            LIMIT 20
        """)
    hasil = cursor.fetchall()
    conn.close()
    return hasil

def update_status_order(order_id, status_baru):
    status_valid = {"pending", "diproses", "dikirim", "selesai", "batal"}
    if status_baru not in status_valid:
        return False
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE orders SET status=? WHERE id=?", (status_baru, order_id))
    conn.commit()
    conn.close()
    return True

def get_order_by_id(order_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT o.id, o.user_id, o.nama, b.nama, p.nama, p.ukuran, o.qty, o.total, o.alamat, o.status, o.created_at
        FROM orders o
        JOIN produk p ON o.produk_id = p.id
        JOIN brands b ON p.brand_id = b.id
        WHERE o.id = ?
    """, (order_id,))
    hasil = cursor.fetchone()
    conn.close()
    return hasil