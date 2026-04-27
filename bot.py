import sys
sys.stdout.reconfigure(encoding="utf-8")

import os
import telebot
from fuzzywuzzy import fuzz, process
from database import (
    init_db, get_semua_produk, get_produk_by_id,
    tambah_produk, edit_produk, hapus_produk,
    simpan_order, get_semua_orders, update_status_order, get_order_by_id
)

# ─────────────────────────────────────────
# KONFIGURASI
# ─────────────────────────────────────────
TOKEN    = os.environ.get("TOKEN", "ISI_TOKEN_BOTFATHER_DISINI")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "ISI_CHAT_ID_ADMIN_DISINI"))

bot = telebot.TeleBot(TOKEN)
init_db()

# Simpan state percakapan per user
user_states = {}

# ─────────────────────────────────────────
# FAQ FUZZY MATCHING
# ─────────────────────────────────────────
FAQ = {
    "halo hai hello menu bantuan help":
        "Halo! Selamat datang di Toko Susu kami!\n\n"
        "Ketik salah satu:\n"
        "- cari [nama susu]  => cari produk\n"
        "- order [id]        => pesan produk\n"
        "- ORD-[nomor]       => cek status pesanan\n"
        "- jam               => jam operasional\n"
        "- kontak            => hubungi kami",

    "jam buka tutup operasional waktu":
        "Jam Operasional:\n"
        "Senin - Jumat : 08.00 - 17.00 WIB\n"
        "Sabtu         : 08.00 - 13.00 WIB\n"
        "Minggu        : Libur",

    "kontak hubungi admin cs telepon email":
        "Kontak Kami:\n"
        "Email : admin@tokosusu.com\n"
        "Telp  : 0812-3456-7890\n"
        "IG    : @toko_susu_official",

    "bayar pembayaran transfer rekening":
        "Metode Pembayaran:\n"
        "- Transfer BCA  : 1234567890 a/n Toko Susu\n"
        "- Transfer BRI  : 0987654321 a/n Toko Susu\n"
        "- COD tersedia untuk area Sidoarjo & Surabaya",

    "pengiriman kirim ongkir estimasi":
        "Info Pengiriman:\n"
        "- Estimasi 1-3 hari kerja\n"
        "- COD area Sidoarjo & Surabaya: GRATIS\n"
        "- Luar kota: JNE / SiCepat (ongkir menyesuaikan)",
}

THRESHOLD_FAQ     = 60
THRESHOLD_PRODUK  = 55

# ─────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────

def is_admin(message):
    return message.from_user.id == ADMIN_ID

def cari_faq(teks):
    hasil = process.extractOne(teks.lower(), FAQ.keys(), scorer=fuzz.partial_ratio)
    if hasil and hasil[1] >= THRESHOLD_FAQ:
        return FAQ[hasil[0]]
    return None

def cari_produk_fuzzy(keyword):
    semua = get_semua_produk()
    hasil = []
    for row in semua:
        # row: (id, brand, nama, ukuran, harga, stok)
        label = f"{row[1]} {row[2]} {row[3]}"
        skor = fuzz.partial_ratio(keyword.lower(), label.lower())
        if skor >= THRESHOLD_PRODUK:
            hasil.append((skor, row))
    hasil.sort(reverse=True)
    return [r[1] for r in hasil[:5]]

def format_list_produk(produk_list):
    if not produk_list:
        return "Produk tidak ditemukan.\nCoba kata kunci lain, contoh: cari bear brand"
    teks = "Hasil Pencarian Produk:\n\n"
    for p in produk_list:
        stok_label = f"Tersedia ({p[5]} pcs)" if p[5] > 0 else "Stok Habis"
        teks += (
            f"ID [{p[0]}] {p[1]} - {p[2]}\n"
            f"   Ukuran : {p[3]}\n"
            f"   Harga  : Rp {p[4]:,}\n"
            f"   Stok   : {stok_label}\n\n"
        )
    teks += "Untuk memesan, ketik: order [ID]\nContoh: order 3"
    return teks

def format_semua_produk_admin():
    semua = get_semua_produk()
    if not semua:
        return "Belum ada produk."
    teks = "=== Daftar Semua Produk ===\n\n"
    for p in semua:
        teks += (
            f"[{p[0]}] {p[1]} - {p[2]} {p[3]}\n"
            f"     Harga: Rp {p[4]:,} | Stok: {p[5]}\n"
        )
    return teks

