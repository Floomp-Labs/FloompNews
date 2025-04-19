import logging
import os
from datetime import datetime, time as datetime_time, timedelta
import threading
import time
from typing import Dict, List, Set, Tuple
import yfinance as yf
import pandas as pd
import ccxt
import ta
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
import feedparser
import schedule
from dotenv import load_dotenv
import nltk
from nltk.sentiment import SentimentIntensityAnalyzer
import requests
from bs4 import BeautifulSoup
import re

# Download required NLTK data
nltk.download('vader_lexicon')

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Get the bot token
token = os.getenv("TELEGRAM_BOT_TOKEN")
if not token:
    logger.error("TELEGRAM_BOT_TOKEN not found in environment variables")
    raise ValueError("TELEGRAM_BOT_TOKEN not found in environment variables")
else:
    logger.info("Successfully loaded Telegram bot token")

# Webhook configuration
WEBHOOK_HOST = os.getenv('WEBHOOK_HOST', '0.0.0.0')
WEBHOOK_PORT = int(os.getenv('PORT', 8443))
WEBHOOK_URL_BASE = os.getenv('WEBHOOK_URL_BASE', f"https://{WEBHOOK_HOST}:{WEBHOOK_PORT}")
WEBHOOK_URL_PATH = f"/{token}"

# Dictionary to store user preferences
user_preferences: Dict[int, Dict] = {}

# Set to track sent articles
sent_articles: Set[str] = set()

# News sources with categories
NEWS_SOURCES = {
    "bitcoin": [
        "https://cointelegraph.com/rss/tag/bitcoin",
        "https://www.coindesk.com/arc/outboundfeeds/rss/?outputType=xml&tags=bitcoin",
        "https://www.coindesk.com/arc/outboundfeeds/rss/?outputType=xml&categories=bitcoin",
        "https://unusualwhales.com/rss/bitcoin"
    ],
    "ethereum": [
        "https://cointelegraph.com/rss/tag/ethereum",
        "https://www.coindesk.com/arc/outboundfeeds/rss/?outputType=xml&tags=ethereum",
        "https://www.coindesk.com/arc/outboundfeeds/rss/?outputType=xml&categories=ethereum",
        "https://unusualwhales.com/rss/ethereum"
    ],
    "defi": [
        "https://cointelegraph.com/rss/tag/defi",
        "https://www.coindesk.com/arc/outboundfeeds/rss/?outputType=xml&tags=defi",
        "https://www.coindesk.com/arc/outboundfeeds/rss/?outputType=xml&categories=defi",
        "https://unusualwhales.com/rss/defi"
    ],
    "nft": [
        "https://cointelegraph.com/rss/tag/nft",
        "https://www.coindesk.com/arc/outboundfeeds/rss/?outputType=xml&tags=nft",
        "https://www.coindesk.com/arc/outboundfeeds/rss/?outputType=xml&categories=nft",
        "https://unusualwhales.com/rss/nft"
    ],
    "regulation": [
        "https://cointelegraph.com/rss/tag/regulation",
        "https://www.coindesk.com/arc/outboundfeeds/rss/?outputType=xml&tags=regulation",
        "https://www.coindesk.com/arc/outboundfeeds/rss/?outputType=xml&categories=regulation",
        "https://unusualwhales.com/rss/regulation"
    ],
    "markets": [
        "https://www.coindesk.com/arc/outboundfeeds/rss/?outputType=xml&categories=markets",
        "https://www.coindesk.com/arc/outboundfeeds/rss/?outputType=xml&tags=markets",
        "https://unusualwhales.com/rss/markets"
    ],
    "technology": [
        "https://www.coindesk.com/arc/outboundfeeds/rss/?outputType=xml&categories=technology",
        "https://www.coindesk.com/arc/outboundfeeds/rss/?outputType=xml&tags=technology",
        "https://unusualwhales.com/rss/technology"
    ]
}

# Cryptocurrency symbols mapping
CRYPTO_SYMBOLS = {
    "bitcoin": "BTC-USD",
    "ethereum": "ETH-USD",
    "defi": "DEFI-USD",
    "nft": "NFT-USD",
    "markets": "BTC-USD"  # Using BTC as market indicator
}

# Initialize sentiment analyzer
sia = SentimentIntensityAnalyzer()

