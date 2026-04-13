# Telegram RPG Bot

Bot Telegram RPG sederhana dengan komponen:
- Player (level, exp, gold, HP)
- Command (`/hunt`, `/inventory`, dll)
- Sistem battle (HP + attack)

## Fitur yang tersedia
- `/start`
- `/profile`
- `/hunt`
- `/inventory`
- `/item use <nama_item>`
- `/shop` dan `/shop buy <item> <qty>`
- `/battle`
- Monster random
- `/guild`, `/guild create <nama>`, `/guild join <nama>`
- `/leaderboard`
- Trading (`/trade offer` dan `/trade accept`)

## Contoh tampilan `/profile`
```text
╔═══════════〔 PROFILE 〕═══════════╗
👤 Nama     : Username
🎖️ Level    : 12 (EXP: 120/200)
🌍 Area     : Volcano
❤️ HP       : 180 / 200
⚔️ ATK      : 35
🛡️ DEF      : 20

💰 Gold     : 1,250
💎 Gems     : 50

🗡️ Weapon   : Flame Sword
🛡️ Armor    : Iron Armor

🎒 Inventory: 5 items
🐾 Pet      : Fire Wolf

🏆 Rank     : #15
╚══════════════════════════════════╝
```

## Sistem stat (simple)
- Base stat dari player:
  - HP: 100
  - ATK: 10
  - DEF: 5
- Equipment memberi bonus otomatis:
  - `wood_sword` → +5 ATK
  - `iron_armor` → +20 HP, +8 DEF
  - `flame_sword` → +12 ATK, +10% critical chance
- Pet juga memberi bonus (contoh `Fire Wolf` +5 ATK).

Formula total:
`TOTAL = BASE + EQUIPMENT + BONUS PET`

Contoh damage saat battle:
- Damage player ke monster = ATK total player (dengan peluang critical dari weapon).
- Damage monster ke player = `max(1, serangan monster - DEF total player)`.

## Jenis item
- **Consumable**: potion (heal), elixir (bonus EXP), antidote.
- **Equipment**: weapon, armor, accessory (bonus stat otomatis saat di-equip).
- **Material**: wood, iron, crystal (untuk progres/crafting lanjutan).
- **Special**: dungeon key / item event.

## Rarity system
- Common ⚪
- Uncommon 🟢
- Rare 🔵
- Epic 🟣
- Legendary 🟠
- Mythic 🔴

## Sistem drop RNG
Setiap monster punya tabel drop sendiri (contoh Slime: gel/potion/wood_sword) dengan peluang berbeda. Bonus drop rate dari accessory akan menambah peluang drop.

## Cara jalankan
1. Install dependency:
   ```bash
   pip install -r requirements.txt
   ```
2. Buat file `.env` (direkomendasikan):
   ```bash
   TELEGRAM_BOT_TOKEN="TOKEN_KAMU"
   BOT_OWNER_ID="123456789"
   # opsional:
   # RPG_DB_PATH="rpg_bot.db"
   ```
   Atau set via export environment:
   ```bash
   export TELEGRAM_BOT_TOKEN="TOKEN_KAMU"
   export BOT_OWNER_ID="123456789"
   ```
3. Jalankan bot:
   ```bash
   python bot.py
   ```

## Catatan
- Data disimpan di SQLite (`rpg_bot.db`) agar cepat dipakai.
- Untuk trade, user penerima harus sudah `/start` dulu.
- `BOT_OWNER_ID` dipakai sebagai konfigurasi owner bot (untuk kebutuhan command admin/owner ke depan).
