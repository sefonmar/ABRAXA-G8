from telethon import TelegramClient
import datetime
import re 

API_ID = 20879464
API_HASH = '9f7455ec162aa0a39af1f7e97b9e7d9d'

def clean_institutional_text(text):
    """Purga total de OTC y enlaces para look de terminal profesional"""
    if not text: return ""
    # Eliminación de OTC y enlaces (Regex optimizado)
    text = re.sub(r'\bOTC\b', '', text, flags=re.IGNORECASE)
    text = re.sub(r'https?://\S+|www\.\S+|t\.me/\S+', '', text)
    return re.sub(r'\s+', ' ', text).strip()

async def fetch_latest_news(limit=300): # Aumentamos a 300 para el historial completo
    client = TelegramClient('horus_final_auth', API_ID, API_HASH)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            return [{"text": "⚠️ REQUIERE LOGIN", "date": "", "impact": "LOW"}]
        
        entity = await client.get_entity('https://t.me/ultimominutoOTCForex')
        messages = []
        high_impact = ['fed', 'cpi', 'nfp', 'rates', 'bofa', 'inflation', 'gold', 'powell', 'urgent', 'rbnz']
        
        async for message in client.iter_messages(entity, limit=limit):
            if message.text:
                cleaned = clean_institutional_text(message.text)
                if cleaned:
                    impact = "HIGH" if any(word in cleaned.lower() for word in high_impact) else "NORMAL"
                    messages.append({
                        "text": cleaned,
                        "date": message.date.strftime("%H:%M | %d %b"),
                        "impact": impact
                    })
        await client.disconnect()
        return messages
    except Exception as e:
        return [{"text": f"Error: {str(e)}", "date": "", "impact": "LOW"}]