#!/data/data/com.termux/files/usr/bin/python3

import os
import sys
import json
import asyncio
import subprocess
import time
import platform
import re
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes
)

# ================= CONFIG =================
BOT_TOKEN = "8763399030:AAEeEvsKVGHy-asu7XdvvLC5apeMm7WOfYU"

# 🔴 YAHAN APNI TELEGRAM USER ID DAALEIN (admin)
# Apni ID jaanne ke liye @userinfobot pe /start karein
ADMIN_IDS = [123456789]  # <-- Change this

BOTS_DIR = Path.home() / "hosted_bots"
BOTS_DIR.mkdir(exist_ok=True)
PROCESSES_FILE = BOTS_DIR / "processes.json"
DEVELOPER_USERNAME = "OFC_SUVAM_MODZ"
# ==========================================


def load_processes():
    if PROCESSES_FILE.exists():
        try:
            return json.loads(PROCESSES_FILE.read_text())
        except Exception:
            return {}
    return {}


def save_processes(procs):
    PROCESSES_FILE.write_text(json.dumps(procs, indent=2))


def get_bot_info(bot_file_path):
    info = {"name": os.path.basename(bot_file_path), "token": "unknown"}
    try:
        with open(bot_file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            token_match = re.search(
                r'(?:BOT_TOKEN|TOKEN|token)\s*[=:]\s*["\']([^"\']+)["\']', content
            )
            if token_match:
                info["token"] = token_match.group(1)[:20] + "..."
            name_match = re.search(
                r'(?:BOT_NAME|NAME|name)\s*[=:]\s*["\']([^"\']+)["\']', content
            )
            if name_match:
                info["name"] = name_match.group(1)
    except Exception:
        pass
    return info


def is_admin(user_id):
    return user_id in ADMIN_IDS


# ================= KEYBOARDS =================
def main_menu_keyboard(user_id=None):
    keyboard = [
        [InlineKeyboardButton("📋  My Bots", callback_data="menu_list"),
         InlineKeyboardButton("📊  Status", callback_data="menu_status")],

        [InlineKeyboardButton("🔄  Restart Bot", callback_data="menu_restart"),
         InlineKeyboardButton("📄  Logs", callback_data="menu_logs")],

        [InlineKeyboardButton("⏹  Stop Bot", callback_data="menu_stop"),
         InlineKeyboardButton("❌  Cancel", callback_data="cancel")],

        [InlineKeyboardButton("🆔  My ID", callback_data="menu_myid")],

        [InlineKeyboardButton("👨‍💻  Contact Admin", url=f"https://t.me/{DEVELOPER_USERNAME}")],

        [InlineKeyboardButton("❓  Help", callback_data="menu_help")],
    ]

    # Agar admin hai to All Bots button bhi
    if user_id and is_admin(user_id):
        keyboard.insert(2, [InlineKeyboardButton("👑  All Users Bots", callback_data="menu_allbots")])

    return InlineKeyboardMarkup(keyboard)


def back_keyboard():
    keyboard = [
        [InlineKeyboardButton("🔙  Back to Menu", callback_data="menu_home")],
        [InlineKeyboardButton("👨‍💻  Contact Admin", url=f"https://t.me/{DEVELOPER_USERNAME}")],
    ]
    return InlineKeyboardMarkup(keyboard)


# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    await update.message.reply_text(
        f"👋 **Welcome {user.first_name}!**\n\n"
        f"Main aapka **Bot Hosting Bot** hoon!\n\n"
        f"🆔 **Your ID:** `{user.id}`\n\n"
        f"📌 **Kaise use karein?**\n"
        f"• Mujhe koi bhi `.py` bot file bhejo\n"
        f"• Mai usse 24/7 Termux me host kar dunga\n"
        f"• Niche ke buttons se apne bots control karo\n\n"
        f"🔒 **Privacy:** Sirf aap apne bots ko control kar sakte ho.\n"
        f"Dusre users aapke bots ko touch nahi kar sakte.\n\n"
        f"📁 Files stored in: `~/hosted_bots/`\n\n"
        f"_Ab koi `.py` file bhejo aur mai host kar dunga!_",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(user.id)
    )


