import logging
import os
import random
import sqlite3
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

if load_dotenv:
    load_dotenv()

DB_PATH = os.getenv("RPG_DB_PATH", "rpg_bot.db")
HUNT_COOLDOWN_SECONDS = 45
BOT_OWNER_ID = int(os.getenv("BOT_OWNER_ID", "0"))

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


@dataclass
class Monster:
    name: str
    hp: int
    attack_min: int
    attack_max: int
    gold_drop: int
    exp_drop: int


MONSTERS: List[Monster] = [
    Monster("Slime", 18, 2, 6, 10, 12),
    Monster("Goblin", 26, 4, 9, 18, 20),
    Monster("Wolf", 32, 5, 10, 24, 25),
    Monster("Orc", 45, 6, 13, 38, 40),
    Monster("Mini Dragon", 65, 8, 17, 60, 72),
]

SHOP_ITEMS: Dict[str, Dict[str, int]] = {
    "potion": {"price": 25, "heal": 30},
    "hi_potion": {"price": 80, "heal": 80},
    "sword": {"price": 120, "attack": 3},
    "greatsword": {"price": 220, "attack": 6},
}


class RPGRepository:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS players (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    level INTEGER NOT NULL DEFAULT 1,
                    exp INTEGER NOT NULL DEFAULT 0,
                    gold INTEGER NOT NULL DEFAULT 0,
                    hp INTEGER NOT NULL DEFAULT 100,
                    max_hp INTEGER NOT NULL DEFAULT 100,
                    attack INTEGER NOT NULL DEFAULT 10,
                    guild_id INTEGER,
                    last_hunt_ts INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS inventory (
                    user_id INTEGER NOT NULL,
                    item_name TEXT NOT NULL,
                    quantity INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (user_id, item_name)
                );

                CREATE TABLE IF NOT EXISTS guilds (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    owner_id INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS trade_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    from_user_id INTEGER NOT NULL,
                    to_user_id INTEGER NOT NULL,
                    item_name TEXT NOT NULL,
                    qty INTEGER NOT NULL,
                    price INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_ts INTEGER NOT NULL
                );
                """
            )

    def ensure_player(self, user_id: int, username: Optional[str]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO players (user_id, username)
                VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE SET username = excluded.username
                """,
                (user_id, username or f"user_{user_id}"),
            )

    def get_player(self, user_id: int) -> Optional[sqlite3.Row]:
        with self._connect() as conn:
            cur = conn.execute("SELECT * FROM players WHERE user_id = ?", (user_id,))
            return cur.fetchone()

    def get_inventory(self, user_id: int) -> List[sqlite3.Row]:
        with self._connect() as conn:
            cur = conn.execute(
                "SELECT item_name, quantity FROM inventory WHERE user_id = ? AND quantity > 0 ORDER BY item_name",
                (user_id,),
            )
            return cur.fetchall()

    def upsert_inventory(self, user_id: int, item_name: str, qty_delta: int) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO inventory (user_id, item_name, quantity)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id, item_name)
                DO UPDATE SET quantity = MAX(0, inventory.quantity + excluded.quantity)
                """,
                (user_id, item_name, qty_delta),
            )

    def update_stats(
        self,
        user_id: int,
        hp: Optional[int] = None,
        gold_delta: int = 0,
        exp_delta: int = 0,
        attack_delta: int = 0,
        set_last_hunt: Optional[int] = None,
    ) -> None:
        with self._connect() as conn:
            player = conn.execute(
                "SELECT level, exp, hp, max_hp, attack, gold FROM players WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            if not player:
                return

            new_exp = player["exp"] + exp_delta
            new_level = player["level"]
            new_max_hp = player["max_hp"]
            while new_exp >= new_level * 100:
                new_exp -= new_level * 100
                new_level += 1
                new_max_hp += 10

            final_hp = player["hp"] if hp is None else max(0, min(hp, new_max_hp))
            final_attack = max(1, player["attack"] + attack_delta)
            final_gold = max(0, player["gold"] + gold_delta)
            if set_last_hunt is not None:
                last_hunt_ts = set_last_hunt
            else:
                last_hunt_ts = conn.execute(
                    "SELECT last_hunt_ts FROM players WHERE user_id = ?", (user_id,)
                ).fetchone()[0]

            conn.execute(
                """
                UPDATE players
                SET level = ?, exp = ?, hp = ?, max_hp = ?, attack = ?, gold = ?, last_hunt_ts = ?
                WHERE user_id = ?
                """,
                (new_level, new_exp, final_hp, new_max_hp, final_attack, final_gold, last_hunt_ts, user_id),
            )

    def set_guild(self, user_id: int, guild_id: int) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE players SET guild_id = ? WHERE user_id = ?", (guild_id, user_id))

    def create_guild(self, name: str, owner_id: int) -> Tuple[bool, str]:
        with self._connect() as conn:
            try:
                conn.execute("INSERT INTO guilds (name, owner_id) VALUES (?, ?)", (name, owner_id))
                gid = conn.execute("SELECT id FROM guilds WHERE name = ?", (name,)).fetchone()[0]
                conn.execute("UPDATE players SET guild_id = ? WHERE user_id = ?", (gid, owner_id))
                return True, f"Guild '{name}' berhasil dibuat."
            except sqlite3.IntegrityError:
                return False, "Nama guild sudah dipakai."

    def join_guild(self, name: str, user_id: int) -> Tuple[bool, str]:
        with self._connect() as conn:
            guild = conn.execute("SELECT id FROM guilds WHERE name = ?", (name,)).fetchone()
            if not guild:
                return False, "Guild tidak ditemukan."
            conn.execute("UPDATE players SET guild_id = ? WHERE user_id = ?", (guild["id"], user_id))
            return True, f"Kamu bergabung ke guild '{name}'."

    def get_guild_info(self, user_id: int) -> str:
        with self._connect() as conn:
            player = conn.execute(
                "SELECT guild_id FROM players WHERE user_id = ?", (user_id,)
            ).fetchone()
            if not player or player["guild_id"] is None:
                return "Kamu belum punya guild. Gunakan /guild create <nama> atau /guild join <nama>."

            guild = conn.execute(
                "SELECT id, name, owner_id FROM guilds WHERE id = ?", (player["guild_id"],)
            ).fetchone()
            members = conn.execute(
                "SELECT username, level FROM players WHERE guild_id = ? ORDER BY level DESC",
                (player["guild_id"],),
            ).fetchall()

            lines = [f"🏰 Guild: {guild['name']} (ID: {guild['id']})"]
            lines.append(f"Owner: {guild['owner_id']}")
            lines.append("Members:")
            for m in members[:15]:
                lines.append(f"- {m['username']} (Lv {m['level']})")
            return "\n".join(lines)

    def get_leaderboard(self, limit: int = 10) -> List[sqlite3.Row]:
        with self._connect() as conn:
            cur = conn.execute(
                "SELECT username, level, exp, gold FROM players ORDER BY level DESC, exp DESC, gold DESC LIMIT ?",
                (limit,),
            )
            return cur.fetchall()

    def create_trade(self, from_user: int, to_user: int, item: str, qty: int, price: int) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO trade_requests (from_user_id, to_user_id, item_name, qty, price, created_ts)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (from_user, to_user, item, qty, price, int(time.time())),
            )
            return cur.lastrowid

    def get_trade(self, trade_id: int) -> Optional[sqlite3.Row]:
        with self._connect() as conn:
            return conn.execute("SELECT * FROM trade_requests WHERE id = ?", (trade_id,)).fetchone()

    def complete_trade(self, trade_id: int) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE trade_requests SET status = 'completed' WHERE id = ?", (trade_id,))


repo = RPGRepository(DB_PATH)


def parse_user_id(raw: str) -> Optional[int]:
    try:
        if raw.startswith("@"):
            return None
        return int(raw)
    except ValueError:
        return None


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    repo.ensure_player(user.id, user.username)
    await update.message.reply_text(
        "Selamat datang di RPG Bot!\n"
        "Perintah utama:\n"
        "/profile, /hunt, /inventory, /item, /shop, /battle, /guild, /leaderboard, /trade\n"
        f"Owner ID: {BOT_OWNER_ID if BOT_OWNER_ID else 'belum diset'}"
    )


async def cmd_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    repo.ensure_player(user.id, user.username)
    p = repo.get_player(user.id)
    await update.message.reply_text(
        f"👤 {p['username']}\n"
        f"Level: {p['level']}\n"
        f"EXP: {p['exp']}/{p['level']*100}\n"
        f"Gold: {p['gold']}\n"
        f"HP: {p['hp']}/{p['max_hp']}\n"
        f"Attack: {p['attack']}"
    )


async def cmd_inventory(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    repo.ensure_player(user.id, user.username)
    inv = repo.get_inventory(user.id)
    if not inv:
        await update.message.reply_text("Inventory kosong.")
        return
    lines = ["🎒 Inventory:"]
    for row in inv:
        lines.append(f"- {row['item_name']}: {row['quantity']}")
    await update.message.reply_text("\n".join(lines))


async def cmd_shop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    user = update.effective_user
    repo.ensure_player(user.id, user.username)

    if not args:
        lines = ["🛒 Shop list:"]
        for name, meta in SHOP_ITEMS.items():
            effect = f"heal +{meta['heal']}" if "heal" in meta else f"attack +{meta['attack']}"
            lines.append(f"- {name}: {meta['price']} gold ({effect})")
        lines.append("\nBeli: /shop buy <item> <qty>")
        await update.message.reply_text("\n".join(lines))
        return

    if args[0] != "buy" or len(args) < 2:
        await update.message.reply_text("Format: /shop buy <item> <qty>")
        return

    item = args[1].lower()
    qty = int(args[2]) if len(args) > 2 and args[2].isdigit() else 1
    if item not in SHOP_ITEMS:
        await update.message.reply_text("Item tidak tersedia.")
        return
    if qty <= 0:
        await update.message.reply_text("Qty harus > 0")
        return

    player = repo.get_player(user.id)
    total = SHOP_ITEMS[item]["price"] * qty
    if player["gold"] < total:
        await update.message.reply_text("Gold tidak cukup.")
        return

    repo.update_stats(user.id, gold_delta=-total)
    repo.upsert_inventory(user.id, item, qty)
    await update.message.reply_text(f"Berhasil beli {qty}x {item} seharga {total} gold.")


async def cmd_item(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    repo.ensure_player(user.id, user.username)

    if len(context.args) < 1:
        await update.message.reply_text("Format: /item use <nama_item>")
        return

    if context.args[0] != "use" or len(context.args) < 2:
        await update.message.reply_text("Format: /item use <nama_item>")
        return

    item = context.args[1].lower()
    inv = {row["item_name"]: row["quantity"] for row in repo.get_inventory(user.id)}
    if inv.get(item, 0) <= 0:
        await update.message.reply_text("Item tidak ada di inventory.")
        return

    if item not in SHOP_ITEMS:
        await update.message.reply_text("Item belum punya efek.")
        return

    player = repo.get_player(user.id)
    if "heal" in SHOP_ITEMS[item]:
        new_hp = min(player["max_hp"], player["hp"] + SHOP_ITEMS[item]["heal"])
        repo.update_stats(user.id, hp=new_hp)
        msg = f"HP dipulihkan menjadi {new_hp}/{player['max_hp']}."
    else:
        repo.update_stats(user.id, attack_delta=SHOP_ITEMS[item]["attack"])
        msg = f"Attack naik +{SHOP_ITEMS[item]['attack']} permanen."

    repo.upsert_inventory(user.id, item, -1)
    await update.message.reply_text(f"Kamu menggunakan {item}. {msg}")


def do_battle(player_hp: int, player_attack: int, monster: Monster) -> Tuple[bool, int, List[str], int]:
    logs: List[str] = [f"⚔️ Kamu bertemu {monster.name}!"]
    m_hp = monster.hp
    p_hp = player_hp

    while p_hp > 0 and m_hp > 0:
        dmg = random.randint(max(1, player_attack - 3), player_attack + 3)
        m_hp -= dmg
        logs.append(f"Kamu menyerang {monster.name} {dmg} damage (HP monster {max(0, m_hp)}).")
        if m_hp <= 0:
            break

        m_dmg = random.randint(monster.attack_min, monster.attack_max)
        p_hp -= m_dmg
        logs.append(f"{monster.name} menyerang balik {m_dmg} damage (HP kamu {max(0, p_hp)}).")

    win = m_hp <= 0
    return win, max(0, p_hp), logs, monster.hp - max(0, m_hp)


async def cmd_hunt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    repo.ensure_player(user.id, user.username)
    player = repo.get_player(user.id)
    now = int(time.time())
    remaining = HUNT_COOLDOWN_SECONDS - (now - player["last_hunt_ts"])
    if remaining > 0:
        await update.message.reply_text(f"Tunggu {remaining} detik sebelum hunt lagi.")
        return

    monster = random.choice(MONSTERS)
    win, hp_left, logs, _ = do_battle(player["hp"], player["attack"], monster)

    if win:
        repo.update_stats(
            user.id,
            hp=hp_left,
            gold_delta=monster.gold_drop,
            exp_delta=monster.exp_drop,
            set_last_hunt=now,
        )
        logs.append(f"✅ Menang! +{monster.exp_drop} EXP, +{monster.gold_drop} Gold")
        if random.random() < 0.4:
            repo.upsert_inventory(user.id, "potion", 1)
            logs.append("🎁 Drop item: potion x1")
    else:
        penalty = min(player["gold"], 15)
        repo.update_stats(user.id, hp=1, gold_delta=-penalty, set_last_hunt=now)
        logs.append(f"❌ Kalah. Kamu kehilangan {penalty} gold dan HP jadi 1.")

    await update.message.reply_text("\n".join(logs[:20]))


async def cmd_battle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    repo.ensure_player(user.id, user.username)
    player = repo.get_player(user.id)
    monster = random.choice(MONSTERS)
    win, hp_left, logs, _ = do_battle(player["hp"], player["attack"], monster)
    if win:
        reward_gold = monster.gold_drop // 2
        reward_exp = monster.exp_drop // 2
        repo.update_stats(user.id, hp=hp_left, gold_delta=reward_gold, exp_delta=reward_exp)
        logs.append(f"Sparring selesai: +{reward_exp} EXP, +{reward_gold} Gold")
    else:
        repo.update_stats(user.id, hp=max(1, hp_left))
        logs.append("Kamu kalah di battle latihan.")

    await update.message.reply_text("\n".join(logs[:20]))


async def cmd_guild(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    repo.ensure_player(user.id, user.username)

    if not context.args:
        await update.message.reply_text(repo.get_guild_info(user.id))
        return

    action = context.args[0].lower()
    if action == "create" and len(context.args) >= 2:
        ok, msg = repo.create_guild(" ".join(context.args[1:]), user.id)
        await update.message.reply_text(("✅ " if ok else "❌ ") + msg)
    elif action == "join" and len(context.args) >= 2:
        ok, msg = repo.join_guild(" ".join(context.args[1:]), user.id)
        await update.message.reply_text(("✅ " if ok else "❌ ") + msg)
    else:
        await update.message.reply_text("Format: /guild create <nama> | /guild join <nama> | /guild")


async def cmd_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = repo.get_leaderboard(limit=10)
    if not data:
        await update.message.reply_text("Belum ada player.")
        return

    lines = ["🏆 Leaderboard Top 10"]
    for i, row in enumerate(data, start=1):
        lines.append(f"{i}. {row['username']} | Lv {row['level']} | EXP {row['exp']} | Gold {row['gold']}")
    await update.message.reply_text("\n".join(lines))


async def cmd_trade(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    repo.ensure_player(user.id, user.username)

    if not context.args:
        await update.message.reply_text(
            "Trade command:\n"
            "/trade offer <to_user_id> <item> <qty> <price>\n"
            "/trade accept <trade_id>"
        )
        return

    action = context.args[0].lower()

    if action == "offer" and len(context.args) == 5:
        to_user = parse_user_id(context.args[1])
        item = context.args[2].lower()
        if not to_user:
            await update.message.reply_text("Gunakan numeric user_id tujuan.")
            return

        try:
            qty = int(context.args[3])
            price = int(context.args[4])
        except ValueError:
            await update.message.reply_text("Qty dan price harus angka.")
            return

        if qty <= 0 or price < 0:
            await update.message.reply_text("Qty harus >0 dan price >=0.")
            return

        inv = {row["item_name"]: row["quantity"] for row in repo.get_inventory(user.id)}
        if inv.get(item, 0) < qty:
            await update.message.reply_text("Item kamu tidak cukup.")
            return

        if not repo.get_player(to_user):
            await update.message.reply_text("User tujuan belum terdaftar (minta dia /start dulu).")
            return

        trade_id = repo.create_trade(user.id, to_user, item, qty, price)
        await update.message.reply_text(
            f"Offer dibuat. ID trade: {trade_id}.\n"
            f"Penerima bisa /trade accept {trade_id}"
        )
        return

    if action == "accept" and len(context.args) == 2:
        try:
            trade_id = int(context.args[1])
        except ValueError:
            await update.message.reply_text("Trade ID tidak valid.")
            return

        trade = repo.get_trade(trade_id)
        if not trade or trade["status"] != "pending":
            await update.message.reply_text("Trade tidak ditemukan / sudah diproses.")
            return
        if trade["to_user_id"] != user.id:
            await update.message.reply_text("Kamu bukan penerima trade ini.")
            return

        from_user = repo.get_player(trade["from_user_id"])
        to_user = repo.get_player(trade["to_user_id"])
        from_inv = {row["item_name"]: row["quantity"] for row in repo.get_inventory(from_user["user_id"])}

        if from_inv.get(trade["item_name"], 0) < trade["qty"]:
            await update.message.reply_text("Trade gagal: stok item pengirim tidak cukup.")
            return
        if to_user["gold"] < trade["price"]:
            await update.message.reply_text("Gold kamu tidak cukup untuk menerima trade.")
            return

        repo.upsert_inventory(from_user["user_id"], trade["item_name"], -trade["qty"])
        repo.upsert_inventory(to_user["user_id"], trade["item_name"], trade["qty"])
        repo.update_stats(from_user["user_id"], gold_delta=trade["price"])
        repo.update_stats(to_user["user_id"], gold_delta=-trade["price"])
        repo.complete_trade(trade_id)
        await update.message.reply_text("✅ Trade berhasil diselesaikan.")
        return

    await update.message.reply_text("Format salah. Cek: /trade")


def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("Set TELEGRAM_BOT_TOKEN sebelum menjalankan bot.")
    if BOT_OWNER_ID <= 0:
        logger.warning("BOT_OWNER_ID belum diset. Set di environment/.env agar fitur owner siap dipakai.")

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("profile", cmd_profile))
    app.add_handler(CommandHandler("hunt", cmd_hunt))
    app.add_handler(CommandHandler("inventory", cmd_inventory))
    app.add_handler(CommandHandler("item", cmd_item))
    app.add_handler(CommandHandler("shop", cmd_shop))
    app.add_handler(CommandHandler("battle", cmd_battle))
    app.add_handler(CommandHandler("guild", cmd_guild))
    app.add_handler(CommandHandler("leaderboard", cmd_leaderboard))
    app.add_handler(CommandHandler("trade", cmd_trade))

    logger.info("Bot running...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
