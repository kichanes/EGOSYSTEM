import logging
import os
import random
import sqlite3
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

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


@dataclass
class Area:
    id: int
    name: str
    level_min: int
    level_max: int
    monsters: List[str]
    boss: str


MONSTERS: List[Monster] = [
    Monster("Slime", 18, 2, 6, 10, 12),
    Monster("Goblin", 26, 4, 9, 18, 20),
    Monster("Wolf", 32, 5, 10, 24, 25),
    Monster("Orc", 45, 6, 13, 38, 40),
    Monster("Mini Dragon", 65, 8, 17, 60, 72),
]

SHOP_ITEMS: Dict[str, Dict[str, object]] = {
    "potion": {"price": 25, "type": "consumable", "name": "Potion", "heal": 30, "rarity": "Common"},
    "elixir": {"price": 70, "type": "consumable", "name": "Elixir", "exp": 40, "rarity": "Uncommon"},
    "antidote": {"price": 45, "type": "consumable", "name": "Antidote", "cure": "poison", "rarity": "Common"},
    "wood_sword": {"price": 90, "type": "weapon", "name": "Wood Sword", "atk": 5, "crit": 0, "rarity": "Common"},
    "iron_sword": {"price": 180, "type": "weapon", "name": "Iron Sword", "atk": 10, "crit": 0, "rarity": "Rare"},
    "flame_sword": {"price": 350, "type": "weapon", "name": "Flame Sword", "atk": 12, "crit": 10, "rarity": "Epic"},
    "iron_armor": {"price": 220, "type": "armor", "name": "Iron Armor", "hp": 20, "def": 8, "rarity": "Rare"},
    "ring_of_luck": {"price": 300, "type": "accessory", "name": "Ring of Luck", "drop_rate": 5, "rarity": "Epic"},
    "amulet_of_power": {"price": 320, "type": "accessory", "name": "Amulet of Power", "atk": 5, "def": 5, "rarity": "Epic"},
    "wood": {"price": 10, "type": "material", "name": "Wood", "rarity": "Common"},
    "iron": {"price": 20, "type": "material", "name": "Iron", "rarity": "Uncommon"},
    "crystal": {"price": 45, "type": "material", "name": "Crystal", "rarity": "Rare"},
    "dungeon_key": {"price": 200, "type": "special", "name": "Dungeon Key", "rarity": "Legendary"},
}

PET_BONUS: Dict[str, Dict[str, int]] = {
    "None": {"atk": 0, "def": 0, "hp": 0},
    "Fire Wolf": {"atk": 5, "def": 0, "hp": 0},
}

RARITY_ICON = {
    "Common": "⚪",
    "Uncommon": "🟢",
    "Rare": "🔵",
    "Epic": "🟣",
    "Legendary": "🟠",
    "Mythic": "🔴",
}

MONSTER_DROPS: Dict[str, List[Tuple[str, int]]] = {
    "Slime": [("gel", 80), ("potion", 30), ("wood_sword", 5)],
    "Goblin": [("iron", 40), ("antidote", 20), ("iron_sword", 5)],
    "Wolf": [("potion", 35), ("wood", 60), ("ring_of_luck", 3)],
    "Orc": [("iron_armor", 8), ("elixir", 25), ("crystal", 15)],
    "Mini Dragon": [("flame_sword", 8), ("dungeon_key", 20), ("crystal", 35)],
}

