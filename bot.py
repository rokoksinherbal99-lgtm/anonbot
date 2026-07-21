import os, io, json, logging, threading, asyncio
from collections import deque
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from http.server import HTTPServer, BaseHTTPRequestHandler
import cloudinary, cloudinary.uploader, cloudinary.api

cloudinary.config(
    cloud_name="jxqs8oxo",
    api_key="329764921398472",
    api_secret="MPCAJibaweEekHtxwv18TqDGSRA"
)

logging.basicConfig(format="%(asctime)s - %(message)s", level=logging.INFO)
TOKEN = os.getenv("BOT_TOKEN")
queue = deque()
sessions = {}
waiting = {}  # uid -> asyncio.Event

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Anonymous Chat Bot\n"
        "/cari - Cari partner ngobrol\n"
        "/stop - Berhenti ngobrol\n"
        "/next - Cari partner baru\n\n"
        "Auto-match setiap 5 detik!",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("Cari Partner", callback_data="cari")
        ]])
    )

async def cari(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid in sessions:
        await update.message.reply_text("Lo masih ngobrol. Ketik /stop dulu.")
        return
    if uid in queue:
        await update.message.reply_text("Lo udah di antrean.")
        return
    if queue:
        partner = queue.popleft()
        sessions[uid] = partner
        sessions[partner] = uid
        ev = waiting.pop(partner, None)
        if ev: ev.set()
        await ctx.bot.send_message(uid, "Bertemu! Kirim pesan.")
        await ctx.bot.send_message(partner, "Bertemu! Kirim pesan.")
    else:
        queue.append(uid)
        ev = asyncio.Event()
        waiting[uid] = ev
        await update.message.reply_text("Antre... auto-match dalam 5 detik.")
        try:
            await asyncio.wait_for(ev.wait(), timeout=5)
        except asyncio.TimeoutError:
            await update.message.reply_text("Belum ada partner. Coba /cari lagi.")
            queue.discard(uid)
            waiting.pop(uid, None)
        else:
            pass  # matched

async def stop(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid in sessions:
        partner = sessions.pop(uid)
        sessions.pop(partner, None)
        await ctx.bot.send_message(partner, "Partner mengakhiri chat.")
        await update.message.reply_text("Chat diakhiri.")
    else:
        queue.discard(uid)
        waiting.pop(uid, None)
        await update.message.reply_text("Gak ada chat aktif.")

async def next_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await stop(update, ctx)
    await cari(update, ctx)

async def button_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "cari":
        uid = query.from_user.id
        if uid in sessions:
            await query.edit_message_text("Lo masih ngobrol. Ketik /stop dulu.")
            return
        if uid in queue:
            await query.edit_message_text("Lo udah di antrean.")
            return
        if queue:
            partner = queue.popleft()
            sessions[uid] = partner
            sessions[partner] = uid
            ev = waiting.pop(partner, None)
            if ev: ev.set()
            await ctx.bot.send_message(uid, "Bertemu! Kirim pesan.")
            await ctx.bot.send_message(partner, "Bertemu! Kirim pesan.")
            await query.edit_message_text("Bertemu! Kirim pesan.")
        else:
            queue.append(uid)
            ev = asyncio.Event()
            waiting[uid] = ev
            await query.edit_message_text("Antre... auto-match.")
            try:
                await asyncio.wait_for(ev.wait(), timeout=5)
            except asyncio.TimeoutError:
                await query.edit_message_text("Belum ada partner. Klik tombol lagi.", 
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("Cari Lagi", callback_data="cari")
                    ]]))
                queue.discard(uid)
                waiting.pop(uid, None)
            else:
                await query.edit_message_text("Bertemu! Kirim pesan.")

async def handle_msg(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in sessions:
        await update.message.reply_text("Gak ada chat. Ketik /cari",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Cari Partner", callback_data="cari")
            ]]))
        return
    partner = sessions[uid]
    if update.message.text:
        await ctx.bot.send_message(partner, update.message.text)
    elif update.message.photo:
        file = await update.message.photo[-1].get_file()
        fp = io.BytesIO()
        await file.download_to_memory(fp)
        fp.seek(0)
        try:
            result = cloudinary.uploader.upload(fp, public_id=f"anonbot_{uid}_{file.file_id}", format="jpg")
            logging.info(f"FOTO UPLOADED: {result['url']}")
        except Exception as e:
            logging.info(f"FOTO ERROR: {str(e)}")
        await ctx.bot.send_photo(partner, file.file_id)
    elif update.message.sticker:
        await ctx.bot.send_sticker(partner, update.message.sticker.file_id)

def run_http():
    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"alive")
        def log_message(self, *a):
            pass
    HTTPServer(("0.0.0.0", int(os.getenv("PORT", 8000))), H).serve_forever()

def main():
    t = threading.Thread(target=run_http, daemon=True)
    t.start()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cari", cari))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("next", next_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
    app.add_handler(MessageHandler(filters.PHOTO, handle_msg))
    app.add_handler(MessageHandler(filters.Sticker.ALL, handle_msg))
    app.add_handler(CallbackQueryHandler(button_cb))
    print("Bot jalan...")
    app.run_polling()

if __name__ == "__main__":
    main()
