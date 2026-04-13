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
