import asyncio
from sentence_transformers.util import normalize_embeddings

class SessionManager:
    def __init__(self):
        self.sessions = {}
        self.lock = asyncio.Lock()
        self.is_responding = {}  # Track whether LLM is responding per user

    async def start_session(self, user_id, state, respond_func):
        print(f"[SESSION] Starting session for {user_id} with state: {state}")
        await self.cancel_session(user_id)
        async with self.lock:
            self.sessions[user_id] = {
                "state": state,
                "respond": respond_func,
                "timeout_task": None,
                "last_prompt_time": None
            }
            self.is_responding[user_id] = False  # Initialize responding flag
        print(f"[SESSION] Session stored for {user_id}")

    async def update_state(self, user_id, new_state):
        async with self.lock:
            session = self.sessions.get(user_id)
            if session:
                session["state"] = new_state

    async def cancel_session(self, user_id):
        async with self.lock:
            session = self.sessions.pop(user_id, None)
            if session:
                if session.get("timeout_task"):
                    session["timeout_task"].cancel()
                    try:
                        await session["timeout_task"]
                    except asyncio.CancelledError:
                        pass

                if session.get("llm_task"):
                    session["llm_task"].cancel()
                    try:
                        await session["llm_task"]
                    except asyncio.CancelledError:
                        pass

            self.is_responding.pop(user_id, None)

    async def run_cancellable_llm(self, user_id, coro):
        task = asyncio.create_task(coro)
        async with self.lock:
            session = self.sessions.get(user_id)
            if session:
                session["llm_task"] = task

        try:
            await task
        except asyncio.CancelledError:
            print(f"[CANCEL] LLM task cancelled for user {user_id}")
        finally:
            async with self.lock:
                session = self.sessions.get(user_id)
                if session:
                    session["llm_task"] = None

    async def get_state(self, user_id):
        async with self.lock:
            session = self.sessions.get(user_id)
            return session["state"] if session else None

    async def schedule_timeout(self, user_id, delay, func):
        async def wrapped():
            print(f"[SESSION] Timeout task started for user {user_id}, waiting {delay} seconds")
            await asyncio.sleep(delay)
            print(f"[SESSION] Timeout task running function for user {user_id}")
            await func()

        async with self.lock:
            session = self.sessions.get(user_id)
            if not session:
                print(f"[SESSION] No active session for user {user_id} when scheduling timeout")
                return
            if session.get("timeout_task"):
                print(f"[SESSION] Cancelling previous timeout task for user {user_id}")
                session["timeout_task"].cancel()

            task = asyncio.create_task(wrapped())
            session["timeout_task"] = task
            print(f"[SESSION] Scheduled new timeout task for user {user_id} with delay {delay}s")

    async def exists(self, user_id):
        async with self.lock:
            return user_id in self.sessions

    async def get_respond_func(self, user_id):
        async with self.lock:
            session = self.sessions.get(user_id)
            return session["respond"] if session else None

    async def is_state(self, user_id, state):
        async with self.lock:
            session = self.sessions.get(user_id)
            return session and session.get("state") == state

    # New helper methods to set/check responding flag
    async def set_responding(self, user_id, value: bool):
        async with self.lock:
            self.is_responding[user_id] = value

    async def get_responding(self, user_id) -> bool:
        async with self.lock:
            return self.is_responding.get(user_id, False)