def get_sentiment_emoji(compound_score: float) -> str:
    """Return an emoji based on sentiment score."""
    if compound_score >= 0.05:
        return "📈"  # Positive
    elif compound_score <= -0.05:
        return "📉"  # Negative
    else:
        return "➡️"  # Neutral

def analyze_sentiment(text: str) -> Dict[str, float]:
    """Analyze sentiment of text using NLTK's VADER."""
    return sia.polarity_scores(text)

def get_article_summary(url: str) -> str:
    """Extract a summary from the article URL."""
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Try to find meta description
        meta_desc = soup.find('meta', {'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            return meta_desc['content']
        
        # Fallback to first paragraph
        first_p = soup.find('p')
        if first_p:
            return first_p.text[:200] + "..."
        
        return "No summary available"
    except Exception as e:
        logger.error(f"Error fetching article summary: {e}")
        return "Error fetching summary"

def get_crypto_price_data(symbol: str, hours: int = 24) -> pd.DataFrame:
    """Get cryptocurrency price data for analysis."""
    try:
        # Get data from yfinance
        ticker = yf.Ticker(symbol)
        data = ticker.history(period=f"{hours}h", interval="1h")
        
        # Calculate technical indicators
        data['RSI'] = ta.momentum.RSIIndicator(data['Close']).rsi()
        data['MACD'] = ta.trend.MACD(data['Close']).macd()
        data['BB_upper'], data['BB_middle'], data['BB_lower'] = ta.volatility.BollingerBands(data['Close']).bollinger_bands()
        
        return data
    except Exception as e:
        logger.error(f"Error fetching price data for {symbol}: {e}")
        return pd.DataFrame()

def analyze_market_impact(symbol: str, sentiment_score: float) -> str:
    """Analyze potential market impact based on news sentiment."""
    try:
        data = get_crypto_price_data(symbol)
        if data.empty:
            return "Market data unavailable"
        
        # Get current price and recent changes
        current_price = data['Close'].iloc[-1]
        price_24h_ago = data['Close'].iloc[0]
        price_change = ((current_price - price_24h_ago) / price_24h_ago) * 100
        
        # Get technical indicators
        rsi = data['RSI'].iloc[-1]
        macd = data['MACD'].iloc[-1]
        
        # Analyze market conditions
        market_condition = "neutral"
        if rsi > 70:
            market_condition = "overbought"
        elif rsi < 30:
            market_condition = "oversold"
        
        # Generate impact prediction
        impact = []
        if sentiment_score > 0.2 and market_condition == "oversold":
            impact.append("Strong potential for price increase")
        elif sentiment_score < -0.2 and market_condition == "overbought":
            impact.append("High risk of price correction")
        
        if abs(price_change) > 5:
            impact.append(f"Significant price movement ({price_change:.2f}%) in last 24h")
        
        if macd > 0:
            impact.append("MACD indicates bullish momentum")
        elif macd < 0:
            impact.append("MACD indicates bearish momentum")
        
        return "\n".join(impact) if impact else "Market impact unclear"
    except Exception as e:
        logger.error(f"Error analyzing market impact: {e}")
        return "Error analyzing market impact"

def scrape_theblock(topic: str) -> List[Tuple[str, str, str]]:
    """Scrape news from The Block."""
    try:
        # Map topics to The Block's URL structure
        topic_mapping = {
            "bitcoin": "bitcoin",
            "ethereum": "ethereum",
            "defi": "defi",
            "nft": "nft",
            "regulation": "regulation",
            "markets": "markets",
            "technology": "technology"
        }
        
        mapped_topic = topic_mapping.get(topic, topic)
        url = f"https://www.theblock.co/topic/{mapped_topic}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        articles = []
        for article in soup.select('article.article-card'):
            title_elem = article.select_one('h3.article-card__title')
            link_elem = article.select_one('a.article-card__link')
            summary_elem = article.select_one('p.article-card__description')
            
            if title_elem and link_elem:
                title = title_elem.text.strip()
                link = "https://www.theblock.co" + link_elem['href']
                summary = summary_elem.text.strip() if summary_elem else ""
                articles.append((title, summary, link))
        
        return articles[:10]  # Return top 10 articles instead of 5
    except Exception as e:
        logger.error(f"Error scraping The Block: {e}", exc_info=True)
        return []

def scrape_decrypt(topic: str) -> List[Tuple[str, str, str]]:
    """Scrape news from Decrypt."""
    try:
        url = f"https://decrypt.co/topic/{topic}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        articles = []
        for article in soup.select('article.post-card'):
            title_elem = article.select_one('h3.post-card__title')
            link_elem = article.select_one('a.post-card__link')
            summary_elem = article.select_one('p.post-card__excerpt')
            
            if title_elem and link_elem:
                title = title_elem.text.strip()
                link = link_elem['href']
                summary = summary_elem.text.strip() if summary_elem else ""
                articles.append((title, summary, link))
        
        return articles[:5]
    except Exception as e:
        logger.error(f"Error scraping Decrypt: {e}")
        return []

def scrape_cryptoslate(topic: str) -> List[Tuple[str, str, str]]:
    """Scrape news from CryptoSlate."""
    try:
        url = f"https://cryptoslate.com/category/{topic}/"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        articles = []
        for article in soup.select('article.post'):
            title_elem = article.select_one('h2.post-title')
            link_elem = article.select_one('a.post-title-link')
            summary_elem = article.select_one('div.post-excerpt')
            
            if title_elem and link_elem:
                title = title_elem.text.strip()
                link = link_elem['href']
                summary = summary_elem.text.strip() if summary_elem else ""
                articles.append((title, summary, link))
        
        return articles[:5]
    except Exception as e:
        logger.error(f"Error scraping CryptoSlate: {e}")
        return []

# Topic mapping for different sources
TOPIC_MAPPING = {
    "bitcoin": {
        "theblock": "bitcoin",
        "decrypt": "bitcoin",
        "cryptoslate": "bitcoin",
        "unusualwhales": "bitcoin"
    },
    "ethereum": {
        "theblock": "ethereum",
        "decrypt": "ethereum",
        "cryptoslate": "ethereum",
        "unusualwhales": "ethereum"
    },
    "defi": {
        "theblock": "defi",
        "decrypt": "defi",
        "cryptoslate": "defi",
        "unusualwhales": "defi"
    },
    "nft": {
        "theblock": "nft",
        "decrypt": "nft",
        "cryptoslate": "nft",
        "unusualwhales": "nft"
    },
    "regulation": {
        "theblock": "regulation",
        "decrypt": "regulation",
        "cryptoslate": "regulation",
        "unusualwhales": "regulation"
    },
    "markets": {
        "theblock": "markets",
        "decrypt": "markets",
        "cryptoslate": "markets",
        "unusualwhales": "markets"
    },
    "technology": {
        "theblock": "technology",
        "decrypt": "technology",
        "cryptoslate": "technology",
        "unusualwhales": "technology"
    }
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send welcome message when the command /start is issued."""
    user_id = update.effective_user.id
    logger.info(f"New user started: {user_id}")
    
    try:
        user_preferences[user_id] = {
            "topics": ["bitcoin", "ethereum", "markets"],
            "frequency": "daily",
            "last_update": datetime.now()
        }
        
        welcome_text = (
            "👋 Welcome to Crypto News Bot!\n\n"
            "I'll keep you updated with the latest cryptocurrency news.\n\n"
            "Available commands:\n"
            "/topics - Set your preferred topics\n"
            "/frequency - Set update frequency (hourly/daily/breaking)\n"
            "/recap - Get a daily news recap\n"
            "/help - Show this help message"
        )
        
        logger.debug(f"Sending welcome message to user {user_id}")
        await update.message.reply_text(welcome_text)
        logger.info(f"Successfully sent welcome message to user {user_id}")
        
        # Send immediate news recap
        await send_daily_recap(update, context)
        
    except Exception as e:
        logger.error(f"Error in start command: {e}", exc_info=True)
        await update.message.reply_text("Sorry, there was an error processing your request. Please try again later.")

async def send_daily_recap(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a daily news recap to the user."""
    user_id = update.effective_user.id
    logger.info(f"Sending daily recap to user {user_id}")
    
    try:
        # Clear sent articles to ensure we get fresh news
        sent_articles.clear()
        
        # Fetch and send news for each topic
        for topic in user_preferences[user_id]["topics"]:
            await fetch_and_send_news_for_topic(context, user_id, topic)
            
        await update.message.reply_text(
            "📰 That's all for today's recap!\n\n"
            "You'll receive regular updates based on your preferences.\n"
            "Use /topics to customize which categories you want to follow."
        )
    except Exception as e:
        logger.error(f"Error sending daily recap: {e}", exc_info=True)
        await update.message.reply_text("Sorry, there was an error fetching the news recap. Please try again later.")

async def fetch_and_send_news_for_topic(context: ContextTypes.DEFAULT_TYPE, user_id: int, topic: str) -> None:
    """Fetch and send news for a specific topic."""
    logger.info(f"Fetching news for topic: {topic}")
    
    # Get articles from all sources
    all_articles = []
    
    # Get RSS feed articles
    for source in NEWS_SOURCES[topic]:
        try:
            logger.info(f"Parsing feed: {source}")
            feed = feedparser.parse(source)
            
            if not feed.entries:
                logger.warning(f"No entries found in feed: {source}")
                continue
            
            logger.info(f"Found {len(feed.entries)} entries in feed {source}")
            
            for entry in feed.entries[:10]:
                if entry.link not in sent_articles:
                    all_articles.append((entry.title, entry.summary, entry.link))
                    logger.info(f"Added article from {source}: {entry.title}")
        except Exception as e:
            logger.error(f"Error processing feed {source}: {e}", exc_info=True)
    
    # Get scraped articles
    if topic in TOPIC_MAPPING:
        topic_mapping = TOPIC_MAPPING[topic]
        
        # The Block articles
        try:
            logger.info(f"Scraping The Block for topic: {topic_mapping['theblock']}")
            theblock_articles = scrape_theblock(topic_mapping["theblock"])
            logger.info(f"Found {len(theblock_articles)} articles from The Block")
            all_articles.extend(theblock_articles)
        except Exception as e:
            logger.error(f"Error scraping The Block: {e}", exc_info=True)
        
        # Decrypt articles
        try:
            logger.info(f"Scraping Decrypt for topic: {topic_mapping['decrypt']}")
            decrypt_articles = scrape_decrypt(topic_mapping["decrypt"])
            logger.info(f"Found {len(decrypt_articles)} articles from Decrypt")
            all_articles.extend(decrypt_articles)
        except Exception as e:
            logger.error(f"Error scraping Decrypt: {e}", exc_info=True)
        
        # CryptoSlate articles
        try:
            logger.info(f"Scraping CryptoSlate for topic: {topic_mapping['cryptoslate']}")
            cryptoslate_articles = scrape_cryptoslate(topic_mapping["cryptoslate"])
            logger.info(f"Found {len(cryptoslate_articles)} articles from CryptoSlate")
            all_articles.extend(cryptoslate_articles)
        except Exception as e:
            logger.error(f"Error scraping CryptoSlate: {e}", exc_info=True)
    
    # Remove duplicates based on title
    seen_titles = set()
    unique_articles = []
    for title, summary, link in all_articles:
        if title not in seen_titles and link not in sent_articles:
            seen_titles.add(title)
            unique_articles.append((title, summary, link))
    
    logger.info(f"Total unique articles found: {len(unique_articles)}")
    
    # Process and send articles
    for title, summary, link in unique_articles[:10]:
        try:
            # Analyze sentiment
            sentiment = analyze_sentiment(title + " " + summary)
            sentiment_emoji = get_sentiment_emoji(sentiment['compound'])
            
            # Get market impact analysis if applicable
            market_impact = ""
            if topic in CRYPTO_SYMBOLS:
                market_impact = analyze_market_impact(CRYPTO_SYMBOLS[topic], sentiment['compound'])
            
            # Format message
            news_text = (
                f"{sentiment_emoji} *{title}*\n\n"
                f"📝 {summary}\n\n"
            )
            
            if market_impact:
                news_text += f"📊 Market Impact:\n{market_impact}\n\n"
            
            news_text += f"🔗 [Read full article]({link})"
            
            logger.info(f"Sending message to user {user_id}: {title}")
            await context.bot.send_message(
                chat_id=user_id,
                text=news_text,
                parse_mode="Markdown",
                disable_web_page_preview=False
            )
            sent_articles.add(link)
            logger.info(f"Successfully sent article: {title}")
            
            # Wait to avoid rate limiting
            time.sleep(1)
            
        except Exception as e:
            logger.error(f"Failed to send message to {user_id}: {e}", exc_info=True)

async def set_topics(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Allow users to set their preferred topics."""
    user_id = update.effective_user.id
    logger.info(f"User {user_id} setting topics")
    
    if not context.args:
        topics_list = "\n".join(f"- {topic.capitalize()}" for topic in NEWS_SOURCES.keys())
        await update.message.reply_text(
            f"Available topics:\n{topics_list}\n\n"
            "Use /topics topic1 topic2 to set your preferences"
        )
        return
    
    selected_topics = [topic.lower() for topic in context.args if topic.lower() in NEWS_SOURCES]
    
    if not selected_topics:
        await update.message.reply_text("No valid topics selected. Try again.")
        return
    
    if user_id not in user_preferences:
        user_preferences[user_id] = {"frequency": "daily"}
    
    user_preferences[user_id]["topics"] = selected_topics
    logger.info(f"User {user_id} updated topics to: {selected_topics}")
    await update.message.reply_text(
        f"✅ Topics updated!\n"
        f"You'll now receive news about: {', '.join(selected_topics)}"
    )

async def set_frequency(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Allow users to set their preferred update frequency."""
    user_id = update.effective_user.id
    
    if not context.args or context.args[0].lower() not in ["hourly", "daily", "breaking"]:
        await update.message.reply_text(
            "Please specify a valid frequency:\n"
            "- hourly: Updates every hour\n"
            "- daily: Updates once per day\n"
            "- breaking: Only breaking news"
        )
        return
    
    frequency = context.args[0].lower()
    
    if user_id not in user_preferences:
        user_preferences[user_id] = {"topics": ["bitcoin", "ethereum"]}
    
    user_preferences[user_id]["frequency"] = frequency
    await update.message.reply_text(f"✅ Frequency updated!\nYou'll now receive {frequency} updates.")

async def handle_floompnews(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle messages containing 'floompnews'."""
    user_id = update.effective_user.id
    logger.info(f"User {user_id} mentioned floompnews")
    
    try:
        # Send a welcome message
        await update.message.reply_text(
            "👋 Welcome to Floomp News!\n\n"
            "I'm your crypto news assistant. Here's what I can do:\n\n"
            "📰 Get news updates:\n"
            "/start - Begin using the bot\n"
            "/recap - Get a news recap\n"
            "/topics - Set your preferred topics\n"
            "/frequency - Set update frequency\n\n"
            "Available topics:\n"
            "- Bitcoin\n"
            "- Ethereum\n"
            "- DeFi\n"
            "- NFT\n"
            "- Regulation\n"
            "- Markets\n"
            "- Technology\n\n"
            "Try /start to begin!"
        )
        
        # If user hasn't started yet, initialize their preferences
        if user_id not in user_preferences:
            user_preferences[user_id] = {
                "topics": ["bitcoin", "ethereum", "markets"],
                "frequency": "daily",
                "last_update": datetime.now()
            }
            
    except Exception as e:
        logger.error(f"Error handling floompnews message: {e}", exc_info=True)
        await update.message.reply_text("Sorry, there was an error processing your request. Please try again later.")

def run_scheduler():
    """Run the scheduler in a separate thread."""
    while True:
        schedule.run_pending()
        time.sleep(1)

def main() -> None:
    """Start the bot."""
    try:
        # Create the Application
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not token:
            logger.error("TELEGRAM_BOT_TOKEN not found in environment variables")
            raise ValueError("TELEGRAM_BOT_TOKEN not found in environment variables")
        
        logger.info("Initializing bot application...")
        application = Application.builder().token(token).build()
        logger.info("Bot application initialized successfully")

        # Add command handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("topics", set_topics))
        application.add_handler(CommandHandler("frequency", set_frequency))
        application.add_handler(CommandHandler("recap", send_daily_recap))
        application.add_handler(CommandHandler("help", start))
        
        # Add message handler for "floompnews"
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.Regex(r'(?i)floompnews'), handle_floompnews))
        
        logger.info("Command handlers added successfully")

        # Set up jobs
        job_queue = application.job_queue
        logger.info("Setting up scheduled jobs...")
        
        # Schedule different frequency jobs
        job_queue.run_repeating(send_daily_recap, interval=3600, first=10, name="hourly")
        job_queue.run_daily(send_daily_recap, time=datetime_time(hour=8, minute=0), name="daily")
        logger.info("Scheduled jobs set up successfully")

        # Start the scheduler in a separate thread
        scheduler_thread = threading.Thread(target=run_scheduler)
        scheduler_thread.daemon = True
        scheduler_thread.start()
        logger.info("Scheduler thread started")

        # Run in polling mode for local testing
        logger.info("Starting bot in polling mode...")
        application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
            
    except Exception as e:
        logger.error("Error in main function:", exc_info=True)
        raise

if __name__ == "__main__":
    main() 