# ================= HELPERS =================
def get_user_bots(user_id):
    """Sirf us user ke bots return kare"""
    processes = load_processes()
    return {name: info for name, info in processes.items()
            if info.get("owner") == user_id}


def get_all_bots():
    return load_processes()


def can_access(user_id, bot_name):
    """Check kare ki user us bot ko access kar sakta hai ya nahi"""
    processes = load_processes()
    if bot_name not in processes:
        return False
    if is_admin(user_id):
        return True
    return processes[bot_name].get("owner") == user_id


# ================= LIST =================
async def list_bots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    my_bots = get_user_bots(user_id)

    if not my_bots:
        await update.message.reply_text(
            "❌ **Aapne abhi tak koi bot host nahi kiya!**\nKoi `.py` file bhej kar start karein.",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(user_id)
        )
        return

    msg = f"**📋 Your Hosted Bots ({len(my_bots)}):**\n\n"
    for name, proc_info in my_bots.items():
        pid = proc_info.get("pid", "N/A")
        status = "🟢 **Running**" if proc_info.get("active") else "🔴 **Stopped**"
        bot_details = get_bot_info(proc_info["path"])
        msg += f"• **{bot_details['name']}**\n"
        msg += f"  Token: `{bot_details['token']}`\n"
        msg += f"  Status: {status}\n"
        msg += f"  PID: `{pid}`\n"
        msg += f"  Folder: `{name}`\n\n"

    for chunk in [msg[i:i+4000] for i in range(0, len(msg), 4000)]:
        await update.message.reply_text(chunk, parse_mode="Markdown",
                                        reply_markup=main_menu_keyboard(user_id))


# ================= STOP =================
async def stop_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args

    if not args:
        my_bots = get_user_bots(user_id)
        if not my_bots:
            await update.message.reply_text("❌ **Aapke koi bots nahi hain!**",
                                            reply_markup=main_menu_keyboard(user_id))
            return
        keyboard = []
        for name in my_bots.keys():
            bot_info = get_bot_info(my_bots[name]["path"])
            keyboard.append([InlineKeyboardButton(
                f"🔴 Stop {bot_info['name']}", callback_data=f"stop_{name}"
            )])
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="menu_home")])
        await update.message.reply_text(
            "**Kaunsa bot band karna chahte ho?**",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return
    await _stop_bot_process(update, context, args[0])


# ================= RESTART =================
async def restart_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args

    if not args:
        my_bots = get_user_bots(user_id)
        if not my_bots:
            await update.message.reply_text("❌ **Aapke koi bots nahi hain!**",
                                            reply_markup=main_menu_keyboard(user_id))
            return
        keyboard = []
        for name in my_bots.keys():
            bot_info = get_bot_info(my_bots[name]["path"])
            keyboard.append([InlineKeyboardButton(
                f"🔄 Restart {bot_info['name']}", callback_data=f"restart_{name}"
            )])
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="menu_home")])
        await update.message.reply_text(
            "**Kaunsa bot restart karna chahte ho?**",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return
    await _restart_bot_process(update, context, args[0])


# ================= LOGS =================
async def logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args
    my_bots = get_user_bots(user_id)

    if not args:
        if not my_bots:
            await update.message.reply_text("❌ **Aapke koi bots nahi hain!**",
                                            reply_markup=main_menu_keyboard(user_id))
            return
        keyboard = []
        for name in my_bots.keys():
            bot_info = get_bot_info(my_bots[name]["path"])
            keyboard.append([InlineKeyboardButton(
                f"📄 {bot_info['name']}", callback_data=f"logs_{name}"
            )])
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="menu_home")])
        await update.message.reply_text(
            "**Kis bot ke logs dekhna chahte ho?**",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return

    bot_name = args[0]
    if not can_access(user_id, bot_name):
        await update.message.reply_text("❌ Aap is bot ke owner nahi ho!",
                                        parse_mode="Markdown")
        return
    await _send_logs(update, bot_name)


async def _send_logs(update, bot_name, edit=False, query=None):
    log_file = BOTS_DIR / bot_name / "bot.log"
    if not log_file.exists():
        text = f"📄 **{bot_name}** ke liye koi logs nahi hain."
    else:
        content = log_file.read_text(errors='ignore')
        text = (f"📄 **{bot_name} - Last Logs:**\n\n```\n{content[-3000:]}\n```"
                if content else f"📄 **{bot_name}** logs: (empty)")

    kb = back_keyboard()

    if edit and query:
        try:
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)
        except Exception:
            await query.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)


