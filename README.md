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
2. Set token bot Telegram:
   ```bash
   export TELEGRAM_BOT_TOKEN="TOKEN_KAMU"
   ```
3. Jalankan bot:
   ```bash
   python bot.py
   ```

## Catatan
- Data disimpan di SQLite (`rpg_bot.db`) agar cepat dipakai.
- Untuk trade, user penerima harus sudah `/start` dulu.