AREAS: List[Area] = [
    Area(1, "Forest", 1, 5, ["Slime", "Goblin", "Boar"], "Goblin King"),
    Area(2, "Desert", 5, 10, ["Scorpion", "Sand Worm", "Mummy"], "Desert Guardian"),
    Area(3, "Mountain", 10, 15, ["Wolf", "Eagle", "Golem"], "Mountain Golem"),
    Area(4, "Ocean", 15, 20, ["Crab", "Pirate", "Serpent"], "Pirate Captain"),
    Area(5, "Volcano", 20, 25, ["Fire Spirit", "Lava Beast", "Fire Demon"], "Flame Dragon"),
    Area(6, "Dark Forest", 25, 30, ["Skeleton", "Witch", "Shadow Beast"], "Necromancer"),
    Area(7, "Kingdom War", 30, 35, ["Knight", "Archer", "Mage"], "Corrupted King"),
    Area(8, "Ice Land", 35, 40, ["Ice Wolf", "Frost Giant", "Ice Spirit"], "Ice Queen"),
    Area(9, "Sky Realm", 40, 45, ["Thunder Bird", "Angel", "Storm Beast"], "Sky Guardian"),
    Area(10, "Abyss", 45, 55, ["Demon", "Void Creature", "Dark Knight"], "Demon King"),
    Area(11, "Celestial Realm", 55, 65, ["Light Spirit", "Celestial Guard", "Star Beast"], "Divine Dragon"),
    Area(12, "Void Dimension", 65, 75, ["Void Spawn", "Chaos Beast", "Time Phantom"], "Void God"),
]


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
            self._migrate_players_columns(conn)

    def _migrate_players_columns(self, conn: sqlite3.Connection) -> None:
        existing_cols = {
            row["name"] for row in conn.execute("PRAGMA table_info(players)").fetchall()
        }
        required_columns = {
            "defense": "INTEGER NOT NULL DEFAULT 5",
            "area": "TEXT NOT NULL DEFAULT 'Grassland'",
            "gems": "INTEGER NOT NULL DEFAULT 0",
            "weapon": "TEXT NOT NULL DEFAULT 'Wooden Sword'",
            "armor": "TEXT NOT NULL DEFAULT 'Leather Armor'",
            "pet": "TEXT NOT NULL DEFAULT 'None'",
            "base_hp": "INTEGER NOT NULL DEFAULT 100",
            "base_attack": "INTEGER NOT NULL DEFAULT 10",
            "base_defense": "INTEGER NOT NULL DEFAULT 5",
            "equipped_weapon": "TEXT NOT NULL DEFAULT 'None'",
            "equipped_armor": "TEXT NOT NULL DEFAULT 'None'",
            "equipped_accessory": "TEXT NOT NULL DEFAULT 'None'",
            "current_area_id": "INTEGER NOT NULL DEFAULT 1",
            "unlocked_area_id": "INTEGER NOT NULL DEFAULT 1",
        }
        for col, definition in required_columns.items():
            if col not in existing_cols:
                conn.execute(f"ALTER TABLE players ADD COLUMN {col} {definition}")

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
                "SELECT level, exp, hp, max_hp, attack, gold, base_hp FROM players WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            if not player:
                return

            new_exp = player["exp"] + exp_delta
            new_level = player["level"]
            new_max_hp = player["max_hp"]
            new_base_hp = player["base_hp"]
            while new_exp >= new_level * 100:
                new_exp -= new_level * 100
                new_level += 1
                new_max_hp += 10
                new_base_hp += 10

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
                SET level = ?, exp = ?, hp = ?, max_hp = ?, base_hp = ?, attack = ?, gold = ?, last_hunt_ts = ?
                WHERE user_id = ?
                """,
                (new_level, new_exp, final_hp, new_max_hp, new_base_hp, final_attack, final_gold, last_hunt_ts, user_id),
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
                "SELECT user_id, username, level, exp, gold FROM players ORDER BY level DESC, exp DESC, gold DESC LIMIT ?",
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


def get_player_rank(user_id: int) -> Optional[int]:
    board = repo.get_leaderboard(limit=10000)
    for idx, row in enumerate(board, start=1):
        if row["user_id"] == user_id:
            return idx
    return None


def get_equipment_bonus(item_key: str, slot: str) -> Dict[str, int]:
    empty = {"atk": 0, "def": 0, "hp": 0, "crit": 0, "drop_rate": 0, "dodge": 0}
    if item_key == "None":
        return empty
    item = SHOP_ITEMS.get(item_key, {})
    if not item or item.get("type") != slot:
        return empty
    return {
        "atk": int(item.get("atk", 0)),
        "def": int(item.get("def", 0)),
        "hp": int(item.get("hp", 0)),
        "crit": int(item.get("crit", 0)),
        "drop_rate": int(item.get("drop_rate", 0)),
        "dodge": int(item.get("dodge", 0)),
    }


def compute_total_stats(player: sqlite3.Row) -> Dict[str, int]:
    weapon_bonus = get_equipment_bonus(player["equipped_weapon"], "weapon")
    armor_bonus = get_equipment_bonus(player["equipped_armor"], "armor")
    accessory_bonus = get_equipment_bonus(player["equipped_accessory"], "accessory")
    pet_bonus = PET_BONUS.get(player["pet"], {"atk": 0, "def": 0, "hp": 0})
    total_hp = int(player["base_hp"]) + weapon_bonus["hp"] + armor_bonus["hp"] + accessory_bonus["hp"] + int(pet_bonus["hp"])
    total_atk = int(player["base_attack"]) + weapon_bonus["atk"] + armor_bonus["atk"] + accessory_bonus["atk"] + int(pet_bonus["atk"])
    total_def = int(player["base_defense"]) + weapon_bonus["def"] + armor_bonus["def"] + accessory_bonus["def"] + int(pet_bonus["def"])
    return {
        "hp": total_hp,
        "atk": total_atk,
        "def": total_def,
        "crit": weapon_bonus["crit"] + accessory_bonus["crit"],
        "drop_rate": accessory_bonus["drop_rate"],
        "dodge": accessory_bonus["dodge"],
    }


def roll_drops(monster_name: str, extra_drop_rate: int = 0) -> List[str]:
    drops: List[str] = []
    for item_name, base_chance in MONSTER_DROPS.get(monster_name, []):
        chance = min(100, base_chance + extra_drop_rate)
        if random.randint(1, 100) <= chance:
            drops.append(item_name)
    return drops


def get_area_by_id(area_id: int) -> Area:
    for area in AREAS:
        if area.id == area_id:
            return area
    return AREAS[0]


def make_scaled_monster(monster_name: str, area_id: int, is_boss: bool = False) -> Monster:
    hp = int(20 * (1.25 ** (area_id - 1)))
    atk_min = int(3 * (1.15 ** (area_id - 1)))
    atk_max = max(atk_min + 2, int(6 * (1.15 ** (area_id - 1))))
    gold = int(12 * (1.2 ** (area_id - 1)))
    exp = int(15 * (1.25 ** (area_id - 1)))
    if is_boss:
        hp = int(hp * 2.4)
        atk_min = int(atk_min * 1.6)
        atk_max = int(atk_max * 1.7)
        gold = int(gold * 3.5)
        exp = int(exp * 4)
    return Monster(monster_name, hp, atk_min, atk_max, gold, exp)


def parse_user_id(raw: str) -> Optional[int]:
    try:
        if raw.startswith("@"):
            return None
        return int(raw)
    except ValueError:
        return None


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("⚔️ Battle", callback_data="menu:battle")],
            [
                InlineKeyboardButton("🎒 Inventory", callback_data="menu:inventory"),
                InlineKeyboardButton("👤 Profile", callback_data="menu:profile"),
            ],
            [
                InlineKeyboardButton("🛒 Shop", callback_data="menu:shop"),
                InlineKeyboardButton("🌍 Area", callback_data="menu:area"),
            ],
            [
                InlineKeyboardButton("🎁 Reward", callback_data="menu:reward"),
                InlineKeyboardButton("❓ Help", callback_data="menu:help"),
            ],
        ]
    )


def back_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Menu", callback_data="menu:main")]])


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    repo.ensure_player(user.id, user.username)
    await update.effective_message.reply_text(
        f"🎮 RPG BOT\n\nSelamat datang, {user.username or f'user_{user.id}'}!\n\nPilih menu:",
        reply_markup=main_menu_keyboard(),
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "📱 Command dasar:\n"
        "/start, /profile (/p), /inventory (/inv), /help\n\n"
        "⚔️ Battle:\n"
        "/hunt (/ht), /adventure (/adv), /fight (/f), /boss, /dungeon (/dg)\n\n"
        "🎒 Item:\n"
        "/equip (/eq), /unequip (/uneq), /use, /drop\n\n"
        "🛒 Ekonomi:\n"
        "/shop (/sh), /buy, /sell, /balance (/bal)\n\n"
        "🌍 Area:\n"
        "/area (/a), /travel (/go), /unlock (/ul)\n\n"
        "👥 Sosial:\n"
        "/leaderboard (/top), /guild (/g), /duel\n"
    )
    await update.effective_message.reply_text(text)


async def on_menu_click(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    repo.ensure_player(user.id, user.username)
    data = query.data or ""

    if data == "menu:main":
        await query.edit_message_text(
            f"🎮 RPG BOT\n\nSelamat datang, {user.username or f'user_{user.id}'}!\n\nPilih menu:",
            reply_markup=main_menu_keyboard(),
        )
        return

    if data == "menu:battle":
        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("🏹 Hunt", callback_data="action:hunt"), InlineKeyboardButton("🗺️ Adventure", callback_data="action:adv")],
                [InlineKeyboardButton("👑 Boss", callback_data="action:boss"), InlineKeyboardButton("🏰 Dungeon", callback_data="action:dg")],
                [InlineKeyboardButton("🔙 Back", callback_data="menu:main")],
            ]
        )
        await query.edit_message_text("⚔️ BATTLE MENU\n\nPilih aksi:", reply_markup=kb)
        return

    if data == "menu:inventory":
        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("⚔️ Equip", callback_data="menu:equip"), InlineKeyboardButton("🧃 Use Item", callback_data="menu:use")],
                [InlineKeyboardButton("🗑️ Drop", callback_data="menu:drop")],
                [InlineKeyboardButton("🔙 Back", callback_data="menu:main")],
            ]
        )
        await query.edit_message_text("🎒 INVENTORY\nGunakan /inv untuk daftar item.", reply_markup=kb)
        return
    if data == "menu:equip":
        await query.edit_message_text("⚔️ EQUIP\nGunakan /eq <item_key>\nContoh: /eq wood_sword", reply_markup=back_menu_keyboard())
        return
    if data == "menu:use":
        await query.edit_message_text("🧃 USE ITEM\nGunakan /use <item_key>\nContoh: /use potion", reply_markup=back_menu_keyboard())
        return
    if data == "menu:drop":
        await query.edit_message_text("🗑️ DROP ITEM\nGunakan /drop <item_key> <qty>", reply_markup=back_menu_keyboard())
        return

    if data == "menu:profile":
        await query.message.reply_text("Membuka profile...")
        await cmd_profile(update, context)
        await query.message.reply_text("Pilih aksi:", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⚔️ Equipment", callback_data="menu:equip")],
            [InlineKeyboardButton("🎒 Inventory", callback_data="menu:inventory")],
            [InlineKeyboardButton("🔙 Back", callback_data="menu:main")],
        ]))
        return

    if data == "menu:shop":
        await query.edit_message_text(
            "🛒 SHOP\nGunakan /shop atau /buy <item> <qty>.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🧃 Potion", callback_data="shop:buy:potion"), InlineKeyboardButton("🗡️ Wood Sword", callback_data="shop:buy:wood_sword")],
                [InlineKeyboardButton("🔙 Back", callback_data="menu:main")],
            ]),
        )
        return

    if data == "menu:area":
        await query.message.reply_text("Membuka area...")
        await cmd_area(update, context)
        await query.message.reply_text("Gunakan /go <id> untuk pindah area.", reply_markup=back_menu_keyboard())
        return

    if data == "menu:reward":
        await query.edit_message_text(
            "🎁 REWARD\nPilih reward:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🎁 Daily", callback_data="reward:daily"), InlineKeyboardButton("📅 Weekly", callback_data="reward:weekly")],
                [InlineKeyboardButton("🔙 Back", callback_data="menu:main")],
            ]),
        )
        return

    if data == "menu:help":
        await query.edit_message_text(
            "❓ HELP\nGunakan tombol untuk bermain:\n- Battle untuk fight\n- Inventory untuk item\n- Shop untuk beli",
            reply_markup=back_menu_keyboard(),
        )
        return

    if data.startswith("action:"):
        action = data.split(":", 1)[1]
        if action == "hunt":
            await cmd_hunt(update, context)
            await query.message.reply_text("Lanjut?", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔁 Hunt Lagi", callback_data="action:hunt"), InlineKeyboardButton("🔙 Menu", callback_data="menu:main")]
            ]))
        elif action == "adv":
            await cmd_adventure(update, context)
        elif action == "boss":
            await cmd_boss(update, context)
        elif action == "dg":
            await cmd_dungeon(update, context)
        return

    if data.startswith("shop:buy:"):
        item = data.split(":")[-1]
        context.args = [item, "1"]
        await cmd_buy(update, context)
        await query.message.reply_text("Lanjut belanja?", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🛒 Shop", callback_data="menu:shop"), InlineKeyboardButton("🏠 Menu", callback_data="menu:main")]
        ]))
        return

    if data.startswith("reward:"):
        kind = data.split(":")[-1]
        reward = 50 if kind == "daily" else 200
        repo.update_stats(user.id, gold_delta=reward)
        await query.message.reply_text(f"✅ Reward {kind} diklaim: +{reward} gold")


async def cmd_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    repo.ensure_player(user.id, user.username)
    p = repo.get_player(user.id)
    current_area = get_area_by_id(int(p["current_area_id"]))
    rank = get_player_rank(user.id)
    exp_target = p["level"] * 100
    total = compute_total_stats(p)
    equipped_weapon_name = "None"
    equipped_armor_name = "None"
    if p["equipped_weapon"] != "None":
        equipped_weapon_name = str(SHOP_ITEMS[p["equipped_weapon"]]["name"])
    if p["equipped_armor"] != "None":
        equipped_armor_name = str(SHOP_ITEMS[p["equipped_armor"]]["name"])
    inventory_count = sum(row["quantity"] for row in repo.get_inventory(user.id))
    await update.effective_message.reply_text(
        "╔═══════════〔 PROFILE 〕═══════════╗\n"
        f"👤 Nama     : {p['username']}\n"
        f"🎖️ Level    : {p['level']} (EXP: {p['exp']}/{exp_target})\n"
        f"🌍 Area     : {current_area.name}\n"
        f"❤️ HP       : {p['hp']} / {total['hp']}\n"
        f"⚔️ ATK      : {total['atk']}\n"
        f"🛡️ DEF      : {total['def']}\n\n"
        f"💰 Gold     : {p['gold']:,}\n"
        f"💎 Gems     : {p['gems']:,}\n\n"
        f"🗡️ Weapon   : {equipped_weapon_name}\n"
        f"🛡️ Armor    : {equipped_armor_name}\n\n"
        f"🎒 Inventory: {inventory_count} items\n"
        f"🐾 Pet      : {p['pet']}\n\n"
        f"🏆 Rank     : #{rank if rank else '-'}\n"
        "╚════════════════════════════════╝"
    )


async def cmd_inventory(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    repo.ensure_player(user.id, user.username)
    inv = repo.get_inventory(user.id)
    if not inv:
        await update.effective_message.reply_text("Inventory kosong.")
        return
    lines = ["🎒 Inventory:"]
    for row in inv:
        lines.append(f"- {row['item_name']}: {row['quantity']}")
    await update.effective_message.reply_text("\n".join(lines))


async def cmd_shop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    user = update.effective_user
    repo.ensure_player(user.id, user.username)

    if not args:
        lines = ["🛒 Shop list:"]
        for name, meta in SHOP_ITEMS.items():
            if meta["type"] == "consumable":
                effect = f"heal +{meta.get('heal', 0)} | exp +{meta.get('exp', 0)}"
            elif meta["type"] == "weapon":
                effect = f"ATK +{meta['atk']} | Crit +{meta.get('crit', 0)}%"
            elif meta["type"] == "armor":
                effect = f"HP +{meta.get('hp', 0)} | DEF +{meta.get('def', 0)}"
            elif meta["type"] == "accessory":
                effect = f"ATK +{meta.get('atk', 0)} | DEF +{meta.get('def', 0)} | Drop +{meta.get('drop_rate', 0)}%"
            else:
                effect = f"Kategori: {meta['type']}"
            rarity = str(meta.get("rarity", "Common"))
            lines.append(f"- {name}: {meta['price']} gold ({effect}) {RARITY_ICON.get(rarity, '⚪')} {rarity}")
        lines.append("\nBeli: /shop buy <item> <qty>")
        lines.append("Equip: /item equip <item_key>")
        await update.effective_message.reply_text("\n".join(lines))
        return

    if args[0] != "buy" or len(args) < 2:
        await update.effective_message.reply_text("Format: /shop buy <item> <qty>")
        return

    item = args[1].lower()
    qty = int(args[2]) if len(args) > 2 and args[2].isdigit() else 1
    if item not in SHOP_ITEMS:
        await update.effective_message.reply_text("Item tidak tersedia.")
        return
    if qty <= 0:
        await update.effective_message.reply_text("Qty harus > 0")
        return

    player = repo.get_player(user.id)
    total = int(SHOP_ITEMS[item]["price"]) * qty
    if player["gold"] < total:
        await update.effective_message.reply_text("Gold tidak cukup.")
        return

    repo.update_stats(user.id, gold_delta=-total)
    repo.upsert_inventory(user.id, item, qty)
    await update.effective_message.reply_text(f"Berhasil beli {qty}x {item} seharga {total} gold.")


async def cmd_item(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    repo.ensure_player(user.id, user.username)

    if len(context.args) < 1:
        await update.effective_message.reply_text("Format: /item use <nama_item> | /item equip <item_key>")
        return

    if context.args[0] not in {"use", "equip"} or len(context.args) < 2:
        await update.effective_message.reply_text("Format: /item use <nama_item> | /item equip <item_key>")
        return

    action = context.args[0]
    item = context.args[1].lower()
    inv = {row["item_name"]: row["quantity"] for row in repo.get_inventory(user.id)}
    if inv.get(item, 0) <= 0:
        await update.effective_message.reply_text("Item tidak ada di inventory.")
        return

    if item not in SHOP_ITEMS:
        await update.effective_message.reply_text("Item belum punya efek.")
        return

    meta = SHOP_ITEMS[item]
    player = repo.get_player(user.id)

    if action == "use":
        if meta["type"] != "consumable":
            await update.effective_message.reply_text("Item ini bukan consumable. Gunakan /item equip <item_key>.")
            return
        total = compute_total_stats(player)
        heal = int(meta.get("heal", 0))
        bonus_exp = int(meta.get("exp", 0))
        new_hp = min(total["hp"], player["hp"] + heal)
        repo.update_stats(user.id, hp=new_hp, exp_delta=bonus_exp)
        repo.upsert_inventory(user.id, item, -1)
        await update.effective_message.reply_text(
            f"Kamu menggunakan {item}. HP {new_hp}/{total['hp']}, EXP +{bonus_exp}."
        )
        return

    if meta["type"] == "weapon":
        with repo._connect() as conn:
            conn.execute("UPDATE players SET equipped_weapon = ? WHERE user_id = ?", (item, user.id))
        await update.effective_message.reply_text(f"✅ Weapon {meta['name']} berhasil di-equip.")
    elif meta["type"] == "armor":
        with repo._connect() as conn:
            conn.execute("UPDATE players SET equipped_armor = ? WHERE user_id = ?", (item, user.id))
        await update.effective_message.reply_text(f"✅ Armor {meta['name']} berhasil di-equip.")
    elif meta["type"] == "accessory":
        with repo._connect() as conn:
            conn.execute("UPDATE players SET equipped_accessory = ? WHERE user_id = ?", (item, user.id))
        await update.effective_message.reply_text(f"✅ Accessory {meta['name']} berhasil di-equip.")
    else:
        await update.effective_message.reply_text("Item ini tidak bisa di-equip.")


async def cmd_use(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.args = ["use", *context.args]
    await cmd_item(update, context)


async def cmd_equip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.args = ["equip", *context.args]
    await cmd_item(update, context)


async def cmd_unequip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    repo.ensure_player(user.id, user.username)
    if not context.args:
        await update.effective_message.reply_text("Format: /unequip weapon|armor|accessory")
        return
    slot = context.args[0].lower()
    field_map = {"weapon": "equipped_weapon", "armor": "equipped_armor", "accessory": "equipped_accessory"}
    if slot not in field_map:
        await update.effective_message.reply_text("Slot tidak valid.")
        return
    with repo._connect() as conn:
        conn.execute(f"UPDATE players SET {field_map[slot]} = 'None' WHERE user_id = ?", (user.id,))
    await update.effective_message.reply_text(f"✅ {slot} berhasil dilepas.")


async def cmd_buy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.args = ["buy", *context.args]
    await cmd_shop(update, context)


async def cmd_balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    repo.ensure_player(user.id, user.username)
    p = repo.get_player(user.id)
    await update.effective_message.reply_text(f"💰 Gold: {p['gold']:,}\n💎 Gems: {p['gems']:,}")


async def cmd_travel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.args = ["move", *context.args]
    await cmd_area(update, context)


def do_battle(player_hp: int, player_attack: int, player_defense: int, crit_chance: int, dodge_chance: int, monster: Monster) -> Tuple[bool, int, List[str], int]:
    logs: List[str] = [f"⚔️ Kamu bertemu {monster.name}!"]
    m_hp = monster.hp
    p_hp = player_hp

    while p_hp > 0 and m_hp > 0:
        dmg = random.randint(max(1, player_attack - 3), player_attack + 3)
        if crit_chance > 0 and random.randint(1, 100) <= crit_chance:
            dmg *= 2
            logs.append("🔥 Critical Hit!")
        m_hp -= dmg
        logs.append(f"Kamu menyerang {monster.name} {dmg} damage (HP monster {max(0, m_hp)}).")
        if m_hp <= 0:
            break

        if dodge_chance > 0 and random.randint(1, 100) <= dodge_chance:
            logs.append("💨 Kamu berhasil dodge serangan monster!")
            continue
        raw_m_dmg = random.randint(monster.attack_min, monster.attack_max)
        m_dmg = max(1, raw_m_dmg - player_defense)
        p_hp -= m_dmg
        logs.append(
            f"{monster.name} menyerang balik {m_dmg} damage "
            f"(raw {raw_m_dmg} - DEF {player_defense}, HP kamu {max(0, p_hp)})."
        )

    win = m_hp <= 0
    return win, max(0, p_hp), logs, monster.hp - max(0, m_hp)


async def cmd_hunt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    repo.ensure_player(user.id, user.username)
    player = repo.get_player(user.id)
    total = compute_total_stats(player)
    area = get_area_by_id(int(player["current_area_id"]))
    now = int(time.time())
    remaining = HUNT_COOLDOWN_SECONDS - (now - player["last_hunt_ts"])
    if remaining > 0:
        await update.effective_message.reply_text(f"Tunggu {remaining} detik sebelum hunt lagi.")
        return

    monster = make_scaled_monster(random.choice(area.monsters), area.id)
    win, hp_left, logs, _ = do_battle(player["hp"], total["atk"], total["def"], total["crit"], total["dodge"], monster)

    if win:
        repo.update_stats(
            user.id,
            hp=hp_left,
            gold_delta=monster.gold_drop,
            exp_delta=monster.exp_drop,
            set_last_hunt=now,
        )
        logs.append(f"✅ Menang! +{monster.exp_drop} EXP, +{monster.gold_drop} Gold")
        dropped_items = roll_drops(monster.name, extra_drop_rate=total["drop_rate"])
        for item_name in dropped_items:
            repo.upsert_inventory(user.id, item_name, 1)
            logs.append(f"🎁 Drop item: {item_name} x1")
    else:
        penalty = min(player["gold"], 15)
        repo.update_stats(user.id, hp=1, gold_delta=-penalty, set_last_hunt=now)
        logs.append(f"❌ Kalah. Kamu kehilangan {penalty} gold dan HP jadi 1.")

    await update.effective_message.reply_text("\n".join(logs[:20]))


async def cmd_battle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    repo.ensure_player(user.id, user.username)
    player = repo.get_player(user.id)
    total = compute_total_stats(player)
    area = get_area_by_id(int(player["current_area_id"]))
    monster = make_scaled_monster(random.choice(area.monsters), area.id)
    win, hp_left, logs, _ = do_battle(player["hp"], total["atk"], total["def"], total["crit"], total["dodge"], monster)
    if win:
        reward_gold = monster.gold_drop // 2
        reward_exp = monster.exp_drop // 2
        repo.update_stats(user.id, hp=hp_left, gold_delta=reward_gold, exp_delta=reward_exp)
        logs.append(f"Sparring selesai: +{reward_exp} EXP, +{reward_gold} Gold")
    else:
        repo.update_stats(user.id, hp=max(1, hp_left))
        logs.append("Kamu kalah di battle latihan.")

    await update.effective_message.reply_text("\n".join(logs[:20]))


async def cmd_guild(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    repo.ensure_player(user.id, user.username)

    if not context.args:
        await update.effective_message.reply_text(repo.get_guild_info(user.id))
        return

    action = context.args[0].lower()
    if action == "create" and len(context.args) >= 2:
        ok, msg = repo.create_guild(" ".join(context.args[1:]), user.id)
        await update.effective_message.reply_text(("✅ " if ok else "❌ ") + msg)
    elif action == "join" and len(context.args) >= 2:
        ok, msg = repo.join_guild(" ".join(context.args[1:]), user.id)
        await update.effective_message.reply_text(("✅ " if ok else "❌ ") + msg)
    else:
        await update.effective_message.reply_text("Format: /guild create <nama> | /guild join <nama> | /guild")


async def cmd_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = repo.get_leaderboard(limit=10)
    if not data:
        await update.effective_message.reply_text("Belum ada player.")
        return

    lines = ["🏆 Leaderboard Top 10"]
    for i, row in enumerate(data, start=1):
        lines.append(f"{i}. {row['username']} | Lv {row['level']} | EXP {row['exp']} | Gold {row['gold']}")
    await update.effective_message.reply_text("\n".join(lines))


async def cmd_trade(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    repo.ensure_player(user.id, user.username)

    if not context.args:
        await update.effective_message.reply_text(
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
            await update.effective_message.reply_text("Gunakan numeric user_id tujuan.")
            return

        try:
            qty = int(context.args[3])
            price = int(context.args[4])
        except ValueError:
            await update.effective_message.reply_text("Qty dan price harus angka.")
            return

        if qty <= 0 or price < 0:
            await update.effective_message.reply_text("Qty harus >0 dan price >=0.")
            return

        inv = {row["item_name"]: row["quantity"] for row in repo.get_inventory(user.id)}
        if inv.get(item, 0) < qty:
            await update.effective_message.reply_text("Item kamu tidak cukup.")
            return

        if not repo.get_player(to_user):
            await update.effective_message.reply_text("User tujuan belum terdaftar (minta dia /start dulu).")
            return

        trade_id = repo.create_trade(user.id, to_user, item, qty, price)
        await update.effective_message.reply_text(
            f"Offer dibuat. ID trade: {trade_id}.\n"
            f"Penerima bisa /trade accept {trade_id}"
        )
        return

    if action == "accept" and len(context.args) == 2:
        try:
            trade_id = int(context.args[1])
        except ValueError:
            await update.effective_message.reply_text("Trade ID tidak valid.")
            return

        trade = repo.get_trade(trade_id)
        if not trade or trade["status"] != "pending":
            await update.effective_message.reply_text("Trade tidak ditemukan / sudah diproses.")
            return
        if trade["to_user_id"] != user.id:
            await update.effective_message.reply_text("Kamu bukan penerima trade ini.")
            return

        from_user = repo.get_player(trade["from_user_id"])
        to_user = repo.get_player(trade["to_user_id"])
        from_inv = {row["item_name"]: row["quantity"] for row in repo.get_inventory(from_user["user_id"])}

        if from_inv.get(trade["item_name"], 0) < trade["qty"]:
            await update.effective_message.reply_text("Trade gagal: stok item pengirim tidak cukup.")
            return
        if to_user["gold"] < trade["price"]:
            await update.effective_message.reply_text("Gold kamu tidak cukup untuk menerima trade.")
            return

        repo.upsert_inventory(from_user["user_id"], trade["item_name"], -trade["qty"])
        repo.upsert_inventory(to_user["user_id"], trade["item_name"], trade["qty"])
        repo.update_stats(from_user["user_id"], gold_delta=trade["price"])
        repo.update_stats(to_user["user_id"], gold_delta=-trade["price"])
        repo.complete_trade(trade_id)
        await update.effective_message.reply_text("✅ Trade berhasil diselesaikan.")
        return

    await update.effective_message.reply_text("Format salah. Cek: /trade")


async def cmd_area(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    repo.ensure_player(user.id, user.username)
    player = repo.get_player(user.id)
    current = int(player["current_area_id"])
    unlocked = int(player["unlocked_area_id"])

    if not context.args:
        lines = [f"🌍 Area saat ini: {get_area_by_id(current).name} (#{current})"]
        lines.append(f"Area terbuka sampai: #{unlocked}")
        lines.append("List area:")
        for area in AREAS:
            status = "✅" if area.id <= unlocked else "🔒"
            lines.append(f"{status} {area.id}. {area.name} (Lv {area.level_min}-{area.level_max})")
        lines.append("Pindah area: /area move <id>")
        await update.effective_message.reply_text("\n".join(lines))
        return

    if context.args[0] != "move" or len(context.args) < 2 or not context.args[1].isdigit():
        await update.effective_message.reply_text("Format: /area move <id>")
        return

    target = int(context.args[1])
    if target < 1 or target > len(AREAS):
        await update.effective_message.reply_text("Area tidak valid.")
        return
    if target > unlocked:
        await update.effective_message.reply_text("Area masih terkunci. Kalahkan boss area sebelumnya.")
        return

    with repo._connect() as conn:
        conn.execute("UPDATE players SET current_area_id = ? WHERE user_id = ?", (target, user.id))
    await update.effective_message.reply_text(f"✅ Berpindah ke area {get_area_by_id(target).name}.")


async def cmd_boss(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    repo.ensure_player(user.id, user.username)
    player = repo.get_player(user.id)
    total = compute_total_stats(player)
    area = get_area_by_id(int(player["current_area_id"]))
    monster = make_scaled_monster(area.boss, area.id, is_boss=True)
    win, hp_left, logs, _ = do_battle(player["hp"], total["atk"], total["def"], total["crit"], total["dodge"], monster)

    if win:
        repo.update_stats(user.id, hp=hp_left, gold_delta=monster.gold_drop, exp_delta=monster.exp_drop)
        logs.append(f"👑 Boss {area.boss} kalah! +{monster.exp_drop} EXP +{monster.gold_drop} Gold")
        unlocked = int(player["unlocked_area_id"])
        if area.id == unlocked and unlocked < len(AREAS):
            with repo._connect() as conn:
                conn.execute(
                    "UPDATE players SET unlocked_area_id = ? WHERE user_id = ?",
                    (unlocked + 1, user.id),
                )
            logs.append(f"🔓 Area baru terbuka: {get_area_by_id(unlocked + 1).name}")
    else:
        repo.update_stats(user.id, hp=max(1, hp_left))
        logs.append("❌ Kamu kalah dari boss.")

    await update.effective_message.reply_text("\n".join(logs[:20]))


async def cmd_adventure(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await cmd_hunt(update, context)


async def cmd_fight(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await cmd_battle(update, context)


async def cmd_dungeon(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await cmd_boss(update, context)


async def cmd_unlock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await cmd_boss(update, context)


async def cmd_sell(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text("Fitur /sell bisa ditambahkan berikutnya (market harga dinamis).")


async def cmd_drop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    repo.ensure_player(user.id, user.username)
    if len(context.args) < 1:
        await update.effective_message.reply_text("Format: /drop <item> <qty>")
        return
    item = context.args[0].lower()
    qty = int(context.args[1]) if len(context.args) > 1 and context.args[1].isdigit() else 1
    if qty <= 0:
        await update.effective_message.reply_text("Qty harus > 0.")
        return
    inv = {row["item_name"]: row["quantity"] for row in repo.get_inventory(user.id)}
    if inv.get(item, 0) < qty:
        await update.effective_message.reply_text("Item tidak cukup.")
        return
    repo.upsert_inventory(user.id, item, -qty)
    await update.effective_message.reply_text(f"🗑️ Berhasil drop {qty}x {item}.")


async def cmd_duel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text("Fitur duel PvP belum aktif.")


def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("Set TELEGRAM_BOT_TOKEN sebelum menjalankan bot.")
    if BOT_OWNER_ID <= 0:
        logger.warning("BOT_OWNER_ID belum diset. Set di environment/.env agar fitur owner siap dipakai.")

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("profile", cmd_profile))
    app.add_handler(CommandHandler("p", cmd_profile))
    app.add_handler(CommandHandler("hunt", cmd_hunt))
    app.add_handler(CommandHandler("ht", cmd_hunt))
    app.add_handler(CommandHandler("adventure", cmd_adventure))
    app.add_handler(CommandHandler("adv", cmd_adventure))
    app.add_handler(CommandHandler("fight", cmd_fight))
    app.add_handler(CommandHandler("f", cmd_fight))
    app.add_handler(CommandHandler("dungeon", cmd_dungeon))
    app.add_handler(CommandHandler("dg", cmd_dungeon))
    app.add_handler(CommandHandler("inventory", cmd_inventory))
    app.add_handler(CommandHandler("inv", cmd_inventory))
    app.add_handler(CommandHandler("item", cmd_item))
    app.add_handler(CommandHandler("use", cmd_use))
    app.add_handler(CommandHandler("equip", cmd_equip))
    app.add_handler(CommandHandler("eq", cmd_equip))
    app.add_handler(CommandHandler("unequip", cmd_unequip))
    app.add_handler(CommandHandler("uneq", cmd_unequip))
    app.add_handler(CommandHandler("drop", cmd_drop))
    app.add_handler(CommandHandler("dr", cmd_drop))
    app.add_handler(CommandHandler("shop", cmd_shop))
    app.add_handler(CommandHandler("sh", cmd_shop))
    app.add_handler(CommandHandler("buy", cmd_buy))
    app.add_handler(CommandHandler("sell", cmd_sell))
    app.add_handler(CommandHandler("balance", cmd_balance))
    app.add_handler(CommandHandler("bal", cmd_balance))
    app.add_handler(CommandHandler("battle", cmd_battle))
    app.add_handler(CommandHandler("guild", cmd_guild))
    app.add_handler(CommandHandler("g", cmd_guild))
    app.add_handler(CommandHandler("leaderboard", cmd_leaderboard))
    app.add_handler(CommandHandler("top", cmd_leaderboard))
    app.add_handler(CommandHandler("duel", cmd_duel))
    app.add_handler(CommandHandler("trade", cmd_trade))
    app.add_handler(CommandHandler("area", cmd_area))
    app.add_handler(CommandHandler("a", cmd_area))
    app.add_handler(CommandHandler("travel", cmd_travel))
    app.add_handler(CommandHandler("go", cmd_travel))
    app.add_handler(CommandHandler("unlock", cmd_unlock))
    app.add_handler(CommandHandler("ul", cmd_unlock))
    app.add_handler(CommandHandler("boss", cmd_boss))
    app.add_handler(CallbackQueryHandler(on_menu_click))

    logger.info("Bot running...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