# ================= STATUS =================
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    my_bots = get_user_bots(user_id)
    total = len(my_bots)
    running = sum(1 for p in my_bots.values() if p.get("active"))

    # Refresh status
    processes = load_processes()
    for name, proc_info in list(processes.items()):
        if proc_info.get("owner") != user_id:
            continue
        pid = proc_info.get("pid")
        if pid:
            try:
                os.kill(pid, 0)
            except Exception:
                proc_info["active"] = False
    save_processes(processes)

    uname = platform.uname()
    msg = (
        f"**📊 Your Status:**\n\n"
        f"**Device:** {uname.node}\n"
        f"**OS:** {uname.system} {uname.release}\n"
        f"**Python:** {sys.version.split()[0]}\n\n"
        f"**🤖 Your Bots:**\n"
        f"• Total: {total}\n"
        f"• 🟢 Running: {running}\n"
        f"• 🔴 Stopped: {total - running}\n\n"
        f"**💾 Storage:** {_get_dir_size(BOTS_DIR):.2f} MB"
    )

    await update.message.reply_text(msg, parse_mode="Markdown",
                                    reply_markup=back_keyboard())


def _get_dir_size(path):
    total = 0
    for p in path.rglob('*'):
        if p.is_file():
            try:
                total += p.stat().st_size
            except Exception:
                pass
    return total / (1024 * 1024)


# ================= HELP =================
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    help_text = (
        "**🤖 Bot Hosting Bot - Help**\n\n"
        "**🔒 Privacy:**\n"
        "• Har user apne bots ko control karta hai\n"
        "• Dusre users aapke bots touch nahi kar sakte\n\n"
        "**🚀 Bot Host Kaise Karein?**\n"
        "1. Sirf `.py` file bhejo\n"
        "2. Automatic detect aur start\n"
        "3. Menu se control karo\n\n"
        "**📱 24/7 Tips:**\n"
        "• Battery optimization OFF karein\n"
        "• Termux → 'Unrestricted' karein\n"
        "• WiFi sleep off karein\n\n"
        "**⚠️ Note:** Sirf `.py` files support hain."
    )
    await update.message.reply_text(
        help_text, parse_mode="Markdown", reply_markup=main_menu_keyboard(user_id)
    )


# ================= FILE HANDLER =================
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    document = update.message.document

    if not document.file_name.endswith('.py'):
        await update.message.reply_text("❌ Sirf `.py` files accept ki jaati hain!")
        return

    msg = await update.message.reply_text("📥 **Bot file mil gaya! Processing...**",
                                          parse_mode="Markdown")

    file = await document.get_file()
    timestamp = int(time.time())
    bot_name = document.file_name.replace('.py', '')
    # Har user ke liye unique folder: user_id_timestamp
    folder_name = f"{user.id}_{bot_name}_{timestamp}"
    bot_folder = BOTS_DIR / folder_name
    bot_folder.mkdir(parents=True, exist_ok=True)
    bot_path = bot_folder / document.file_name
    await file.download_to_drive(bot_path)
    bot_path.chmod(0o755)

    await msg.edit_text(f"✅ **File saved!**\nPath: `{bot_path}`\n\n🔄 **Bot start kar raha hoon...**",
                        parse_mode="Markdown")

    success = await _start_bot_process(update, context, folder_name, str(bot_path),
                                       user.id, msg)

    if success:
        await msg.edit_text(
            f"✅ **Bot Successfully Hosted!** 🚀\n\n"
            f"📁 **Name:** `{bot_name}`\n"
            f"📍 **Folder:** `{folder_name}`\n"
            f"📄 **File:** `{document.file_name}`\n\n"
            f"Menu buttons se control karein 👇",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(user.id)
        )
    else:
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔴 Try Again", callback_data="menu_home"),
             InlineKeyboardButton("📄 Logs", callback_data=f"logs_{folder_name}")],
            [InlineKeyboardButton("👨‍💻 Contact Admin", url=f"https://t.me/{DEVELOPER_USERNAME}")]
        ])
        await msg.edit_text(
            f"❌ **Bot start nahi ho paya!**\n\n"
            f"Possible reasons:\n"
            f"• Syntax error\n"
            f"• Missing libraries\n"
            f"• `pip install python-telegram-bot` karein\n",
            parse_mode="Markdown",
            reply_markup=kb
        )