def format_order_summary(order_id, nama_customer, produk, qty, total, alamat, untuk_admin=False, username=""):
    prefix = "Order Baru Masuk!\n\n" if untuk_admin else "Order Berhasil Dibuat!\n\n"
    teks = (
        f"{prefix}"
        f"No. Order : ORD-{order_id}\n"
        f"Nama      : {nama_customer}\n"
        f"Produk    : {produk[1]} {produk[2]} {produk[3]}\n"
        f"Qty       : {qty} pcs\n"
        f"Total     : Rp {total:,}\n"
        f"Alamat    : {alamat}\n"
        f"Status    : Pending\n"
    )
    if untuk_admin and username:
        teks += f"Username  : @{username}\n"
    teks += "\nSegera proses pesanan!" if untuk_admin else "\nTerima kasih telah berbelanja!"
    return teks

def format_list_orders(orders):
    if not orders:
        return "Belum ada order."
    teks = "=== Daftar Order Terbaru ===\n\n"
    for o in orders:
        # o: (id, nama, brand, nama_produk, ukuran, qty, total, alamat, status, created_at)
        teks += (
            f"ORD-{o[0]} | {o[8].upper()}\n"
            f"  Pembeli : {o[1]}\n"
            f"  Produk  : {o[2]} {o[3]} {o[4]}\n"
            f"  Qty     : {o[5]} | Total: Rp {o[6]:,}\n"
            f"  Tanggal : {o[9][:10]}\n\n"
        )
    return teks

# ─────────────────────────────────────────
# PERINTAH ADMIN
# ─────────────────────────────────────────

def handle_admin(message, teks):
    """Proses semua perintah khusus admin. Return True jika berhasil ditangani."""

    # /help_admin — tampilkan semua perintah admin
    if teks == "/help_admin":
        bot.reply_to(message,
            "=== Perintah Admin ===\n\n"
            "/produk               => lihat semua produk\n"
            "/orders               => lihat 20 order terbaru\n"
            "/orders_pending       => lihat order pending\n\n"
            "/tambah brand|nama|ukuran|harga|stok\n"
            "   Contoh: /tambah Dancow|Fortigro|400g|65000|30\n\n"
            "/edit id|field|nilai\n"
            "   Field: harga / stok / nama / ukuran\n"
            "   Contoh: /edit 3|harga|70000\n"
            "   Contoh: /edit 3|stok|50\n\n"
            "/hapus id\n"
            "   Contoh: /hapus 5\n\n"
            "/status id|status_baru\n"
            "   Status: pending / diproses / dikirim / selesai / batal\n"
            "   Contoh: /status 7|dikirim"
        )
        return True

    # /produk — lihat semua produk
    if teks == "/produk":
        bot.reply_to(message, format_semua_produk_admin())
        return True

    # /orders — lihat semua order terbaru
    if teks == "/orders":
        orders = get_semua_orders()
        bot.reply_to(message, format_list_orders(orders))
        return True

    # /orders_pending — lihat order pending
    if teks == "/orders_pending":
        orders = get_semua_orders(status="pending")
        bot.reply_to(message, format_list_orders(orders) or "Tidak ada order pending.")
        return True

    # /tambah brand|nama|ukuran|harga|stok
    if teks.startswith("/tambah "):
        try:
            parts = teks[8:].split("|")
            if len(parts) != 5:
                raise ValueError
            brand, nama, ukuran, harga, stok = [p.strip() for p in parts]
            produk_id = tambah_produk(brand, nama, ukuran, int(harga), int(stok))
            bot.reply_to(message,
                f"Produk berhasil ditambahkan!\n"
                f"ID: {produk_id}\n"
                f"{brand} - {nama} {ukuran}\n"
                f"Harga: Rp {int(harga):,} | Stok: {stok}"
            )
        except Exception:
            bot.reply_to(message,
                "Format salah!\n"
                "Gunakan: /tambah brand|nama|ukuran|harga|stok\n"
                "Contoh: /tambah Dancow|Fortigro|400g|65000|30"
            )
        return True

    # /edit id|field|nilai
    if teks.startswith("/edit "):
        try:
            parts = teks[6:].split("|")
            if len(parts) != 3:
                raise ValueError
            produk_id, field, nilai = [p.strip() for p in parts]
            nilai_fix = int(nilai) if field in ("harga", "stok") else nilai
            ok = edit_produk(int(produk_id), field, nilai_fix)
            if ok:
                bot.reply_to(message, f"Produk ID {produk_id} berhasil diupdate!\n{field} = {nilai}")
            else:
                bot.reply_to(message, f"Field '{field}' tidak valid.\nField yang bisa diedit: harga, stok, nama, ukuran")
        except Exception:
            bot.reply_to(message,
                "Format salah!\n"
                "Gunakan: /edit id|field|nilai\n"
                "Contoh: /edit 3|harga|70000"
            )
        return True

    # /hapus id
    if teks.startswith("/hapus "):
        try:
            produk_id = int(teks[7:].strip())
            produk = get_produk_by_id(produk_id)
            if not produk:
                bot.reply_to(message, f"Produk ID {produk_id} tidak ditemukan.")
            else:
                hapus_produk(produk_id)
                bot.reply_to(message, f"Produk [{produk_id}] {produk[1]} {produk[2]} {produk[3]} berhasil dihapus.")
        except Exception:
            bot.reply_to(message, "Format salah!\nGunakan: /hapus [id]\nContoh: /hapus 5")
        return True

    # /status id|status_baru
    if teks.startswith("/status "):
        try:
            parts = teks[8:].split("|")
            if len(parts) != 2:
                raise ValueError
            order_id, status_baru = [p.strip() for p in parts]
            ok = update_status_order(int(order_id), status_baru.lower())
            if ok:
                # Ambil data order untuk notifikasi ke customer
                order = get_order_by_id(int(order_id))
                bot.reply_to(message, f"Status ORD-{order_id} diupdate menjadi: {status_baru.upper()}")
                if order:
                    # Kirim notifikasi ke customer
                    pesan_customer = (
                        f"Update Pesanan Kamu!\n\n"
                        f"No. Order : ORD-{order[0]}\n"
                        f"Produk    : {order[3]} {order[4]} {order[5]}\n"
                        f"Status    : {status_baru.upper()}\n\n"
                        f"Terima kasih telah berbelanja di Toko Susu kami!"
                    )
                    try:
                        bot.send_message(order[1], pesan_customer)
                    except Exception:
                        bot.reply_to(message, "(Gagal kirim notifikasi ke customer.)")
            else:
                bot.reply_to(message,
                    f"Status '{status_baru}' tidak valid.\n"
                    "Status yang tersedia: pending, diproses, dikirim, selesai, batal"
                )
        except Exception:
            bot.reply_to(message,
                "Format salah!\n"
                "Gunakan: /status id|status_baru\n"
                "Contoh: /status 7|dikirim"
            )
        return True

    return False  # Bukan perintah admin

