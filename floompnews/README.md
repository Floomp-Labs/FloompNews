# Crypto News Aggregator Bot

A Telegram bot that aggregates and sends curated cryptocurrency news from reliable sources.

## Features

- Personalized news feed based on user preferences
- Trusted sources including CoinDesk, Cointelegraph, and The Block
- Customizable notification frequency (hourly, daily, breaking news)
- News categorization by type (market updates, regulations, technology)
- Brief summaries with links to full articles

## Setup

1. Clone this repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create a `.env` file with your Telegram bot token:
   ```
   TELEGRAM_BOT_TOKEN=your_bot_token_here
   ```
4. Run the bot:
   ```bash
   python bot.py
   ```

## Commands

- `/start` - Start the bot and set default preferences
- `/topics` - View or set your preferred topics
- `/frequency` - Set your preferred update frequency

## Available Topics

- Bitcoin
- Ethereum
- DeFi
- NFT
- Regulation

## License

MIT 