import asyncio
from telethon import TelegramClient, events
from sentence_transformers import SentenceTransformer
from sentence_transformers.util import normalize_embeddings
from qdrant_client import QdrantClient
from session_manager import SessionManager
from llm_handler import LLMHandler
from timers import TimerHandler
import os

# Access control
AUTHORIZED_USER_IDS = [
    # 1234566,
    ]  # Replace with actual user IDs allowed to interact
IGNORE_IDS = [987654321, -1001234567890]      # Blocked users or group/chat IDs

# Your Telegram API credentials (from https://my.telegram.org)

# Load from environment
api_id = int(os.environ.get("TELEGRAM_API_ID", 0))
api_hash = os.environ.get("TELEGRAM_API_HASH", "")
emb_model = os.environ.get("EMB_MODEL", "sentence-transformers/all-mpnet-base-v2")
llm_model = os.environ.get("LLM_MODEL", "llama3.1:8b")
qdrant_ip = os.environ.get("QDRANT_IP", "localhost")  # fallback default
qdrant_port = os.environ.get("QDRANT_PORT", "6333")  # fallback default
llm_url = os.environ.get("LLM_URL", "localhost")  # fallback default
llm_port = os.environ.get("LLM_PORT", "11434")  # fallback default

LLM_API_URL = f"http://{llm_url}:{llm_port}/v1/chat/completions"

# Constants
STATE_WAITING = "waiting_prompt"
STATE_PROMPTED = "prompted"
STATE_TALKING = "talking_ai"
STATE_SILENT = "silent"

# LLM configuration
SYSTEM_PROMPT = {
    "role": "system",
    "content": """
    You are a helpful system troubleshooting assistant. Be concise, direct, and clear. Avoid unnecessary elaboration or filler words. Only provide only factual and relevant information based on the context. 
    If a question does not need extra detail, keep your response brief. Use a tone that is professional, calm, and tactful. Do not explain your reasoning unless explicitly asked. if you have insufficient data just say you do not know.
    the system you are working on is a web application with mobile application for the military Command and control. its main feature includes but not limited to, force tracking, video streaming, incident creation and ops logs with critical event table. 
    """
}
SIMILARITY_THRESHOLD = 0.352

# Validate required variables
if not all([api_id, api_hash]):
    raise ValueError("Missing one of the required environment variables: TELEGRAM_API_ID, TELEGRAM_API_HASH")

# Initialize
pending_responses = {}
pending_lock = asyncio.Lock()

model = SentenceTransformer(emb_model)
qdrant = QdrantClient(qdrant_ip, port=qdrant_port)
session_name = os.environ.get("TELETHON_SESSION", "userbot_session")
client = TelegramClient(session_name, api_id, api_hash)

# Init classes 
# === Utility Functions ===
session_mgr = SessionManager()
llm = LLMHandler(emb_model, qdrant, LLM_API_URL, llm_model, client)
timers = TimerHandler(session_mgr)

# === Telegram Event Handlers ===
@client.on(events.NewMessage(incoming=True))
async def main_handler(event):
    sender = await event.get_sender()
    chat_id = event.chat_id
    sender_id = sender.id
    msg_text = event.raw_text.strip().lower()

    # Filter unwanted sources
    if not event.is_private or sender_id in IGNORE_IDS or chat_id in IGNORE_IDS:
        return

    # Detect manual reply from yourself
    me = await client.get_me()
    print(f"[DEBUG] me.id = {me.id}, event.sender_id = {event.sender_id}, sender_id = {sender_id}")

    if event.sender_id == me.id:
        print("[MANUAL REPLY] Detected manual reply from yourself")
        async with session_mgr.lock:
            to_cancel = list(session_mgr.sessions.keys())

        for user_id in to_cancel:
            print(f"[MANUAL REPLY] Cancelling LLM and starting silent timeout for user {user_id}")
            await session_mgr.cancel_session(user_id)

            # Cancel any running LLM task
            await session_mgr.cancel_llm_task(user_id)

            # Start a silent session that lasts 3 hours (10800 seconds)
            await session_mgr.start_session(user_id, STATE_SILENT, event.respond)
            await timers.schedule_silent_period(user_id)
        return



    # Authorized user — respond directly
    if sender_id in AUTHORIZED_USER_IDS:
        await llm.respond_with_llm(event, SYSTEM_PROMPT)
        return

    # === Unauthorized User Handling ===
    print(f"[UNAUTHORIZED] User {sender_id} sent: {event.raw_text}")

    current_state = await session_mgr.get_state(sender_id)

    # === SILENT state (manual override active) ===
    if current_state == STATE_SILENT:
        print(f"[SILENT STATE] Ignoring message from {sender_id} during manual response timeout")
        return
    
    # === PROMPTED state ===
    if current_state == STATE_PROMPTED:
        if msg_text in ["yes", "no"]:
            if msg_text == "yes":
                await session_mgr.update_state(sender_id, STATE_TALKING)
                await event.respond("[AI]: At any moment if you would like to end the chat with me, just respond with 'End discussion'.")
                await event.respond("[AI]: How can I help?")
                await session_mgr.schedule_timeout(sender_id, 600, lambda: timers.schedule_inactivity_prompt(sender_id))
            else:
                await event.respond("[system]: No problem! Ping Kee will get to you as soon as he can.")
                await session_mgr.cancel_session(sender_id)

                # Trigger 3-hour silent mode
                await session_mgr.start_session(sender_id, STATE_SILENT, event.respond)
                await timers.schedule_silent_period(sender_id)
        else:
            await event.respond("[system]: Please reply with just 'Yes' or 'No'.")
        return


    # === TALKING state ===
    elif current_state == STATE_TALKING:
        if msg_text == "end discussion":
            await event.respond("[AI]: Okay, ending AI conversation.")
            await session_mgr.cancel_session(sender_id)
            return

        await session_mgr.set_responding(sender_id, True)

        # Wrap LLM call in cancellable task
        await session_mgr.run_cancellable_llm(
            sender_id,
            llm.respond_with_llm(event, SYSTEM_PROMPT)
        )

        # Clear responding flag after done
        await session_mgr.set_responding(sender_id, False)

        # Schedule timeout only if not responding (double check)
        if await session_mgr.exists(sender_id):
            await session_mgr.schedule_timeout(sender_id, 600, lambda: timers.schedule_inactivity_prompt(sender_id))
        return

    # === New or Waiting State ===
    elif current_state is None:
        print(f"[DEBUG] Scheduling 5-minute prompt for user {sender_id}")
        await session_mgr.start_session(sender_id, STATE_WAITING, event.respond)
        await session_mgr.schedule_timeout(sender_id, 300, lambda: timers.schedule_initial_prompt(sender_id))
        return

# === Run Bot ===
async def main():
    print("Userbot is running — responding only to authorized users.")
    print(f"Qdrant URL: {qdrant_ip}")
    
    await client.connect()
    if not await client.is_user_authorized():
        raise RuntimeError("User is not authorized. Generate the session file interactively first.")

    await client.run_until_disconnected()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())