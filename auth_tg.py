from telethon import TelegramClient
import asyncio

api_id = 20879464
api_hash = '9f7455ec162aa0a39af1f7e97b9e7d9d'
client = TelegramClient('horus_final_auth', api_id, api_hash)

async def main():
    await client.start()
    print("✅ Sesión validada con éxito!")

asyncio.run(main())