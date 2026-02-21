import asyncio
from telethon import TelegramClient

# TUS CREDENCIALES REALES
api_id = 20879464 
api_hash = '9f7455ec162aa0a39af1f7e97b9e7d9d'

async def main():
    # Creamos la sesión definitiva
    client = TelegramClient('horus_real_session', api_id, api_hash)
    await client.start()
    print("✅ ¡SESIÓN CREADA CON ÉXITO! Ya puedes volver a app.py")
    await client.disconnect()

if __name__ == '__main__':
    asyncio.run(main())