# ─────────────────────────────────────────
# HANDLER UTAMA
# ─────────────────────────────────────────

@bot.message_handler(func=lambda m: True)
def handle_message(message):
    user_id  = message.from_user.id
    username = message.from_user.username or "customer"
    teks     = message.text.strip() if message.text else ""

    if not teks:
        return

    # ── ADMIN: cek perintah admin lebih dulu ──
    if is_admin(message):
        if handle_admin(message, teks):
            return

    # ── FLOW ORDER (jika user sedang dalam proses order) ──
    if user_id in user_states:
        state = user_states[user_id]
        step  = state["step"]
        data  = state["data"]

        if step == "nama":
            data["nama"] = teks
            state["step"] = "alamat"
            bot.reply_to(message, "Alamat pengiriman kamu?")

        elif step == "alamat":
            data["alamat"] = teks
            state["step"] = "konfirmasi"
            produk = data["produk"]
            qty    = data["qty"]
            total  = produk[4] * qty
            data["total"] = total
            konfirmasi = (
                f"Konfirmasi Order:\n\n"
                f"Produk : {produk[1]} {produk[2]} {produk[3]}\n"
                f"Qty    : {qty} pcs\n"
                f"Total  : Rp {total:,}\n"
                f"Alamat : {teks}\n\n"
                f"Ketik 'ya' untuk konfirmasi atau 'batal' untuk membatalkan."
            )
            bot.reply_to(message, konfirmasi)

        elif step == "konfirmasi":
            if teks.lower() == "ya":
                produk = data["produk"]
                order_id = simpan_order(
                    user_id, username,
                    data["nama"], produk[0], data["qty"], data["total"], data["alamat"]
                )
                # Summary ke USER
                bot.reply_to(message, format_order_summary(
                    order_id, data["nama"], produk, data["qty"], data["total"], data["alamat"],
                    untuk_admin=False
                ))
                # Summary ke ADMIN
                bot.send_message(ADMIN_ID, format_order_summary(
                    order_id, data["nama"], produk, data["qty"], data["total"], data["alamat"],
                    untuk_admin=True, username=username
                ))
                del user_states[user_id]

            elif teks.lower() == "batal":
                del user_states[user_id]
                bot.reply_to(message, "Order dibatalkan.\nKetik 'cari [produk]' untuk mencari produk lagi.")

            else:
                bot.reply_to(message, "Ketik 'ya' untuk konfirmasi atau 'batal' untuk membatalkan.")
        return

    teks_lower = teks.lower()

    # ── CEK STATUS ORDER: ORD-[nomor] ──
    if teks_lower.startswith("ord-"):
        try:
            order_id = int(teks_lower.replace("ord-", "").strip())
            order = get_order_by_id(order_id)
            if order:
                bot.reply_to(message,
                    f"Status Pesanan ORD-{order[0]}:\n\n"
                    f"Produk  : {order[3]} {order[4]} {order[5]}\n"
                    f"Qty     : {order[6]} pcs\n"
                    f"Total   : Rp {order[7]:,}\n"
                    f"Status  : {order[9].upper()}\n"
                    f"Tanggal : {order[10][:10]}"
                )
            else:
                bot.reply_to(message, f"Order ORD-{order_id} tidak ditemukan.")
        except Exception:
            bot.reply_to(message, "Format salah. Contoh: ORD-5")
        return

    # ── CARI PRODUK: cari [keyword] ──
    if teks_lower.startswith("cari "):
        keyword = teks[5:].strip()
        hasil = cari_produk_fuzzy(keyword)
        bot.reply_to(message, format_list_produk(hasil))
        return

    # ── ORDER PRODUK: order [id] ──
    if teks_lower.startswith("order "):
        try:
            produk_id = int(teks_lower.replace("order ", "").strip())
            produk = get_produk_by_id(produk_id)
            if not produk:
                bot.reply_to(message, f"Produk ID {produk_id} tidak ditemukan.\nKetik 'cari [nama produk]' untuk mencari.")
                return
            if produk[5] <= 0:
                bot.reply_to(message, f"Maaf, stok {produk[1]} {produk[2]} {produk[3]} sedang habis.")
                return

            # Tanya qty
            state = {"step": "qty_input", "data": {"produk": produk}}
            user_states[user_id] = state
            bot.reply_to(message,
                f"Produk dipilih:\n"
                f"{produk[1]} {produk[2]} {produk[3]}\n"
                f"Harga : Rp {produk[4]:,}\n"
                f"Stok  : {produk[5]} pcs\n\n"
                f"Berapa jumlah yang ingin dipesan?"
            )
        except Exception:
            bot.reply_to(message, "Format salah.\nGunakan: order [ID]\nContoh: order 3")
        return

    # ── TANGANI LANGKAH QTY (setelah pilih produk) ──
    if user_id in user_states and user_states[user_id]["step"] == "qty_input":
        try:
            qty = int(teks)
            produk = user_states[user_id]["data"]["produk"]
            if qty <= 0:
                raise ValueError
            if qty > produk[5]:
                bot.reply_to(message, f"Stok tidak cukup. Stok tersedia: {produk[5]} pcs.")
                return
            user_states[user_id]["data"]["qty"] = qty
            user_states[user_id]["step"] = "nama"
            bot.reply_to(message, "Siapa nama penerima?")
        except Exception:
            bot.reply_to(message, "Masukkan angka yang valid untuk jumlah pesanan.")
        return

    # ── FUZZY FAQ ──
    jawaban = cari_faq(teks)
    if jawaban:
        bot.reply_to(message, jawaban)
        return

    # ── FALLBACK ──
    bot.reply_to(message,
        "Maaf, saya tidak mengerti.\n\n"
        "Coba:\n"
        "- halo           => lihat menu\n"
        "- cari [produk]  => cari produk susu\n"
        "- order [id]     => pesan produk\n"
        "- ORD-[nomor]    => cek status pesanan"
    )

# ─────────────────────────────────────────
# JALANKAN BOT
# ─────────────────────────────────────────
print("Bot Toko Susu aktif dan berjalan...")
bot.infinity_polling()