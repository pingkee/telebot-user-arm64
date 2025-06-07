from datetime import datetime, timezone, timedelta
from sentence_transformers import SentenceTransformer
from telethon import TelegramClient
from session_manager import SessionManager
import httpx
import os

SIMILARITY_THRESHOLD = 0.352
session_mgr = SessionManager()

class LLMHandler:
    def __init__(self, model_name, qdrant_client, llm_url, llm_model, telegram_client):
        self.model = SentenceTransformer(model_name)
        self.qdrant = qdrant_client
        self.llm_model = llm_model
        self.client = telegram_client
        self.LLM_API_URL = llm_url

    async def fetch_context_and_history(self, chat, sender_id, user_msg, current_msg_id=None):
        embedding = self.model.encode([user_msg], normalize_embeddings=True)[0].tolist()

        results = self.qdrant.search(
            collection_name="outreach",
            query_vector=embedding,
            limit=5,
            with_payload=True,
        )

        relevant_contexts = [
            hit.payload["text"]
            for hit in results
            if hit.payload and "text" in hit.payload and hit.score >= SIMILARITY_THRESHOLD
        ]

        cutoff = datetime.now(timezone.utc) - timedelta(days=3)
        turns = []

        async for msg in self.client.iter_messages(chat, limit=100, reverse=True):
            if not msg.date:
                continue
            msg_date = msg.date.replace(tzinfo=timezone.utc)
            if msg_date < cutoff or (current_msg_id and msg.id == current_msg_id):
                continue
            if msg.message:
                role = "User" if msg.sender_id == sender_id else "Assistant"
                turns.append(f"{role}: {msg.message.strip()}")
            if len(turns) >= 20:
                break

        history = {
            "role": "user",
            "content": "Conversation history:\n" + "\n".join(turns)
        }

        return relevant_contexts, history

    async def respond_with_llm(self, event, system_prompt):
        user_msg = event.message.message
        chat = await event.get_chat()
        sender = await event.get_sender()

        relevant, history = await self.fetch_context_and_history(chat, sender.id, user_msg, event.message.id)

        context_section = {
            "role": "system",
            "content": (
                "Context obtain from assistant database:\n" + "\n\n".join(relevant)
                if relevant else "No relevant context found in the database."
            )
        }

        payload = {
            "model": self.llm_model,
            "messages": [
                system_prompt,
                context_section,
                history,
                {"role": "user", "content": user_msg}
            ],
            "top_p": 1,
            "n": 1,
            "temperature": 0.7,
            "max_tokens": 512,
            "stream": False,
            "frequency_penalty": 0
        }

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(600.0)) as client:
                response = await client.post(self.LLM_API_URL, json=payload)
                response.raise_for_status()
                data = response.json()
                reply = data['choices'][0]['message']['content']

                # ✅ Check if the session still exists before replying
                if not await session_mgr.exists(sender.id):
                    print(f"[LLM] Session canceled before response could be sent to {sender.id}. Suppressing reply.")
                    return

                await event.respond(f"[AI]: {reply.strip()}")

        except httpx.HTTPError as e:
            print(f"[ERROR] LLM API call failed: {e}")

            # Still check session before replying with error
            if await session_mgr.exists(sender.id):
                await event.respond("[AI]: Sorry, backend system down!")
