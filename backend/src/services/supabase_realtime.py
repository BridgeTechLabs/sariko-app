from typing import Optional
import os
import logging
        
import asyncio
from realtime import AsyncRealtimeClient, RealtimeSubscribeStates

logger = logging.getLogger(__name__)

async def keep_realtime_alive():
    
    SUPABASE_PROJECT_ID = os.environ.get("SUPABASE_PROJECT_ID", None)
    SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", None)
    REALTIME_URL = f"wss://{SUPABASE_PROJECT_ID}.supabase.co/realtime/v1"
    
    if not SUPABASE_PROJECT_ID or not SUPABASE_ANON_KEY:
        logger.error("SUPABASE_PROJECT_ID and SUPABASE_ANON_KEY must be set in environment variables.")
        return
    
    try:
        logger.warning("Keepalive: Starting...")
        client = AsyncRealtimeClient(REALTIME_URL, SUPABASE_ANON_KEY)
        await client.connect()

        channel = client.channel("backend-keepalive")    
        channel.on_broadcast('ping', lambda payload: None)

        def _on_subscribe(status: RealtimeSubscribeStates, err: Optional[Exception]):

            logger.warning(f"status {status}")

            if status == RealtimeSubscribeStates.SUBSCRIBED:
                logger.warning("Realtime keepalive: CONNECTED ✅")
            elif status == RealtimeSubscribeStates.CHANNEL_ERROR:
                logger.warning(f"Realtime keepalive: ERROR ❌ {err}")
            elif status == RealtimeSubscribeStates.TIMED_OUT:
                logger.warning("Realtime keepalive: TIMEOUT ❌")

        await channel.subscribe(_on_subscribe)
        logger.warning("Keepalive: Subscribed, starting heartbeat loop")

        while True:
            await channel.send_broadcast('ping', {})
            await channel.send_broadcast('ping', {})
            is_alive = client.is_connected  # hoặc channel.state == "joined"
            logger.debug(f"Keepalive: ping sent, connected={is_alive}")
            await asyncio.sleep(30)

    except Exception as e:
        logger.error(f"Keepalive crashed: {e}")