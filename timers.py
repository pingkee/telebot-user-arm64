import asyncio
from session_manager import SessionManager

# Constants
STATE_WAITING = "waiting_prompt"
STATE_PROMPTED = "prompted"
STATE_TALKING = "talking_ai"
STATE_SILENT = "silent"

class TimerHandler:
    def __init__(self, session_mgr: SessionManager):
        self.session_mgr = session_mgr

    async def schedule_inactivity_prompt(self, sender_id):
        await asyncio.sleep(600)
        if await self.session_mgr.is_state(sender_id, "talking_ai"):
            respond = await self.session_mgr.get_respond_func(sender_id)
            if respond:
                print(f"[TIMER] Sending inactivity prompt to user {sender_id}")
                await respond("[AI]: Still around? Do you still need my help? Reply 'Yes' or 'No'.")
                await self.session_mgr.update_state(sender_id, "prompted")
                await self.session_mgr.schedule_timeout(sender_id, 600, lambda: self.auto_end_session(sender_id))

    async def schedule_initial_prompt(self, sender_id):
        print(f"[TIMER] schedule_initial_prompt() called for {sender_id}")
        await asyncio.sleep(300)  # shortened for testing

        current_state = await self.session_mgr.get_state(sender_id)
        print(f"[TIMER] Current state for {sender_id} is '{current_state}' (expecting 'waiting_prompt')")
        print(f"[TIMER] Woke up after sleep for {sender_id}")

        if current_state == STATE_WAITING:
            print(f"[TIMER] User {sender_id} still in 'waiting_prompt' state")
            respond = await self.session_mgr.get_respond_func(sender_id)
            if respond:
                print(f"[TIMER] Respond function exists. Sending message to {sender_id}")
                await respond(
                    "[system]: Hi, Ping Kee is currently busy. Would you like to talk to his AI assistant instead? Reply with 'Yes' or 'No' only."
                )
                await self.session_mgr.update_state(sender_id, "prompted")
            else:
                print(f"[TIMER] No respond function for {sender_id}")
        else:
            print(f"[TIMER] User {sender_id} is no longer in 'waiting_prompt' state")

    async def auto_end_session(self, sender_id):
        await asyncio.sleep(600)
        if await self.session_mgr.is_state(sender_id, "prompted"):
            respond = await self.session_mgr.get_respond_func(sender_id)
            if respond:
                print(f"[TIMER] Auto ending session for user {sender_id} due to inactivity")
                await respond("[AI]: Ending our session due to inactivity. Feel free to message again anytime.")
            await self.session_mgr.cancel_session(sender_id)
            
    async def schedule_silent_period(self, sender_id):
        print(f"[TIMER] Starting 3-hour silent period for user {sender_id}")
        await asyncio.sleep(10800)  # 3 hours

        current_state = await self.session_mgr.get_state(sender_id)
        if current_state == STATE_SILENT:
            print(f"[TIMER] Silent period expired for user {sender_id}. Reverting to STATE_WAITING.")
            await self.session_mgr.cancel_session(sender_id)  # End silent session
            await self.session_mgr.start_session(sender_id, STATE_WAITING)
            await self.schedule_initial_prompt(sender_id)
