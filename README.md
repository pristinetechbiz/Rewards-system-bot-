# Community Rewards Bot

A Telegram-based community rewards system where members earn points for engagement
and redeem them for airtime and data bundles via the eBills Africa API.

## Quick Start (Local)

**Prerequisites:** Python 3.11+, Docker Desktop, Git

```bash
# 1. Clone and enter the project
git clone <your-repo-url> && cd rewards-bot

# 2. Create a virtual environment
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with your BOT_TOKEN, ADMIN_IDS, eBills credentials

# 5. Start Postgres + Redis
docker compose up -d db redis

# 6. Initialise the database
psql $DATABASE_URL -f migrations/init.sql

# 7. Run the bot
python bot.py
```

Send `/start` to your bot. You should receive a welcome message and 100 points.

---

## Deploy to Kuberns (Production — Recommended)

Kuberns keeps your bot running 24/7 with no idle timeout.

1. Push your code to GitHub (make sure `.env` is in `.gitignore`).
2. Sign up at [kuberns.com](https://kuberns.com).
3. Click **Create Service** → connect your GitHub repo → select `main` branch.
4. Kuberns auto-detects Python and sets start command to `python bot.py`.
5. Add a **PostgreSQL** database and a **Redis** instance via the dashboard.
6. In the **Environment** section, add all variables from `.env.example`.
7. Click **Deploy** and watch the logs for `Start polling`.

---

## Deploy to Railway (Alternative)

```
railway.app → New Project → Deploy from GitHub → select repo
Add PostgreSQL and Redis plugins → set env vars → deploy
```

Use [UptimeRobot](https://uptimerobot.com) (free) to prevent idle sleep.

---

## Admin Commands

All admin commands work in **private chat with the bot only**.

| Command | Description |
|---|---|
| `/admin` | Show admin help panel |
| `/award_points {user_id} {amount} {reason}` | Manually award points |
| `/resolve_ticket {ticket_id} {points}` | Resolve support ticket |
| `/verify_contribution {user_id} {score 1-10} {description}` | Verify contribution |
| `/stats` | System-wide statistics |
| `/ebills_balance` | Check eBills wallet balance |

**Finding Telegram user IDs:** Message [@userinfobot](https://t.me/userinfobot) on Telegram.

---

## Points Economy

| Activity | Points |
|---|---|
| Registration (`/start`) | 100 pts |
| Opening a support ticket | 50 pts |
| Ticket resolved by admin | 50–150 pts |
| Contribution (score × 10) | 10–100 pts |
| Admin bonus | Variable |

| Redemption | Rate | Minimum |
|---|---|---|
| Airtime | 10 pts = ₦1 | ₦50 (500 pts) |
| Data bundle | 8 pts = ₦1 value | Plan-dependent |

---

## Project Structure

```
rewards-bot/
├── bot.py                  # Entry point
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── config/settings.py      # Pydantic env config
├── db/
│   ├── models.py           # Dataclasses
│   └── repository.py       # All DB operations
├── bot/
│   ├── handlers/           # One file per feature
│   ├── keyboards/inline.py # All keyboard builders
│   ├── middlewares/auth.py # User injection + admin guard
│   └── utils/
│       ├── ebills.py       # eBills API client
│       └── helpers.py      # Phone validation, formatting
└── migrations/init.sql     # Database schema
```
