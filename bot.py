import logging
import asyncio
from telegram import Update, constants
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from cerebras.cloud.sdk import Cerebras
import config

# --- LOGGING SETUP ---
# Establishes a visibility layer for debugging and monitoring.
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- CEREBRAS CLIENT INITIALIZATION ---
# Initialize the AI client globally to reuse the connection.
try:
    client = Cerebras(api_key=config.CEREBRAS_API_KEY)
except Exception as e:
    logger.critical(f"Failed to initialize Cerebras Client: {e}")
    exit(1)

# --- CORE FUNCTIONS ---

def get_cerebras_response(user_input: str) -> str:
    """
    Synchronous function to communicate with Cerebras API.
    This will be run in a separate thread to avoid blocking the bot.
    """
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system", 
                    "content": "You are a helpful, intelligent AI assistant on Telegram."
                },
                {
                    "role": "user", 
                    "content": user_input
                }
            ],
            model=config.MODEL_ID,
        )
        # Extract the content from the response object
        return chat_completion.choices[0].message.content
    except Exception as e:
        logger.error(f"Cerebras API Error: {e}")
        return "⚠️ I encountered an error while processing your request. Please try again later."

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles the /start command.
    """
    user_first_name = update.effective_user.first_name
    welcome_text = (
        f"Hello, {user_first_name}! 🤖\n\n"
        f"I am an AI Bot powered by the hyper-fast **Cerebras {config.MODEL_ID}**.\n\n"
        "Ask me anything, and I will generate code, summarize text, or answer questions instantly."
    )
    await update.message.reply_text(welcome_text, parse_mode=constants.ParseMode.MARKDOWN)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles incoming text messages.
    """
    user_text = update.message.text
    
    if not user_text:
        return

    # 1. UX: Show "Typing..." status so the user knows the AI is thinking
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=constants.ChatAction.TYPING)

    # 2. PROCESS: Offload the blocking Cerebras call to a separate thread
    # This ensures the bot remains responsive to other users while waiting.
    loop = asyncio.get_running_loop()
    
    # Execute the blocking function in a default executor
    ai_response = await loop.run_in_executor(None, get_cerebras_response, user_text)

    # 3. REPLY: Send the AI's response back to Telegram
    # We split long messages if they exceed Telegram's limit (4096 chars)
    if len(ai_response) > 4096:
        for x in range(0, len(ai_response), 4096):
            await update.message.reply_text(ai_response[x:x+4096])
    else:
        await update.message.reply_text(ai_response)

# --- MAIN EXECUTION ---
if __name__ == '__main__':
    # Validate Token Presence
    if not config.TELEGRAM_BOT_TOKEN or config.TELEGRAM_BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        logger.critical("Telegram Bot Token is missing in config.py!")
        exit(1)

    # Build the Application
    application = ApplicationBuilder().token(config.TELEGRAM_BOT_TOKEN).build()

    # Register Handlers
    start_handler = CommandHandler('start', start)
    # Filters.TEXT & ~filters.COMMAND ensure we only reply to text that isn't a command
    msg_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message)

    application.add_handler(start_handler)
    application.add_handler(msg_handler)

    print(":: SYSTEM ONLINE :: Telegram Bot is listening...")
    
    # Run the bot
    application.run_polling()
