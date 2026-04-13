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
📊 EXP Bar  : ▰▰▰▰▰▱▱▱▱▱
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
