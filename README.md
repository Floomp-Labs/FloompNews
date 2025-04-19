Crypto News Aggregator Bot
A smart Telegram bot that delivers curated, real-time cryptocurrency news with sentiment analysis and market impact predictions.

🌟 Features
📰 Aggregates news from CoinDesk, Cointelegraph, The Block, Decrypt, and more

💬 Summarizes news with sentiment emojis (📈📉➡️)

📊 Analyzes potential market impact using RSI, MACD, and Bollinger Bands

🧠 Personalized updates by topics and frequency

🧾 Optional command /recap for daily summaries

⚙️ Setup Instructions
Clone the repo

bash
Copy
Edit
git clone https://github.com/yourusername/crypto-news-bot.git
cd crypto-news-bot
Install dependencies

bash
Copy
Edit
pip install -r requirements.txt
Create a .env file

ini
Copy
Edit
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
Run the bot

bash
Copy
Edit
python bot.py
💬 Bot Commands
/start – Start the bot and receive a welcome message

/topics – Set or change preferred crypto news topics

/frequency – Choose between hourly, daily, or breaking news

/recap – Get a summary of today’s top news

/help – Redisplay usage instructions

🧠 Supported Topics
Bitcoin

Ethereum

DeFi

NFT

Regulation

Markets

Technology

📦 Dependencies
See requirements.txt for full list. Highlights include:

python-telegram-bot

feedparser, beautifulsoup4, requests

nltk, yfinance, ta, ccxt

🛡 License
MIT – Free to use and modify. Contributions welcome!

