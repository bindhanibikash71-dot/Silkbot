import os
import json
import requests
import urllib.parse
from gtts import gTTS
import telebot
from flask import Flask, request
from openai import OpenAI

# ==========================================
# 1. LOAD ENVIRONMENT VARIABLES
# ==========================================
BOT_TOKEN = os.environ.get('BOT_TOKEN')
OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY')
RENDER_EXTERNAL_URL = os.environ.get('RENDER_EXTERNAL_URL')
ADMIN_ID = os.environ.get('ADMIN_ID')

if not BOT_TOKEN or not OPENROUTER_API_KEY or not ADMIN_ID:
    raise ValueError("Bhai, Environment variables (BOT_TOKEN, OPENROUTER_API_KEY, ADMIN_ID) check karo!")

# ==========================================
# 2. INITIALIZE BOT & API
# ==========================================
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# Bot ki details get karna (Username check karne ke liye)
try:
    BOT_INFO = bot.get_me()
    BOT_USERNAME = BOT_INFO.username
except Exception as e:
    BOT_USERNAME = ""

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
    default_headers={
        "HTTP-Referer": RENDER_EXTERNAL_URL if RENDER_EXTERNAL_URL else "http://localhost",
        "X-Title": "Pro Telegram Group Bot"
    }
)

AI_MODEL = "z-ai/glm-4.5-air:free"

# ==========================================
# 3. DATABASE (Chat IDs save karne ke liye)
# ==========================================
CHATS_FILE = 'chats.json'

def load_chats():
    if os.path.exists(CHATS_FILE):
        with open(CHATS_FILE, 'r') as f:
            try: return set(json.load(f))
            except: return set()
    return set()

def save_chat(chat_id):
    chats = load_chats()
    if chat_id not in chats:
        chats.add(chat_id)
        with open(CHATS_FILE, 'w') as f:
            json.dump(list(chats), f)

# ==========================================
# 4. ADMIN PANEL (Broadcast & Stats)
# ==========================================
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if str(message.from_user.id) != str(ADMIN_ID): return
    text = (
        "👑 **Pro Admin Panel** 👑\n\n"
        "📊 `/stats` - Total Groups/Users\n"
        "📢 `/broadcast <msg>` - Promotion message bhejein."
    )
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(commands=['stats'])
def bot_stats(message):
    if str(message.from_user.id) != str(ADMIN_ID): return
    chats = load_chats()
    bot.reply_to(message, f"📊 **Bot Stats**\n\nBot is active in **{len(chats)}** chats.", parse_mode="Markdown")

@bot.message_handler(commands=['broadcast'])
def broadcast_message(message):
    if str(message.from_user.id) != str(ADMIN_ID): return
    broadcast_text = message.text.replace('/broadcast', '').strip()
    if not broadcast_text:
        bot.reply_to(message, "⚠️ Example: `/broadcast Follow my page!`")
        return

    chats = load_chats()
    success, failed = 0, 0
    bot.reply_to(message, "⏳ Broadcast in progress...")

    for chat_id in chats:
        try:
            bot.send_message(chat_id, f"📢 **Admin Announcement:**\n\n{broadcast_text}", parse_mode="Markdown")
            success += 1
        except:
            failed += 1
    bot.reply_to(message, f"✅ **Complete!**\nSuccess: {success}\nFailed: {failed}")

# ==========================================
# 5. NEW TAGDA FEATURES 🔥
# ==========================================

# Feature 1: Welcome New Members
@bot.message_handler(content_types=['new_chat_members'])
def welcome_new_member(message):
    save_chat(message.chat.id)
    for new_member in message.new_chat_members:
        # Bot khud ko welcome na kare
        if new_member.id != BOT_INFO.id:
            welcome_text = f"🎉 Welcome to the group, [{new_member.first_name}](tg://user?id={new_member.id})!\n\nMain ek AI Bot hoon. Kuch bhi poochne ke liye mujhe mention karein ya `/ask` likhein."
            bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown")

# Feature 2: AI Image Generation (/imagine)
@bot.message_handler(commands=['imagine'])
def generate_image(message):
    save_chat(message.chat.id)
    prompt = message.text.replace('/imagine', '').strip()
    
    if not prompt:
        bot.reply_to(message, "🎨 Bhai, kya banau? Aise likho: `/imagine A futuristic city flying in the sky`")
        return

    bot.send_chat_action(message.chat.id, 'upload_photo')
    bot.reply_to(message, "⏳ AI image generate kar raha hai, please wait...")
    
    try:
        # Using free Pollinations AI for image generation
        encoded_prompt = urllib.parse.quote(prompt)
        image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true"
        bot.send_photo(message.chat.id, image_url, caption=f"🎨 **Generated:** {prompt}\n\n🤖 Powered by AI")
    except Exception as e:
        bot.reply_to(message, "⚠️ Image generate nahi ho payi bhai. Thodi der baad try karo.")

