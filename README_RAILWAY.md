# Leon v2 OSINT Bot — Railway deployment

## Deploy
1. Upload `bot_railway.py`, `requirements.txt`, and `Procfile` to a GitHub repository.
2. In Railway, deploy the repository as a service.
3. In Railway → Variables, add `BOT_TOKEN` with your NEW Telegram bot token from @BotFather.
4. Set start command to `python bot_railway.py` if Railway does not detect the Procfile.
5. Check Deploy Logs.

## SQLite persistence (recommended)
Attach a Railway Volume mounted at `/data`, then set Railway variable `DB_FILE=/data/leon_osint.db`. Without a persistent volume, SQLite data may be lost when the service is recreated.

## Important security notes
- The token embedded in the uploaded original source was exposed. Revoke/regenerate it using Telegram @BotFather (`/revoke`) and use only the NEW token in Railway Variables. Never commit the token to GitHub.
- Free hosting and uninterrupted 24/7 uptime are not guaranteed; check Railway's current plan and usage rules.
- Use personal-data lookup functions only where lawful and authorized.