# ================= PROCESS MGMT =================
async def _start_bot_process(update, context, name, path, owner_id, msg=None):
    try:
        log_file = Path(path).parent / "bot.log"
        err_file = Path(path).parent / "bot_error.log"
        cmd = f"cd '{Path(path).parent}' && nohup python3 '{path}' > '{log_file}' 2> '{err_file}' & echo $!"

        proc = await asyncio.create_subprocess_shell(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        stdout, _ = await proc.communicate()
        pid = stdout.decode().strip()

        if not pid or not pid.isdigit():
            return False

        processes = load_processes()
        processes[name] = {
            "pid": int(pid),
            "path": str(path),
            "active": True,
            "owner": owner_id,
            "started_at": time.time()
        }
        save_processes(processes)
        return True
    except Exception as e:
        if msg:
            await msg.edit_text(f"❌ Error: {str(e)}")
        return False


async def _stop_bot_process(update, context, name, query=None):
    user_id = update.effective_user.id if update.effective_user else None

    if not can_access(user_id, name):
        text = "❌ Aap is bot ke owner nahi ho!"
        if query:
            await query.edit_message_text(text, reply_markup=back_keyboard())
        else:
            await update.message.reply_text(text, reply_markup=back_keyboard())
        return

    processes = load_processes()
    proc_info = processes[name]
    pid = proc_info.get("pid")
    if pid:
        try:
            os.kill(pid, 15)
            await asyncio.sleep(1)
            try:
                os.kill(pid, 0)
                os.kill(pid, 9)
            except Exception:
                pass
        except ProcessLookupError:
            pass
        except Exception:
            pass

    proc_info["active"] = False
    proc_info["pid"] = None
    save_processes(processes)

    text = f"🔴 **Bot Stopped:** `{name}`\nUse menu to restart."
    kb = back_keyboard()
    if query:
        try:
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)
        except Exception:
            await query.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)


async def _restart_bot_process(update, context, name, query=None):
    user_id = update.effective_user.id if update.effective_user else None

    if not can_access(user_id, name):
        text = "❌ Aap is bot ke owner nahi ho!"
        if query:
            await query.edit_message_text(text, reply_markup=back_keyboard())
        else:
            await update.message.reply_text(text, reply_markup=back_keyboard())
        return

    processes = load_processes()
    proc_info = processes[name]

    # stop first
    pid = proc_info.get("pid")
    if pid:
        try:
            os.kill(pid, 15)
            await asyncio.sleep(1)
            try:
                os.kill(pid, 0)
                os.kill(pid, 9)
            except Exception:
                pass
        except Exception:
            pass

    success = await _start_bot_process(update, context, name, proc_info["path"],
                                       proc_info.get("owner", user_id))

    text = (f"🔄 **Bot Restarted:** `{name}` ✅" if success
            else f"❌ `{name}` restart nahi ho paya. Logs check karein.")
    kb = back_keyboard()
    if query:
        try:
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)
        except Exception:
            await query.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)