# Feature 3: Voice Answer (/voice)
@bot.message_handler(commands=['voice'])
def handle_voice_ask(message):
    save_chat(message.chat.id)
    query = message.text.replace('/voice', '').strip()
    
    if not query:
        bot.reply_to(message, "🎤 Bhai, kuch poocho toh! Example: `/voice Tell me a joke`")
        return

    bot.send_chat_action(message.chat.id, 'record_audio')
    
    try:
        # 1. Get Answer from AI
        response = client.chat.completions.create(
            model=AI_MODEL,
            messages=[
                {"role": "system", "content": "You are a helpful AI. Give short and direct answers because it will be converted to audio."},
                {"role": "user", "content": query}
            ],
            max_tokens=150
        )
        reply_text = response.choices[0].message.content

        # 2. Convert text to speech
        tts = gTTS(text=reply_text, lang='en') # Change 'en' to 'hi' for Hindi voice
        filename = f"voice_{message.message_id}.mp3"
        tts.save(filename)

        # 3. Send Voice Note
        with open(filename, 'rb') as audio:
            bot.send_voice(message.chat.id, audio)
        
        # 4. Clean up file
        os.remove(filename)

    except Exception as e:
        bot.reply_to(message, f"⚠️ Voice banne me error aaya: `{str(e)}`", parse_mode="Markdown")

# ==========================================
# 6. GENERAL AI CHAT (Ask & Smart Mention)
# ==========================================

def get_ai_response(query):
    response = client.chat.completions.create(
        model=AI_MODEL,
        messages=[
            {"role": "system", "content": "You are a helpful and smart Telegram group assistant. Give concise and formatting-friendly answers."},
            {"role": "user", "content": query}
        ],
        max_tokens=300
    )
    return response.choices[0].message.content

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    save_chat(message.chat.id)
    help_text = (
        f"👋 **Welcome to the Advanced AI Bot!**\n\n"
        "Here is what I can do:\n"
        "💬 `/ask <question>` - Ask me anything.\n"
        "🎤 `/voice <question>` - Get answer in a Voice Note.\n"
        "🎨 `/imagine <prompt>` - Generate an AI Image.\n\n"
        f"💡 *Pro Tip:* Aap directly mujhe tag kar ke (`@{BOT_USERNAME} hello`) ya mere message ka reply kar ke bhi baat kar sakte hain!"
    )
    bot.reply_to(message, help_text, parse_mode="Markdown")

@bot.message_handler(commands=['ask'])
def handle_ask(message):
    save_chat(message.chat.id)
    query = message.text.replace('/ask', '').strip()
    if not query:
        bot.reply_to(message, "Bhai question likho! `/ask What is AI?`")
        return
    bot.send_chat_action(message.chat.id, 'typing')
    try:
        bot.reply_to(message, get_ai_response(query))
    except Exception as e:
        bot.reply_to(message, f"⚠️ Error: `{str(e)}`")

# Feature 4: Smart Tag/Reply Handler (No /ask needed)
@bot.message_handler(func=lambda message: True, content_types=['text'])
def handle_all_text(message):
    save_chat(message.chat.id)
    
    is_reply_to_bot = message.reply_to_message and message.reply_to_message.from_user.id == BOT_INFO.id
    is_bot_mentioned = BOT_USERNAME and f"@{BOT_USERNAME}" in message.text

    # Agar bot ko tag kiya gaya hai, ya bot ke message ka reply kiya hai
    if is_reply_to_bot or is_bot_mentioned:
        # Message me se bot ka naam hata do taaki AI confuse na ho
        query = message.text.replace(f"@{BOT_USERNAME}", "").strip()
        
        if not query and is_bot_mentioned:
            bot.reply_to(message, "Haan bhai, bolo kya madad karun?")
            return

        bot.send_chat_action(message.chat.id, 'typing')
        try:
            bot.reply_to(message, get_ai_response(query))
        except Exception as e:
            bot.reply_to(message, f"⚠️ Error: `{str(e)}`")

# ==========================================
# 7. FLASK ROUTES
# ==========================================

@app.route('/', methods=['GET'])
def index():
    return f"Pro Telegram Group Help Bot is running!", 200

@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '', 200
    else:
        return 'Forbidden', 403

if RENDER_EXTERNAL_URL:
    bot.remove_webhook()
    bot.set_webhook(url=f"{RENDER_EXTERNAL_URL}/{BOT_TOKEN}")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