# ================= CALLBACK HANDLER =================
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id

    # ---------- MENU NAVIGATION ----------
    if data == "menu_home":
        try:
            await query.edit_message_text(
                "🏠 **Main Menu**\n\nNiche buttons se option chunein:",
                parse_mode="Markdown",
                reply_markup=main_menu_keyboard(user_id)
            )
        except Exception:
            await query.message.reply_text(
                "🏠 **Main Menu**",
                parse_mode="Markdown",
                reply_markup=main_menu_keyboard(user_id)
            )
        return

    if data == "cancel":
        try:
            await query.edit_message_text(
                "❌ **Cancelled.**",
                reply_markup=main_menu_keyboard(user_id)
            )
        except Exception:
            pass
        return

    if data == "menu_myid":
        try:
            await query.edit_message_text(
                f"🆔 **Your Telegram ID:**\n\n`{user_id}`\n\n"
                f"Yeh ID admin ko dein agar admin access chahiye.",
                parse_mode="Markdown",
                reply_markup=back_keyboard()
            )
        except Exception:
            pass
        return

    if data == "menu_list":
        my_bots = get_user_bots(user_id)
        if not my_bots:
            try:
                await query.edit_message_text(
                    "❌ **Aapke koi bots nahi hain!**\nKoi `.py` file bhej kar start karein.",
                    parse_mode="Markdown",
                    reply_markup=back_keyboard()
                )
            except Exception:
                pass
            return
        msg = f"**📋 Your Hosted Bots ({len(my_bots)}):**\n\n"
        for name, proc_info in my_bots.items():
            status = "🟢 Running" if proc_info.get("active") else "🔴 Stopped"
            bot_details = get_bot_info(proc_info["path"])
            msg += f"• **{bot_details['name']}**\n  Token: `{bot_details['token']}`\n  Status: {status}\n  PID: `{proc_info.get('pid','N/A')}`\n\n"
        try:
            await query.edit_message_text(msg[:4000], parse_mode="Markdown",
                                          reply_markup=back_keyboard())
        except Exception:
            pass
        return

    if data == "menu_allbots":
        if not is_admin(user_id):
            await query.edit_message_text("❌ Only admin!", reply_markup=back_keyboard())
            return
        all_bots = get_all_bots()
        if not all_bots:
            try:
                await query.edit_message_text("❌ No bots hosted.",
                                              reply_markup=back_keyboard())
            except Exception:
                pass
            return
        msg = f"**👑 All Users Bots ({len(all_bots)}):**\n\n"
        for name, proc_info in all_bots.items():
            status = "🟢" if proc_info.get("active") else "🔴"
            owner = proc_info.get("owner", "?")
            bot_details = get_bot_info(proc_info["path"])
            msg += f"{status} **{bot_details['name']}**\n  Owner: `{owner}`\n  Folder: `{name}`\n\n"
        try:
            await query.edit_message_text(msg[:4000], parse_mode="Markdown",
                                          reply_markup=back_keyboard())
        except Exception:
            pass
        return

    if data == "menu_status":
        my_bots = get_user_bots(user_id)
        total = len(my_bots)
        running = sum(1 for p in my_bots.values() if p.get("active"))
        msg = (
            f"**📊 Your Status:**\n\n"
            f"**Device:** {platform.uname().node}\n"
            f"**OS:** {platform.uname().system}\n"
            f"**Python:** {sys.version.split()[0]}\n\n"
            f"**🤖 Your Bots:**\n"
            f"• Total: {total}\n"
            f"• 🟢 Running: {running}\n"
            f"• 🔴 Stopped: {total - running}\n\n"
            f"**💾 Storage:** {_get_dir_size(BOTS_DIR):.2f} MB"
        )
        try:
            await query.edit_message_text(msg, parse_mode="Markdown",
                                          reply_markup=back_keyboard())
        except Exception:
            pass
        return

    if data == "menu_help":
        help_text = (
            "**🤖 Help Menu**\n\n"
            "**🔒 Privacy:**\n"
            "• Har user ke bots private hain\n"
            "• Sirf owner control kar sakta hai\n\n"
            "**🚀 Host:** `.py` file bhejo\n"
            "**⚙️ Control:** Menu buttons se\n\n"
            "**📱 24/7 Tips:**\n"
            "• Battery optimization OFF\n"
            "• Termux → Unrestricted\n"
            "• WiFi sleep off"
        )
        try:
            await query.edit_message_text(help_text, parse_mode="Markdown",
                                          reply_markup=back_keyboard())
        except Exception:
            pass
        return

    # ---------- BOT LIST SELECTION MENUS ----------
    if data in ("menu_stop", "menu_restart", "menu_logs"):
        my_bots = get_user_bots(user_id)
        if not my_bots:
            try:
                await query.edit_message_text(
                    "❌ **Aapke koi bots nahi hain!**",
                    reply_markup=back_keyboard()
                )
            except Exception:
                pass
            return
        keyboard = []
        for name in my_bots.keys():
            bot_info = get_bot_info(my_bots[name]["path"])
            if data == "menu_stop":
                keyboard.append([InlineKeyboardButton(
                    f"🔴 Stop {bot_info['name']}", callback_data=f"stop_{name}"
                )])
            elif data == "menu_restart":
                keyboard.append([InlineKeyboardButton(
                    f"🔄 Restart {bot_info['name']}", callback_data=f"restart_{name}"
                )])
            else:
                keyboard.append([InlineKeyboardButton(
                    f"📄 {bot_info['name']}", callback_data=f"logs_{name}"
                )])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="menu_home")])
        titles = {
            "menu_stop": "**Kaunsa bot band karna chahte ho?** 🔴",
            "menu_restart": "**Kaunsa bot restart karna chahte ho?** 🔄",
            "menu_logs": "**Kis bot ke logs dekhna chahte ho?** 📄",
        }
        try:
            await query.edit_message_text(
                titles[data],
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        except Exception:
            pass
        return

    # ---------- BOT ACTION CALLBACKS ----------
    if "_" in data:
        action, bot_name = data.split("_", 1)
        if action == "stop":
            await _stop_bot_process(update, context, bot_name, query=query)
        elif action == "restart":
            await _restart_bot_process(update, context, bot_name, query=query)
        elif action == "logs":
            if not can_access(user_id, bot_name):
                try:
                    await query.edit_message_text(
                        "❌ Aap is bot ke owner nahi ho!",
                        reply_markup=back_keyboard()
                    )
                except Exception:
                    pass
                return
            await _send_logs(update, bot_name, edit=True, query=query)


# ================= POST INIT =================
async def post_init(app: Application):
    processes = load_processes()
    restarted = 0
    for name, proc_info in list(processes.items()):
        if proc_info.get("active"):
            pid = proc_info.get("pid")
            if pid:
                try:
                    os.kill(pid, 0)
                    continue
                except Exception:
                    pass
            bot_path = proc_info["path"]
            if os.path.exists(bot_path):
                print(f"🔄 Auto-restarting {name}...")
                try:
                    log_file = Path(bot_path).parent / "bot.log"
                    err_file = Path(bot_path).parent / "bot_error.log"
                    proc = subprocess.Popen(
                        ["python3", bot_path],
                        stdout=open(log_file, 'a'),
                        stderr=open(err_file, 'a'),
                        cwd=str(Path(bot_path).parent)
                    )
                    processes[name]["pid"] = proc.pid
                    restarted += 1
                except Exception as e:
                    print(f"❌ Failed to restart {name}: {e}")
                    processes[name]["active"] = False
    save_processes(processes)
    print(f"✅ Auto-restarted {restarted} bots. Total: {len(processes)}")


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"Error: {context.error}")


# ================= MAIN =================
def main():
    try:
        import telegram  # noqa
    except ImportError:
        print("Installing python-telegram-bot...")
        os.system("pip install python-telegram-bot==20.7")

    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("list", list_bots))
    app.add_handler(CommandHandler("stop", stop_bot))
    app.add_handler(CommandHandler("restart", restart_bot))
    app.add_handler(CommandHandler("logs", logs))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("help", help_command))

    app.add_handler(MessageHandler(filters.Document.FileExtension("py"), handle_document))
    app.add_handler(CallbackQueryHandler(button_callback))

    app.add_error_handler(error_handler)

    print("🤖 Multi-User Bot Hosting Bot started!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
