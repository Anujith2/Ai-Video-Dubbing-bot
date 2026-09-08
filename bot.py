import os
import threading
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from moviepy.video.io.VideoFileClip import VideoFileClip
from openai import OpenAI
from gtts import gTTS

# ----------------- RENDER KEEP-ALIVE (FLASK APP) -----------------
app = Flask('')

@app.route('/')
def home():
    return "Telegram AI Dubbing Bot is running!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = threading.Thread(target=run_web)
    t.start()
# -----------------------------------------------------------------

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "YOUR_OPENAI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")

client = OpenAI(api_key=OPENAI_API_KEY)

# 8 Languages List
LANGUAGES = {
    "lang_te": "Telugu",
    "lang_kn": "Kannada",
    "lang_hi": "Hindi",
    "lang_ta": "Tamil",
    "lang_bn": "Bengali",
    "lang_mr": "Marathi",
    "lang_en": "English",
    "lang_ml": "Malayalam"
}

# /start Command with English text and Admin Contact Button
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("💬 Contact Admin", url="https://t.me/anujith1238")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "Hello! 👋\n"
        "I am an AI Dubbing Bot. Send me any video, and I can translate and dub it into your preferred language!\n\n"
        "Send your video now to get started.",
        reply_markup=reply_markup
    )

# Handle incoming video
async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    video = update.message.video or update.message.document
    if not video:
        await update.message.reply_text("Please send a valid video file.")
        return

    status_msg = await update.message.reply_text("Downloading video, please wait...")
    
    file = await context.bot.get_file(video.file_id)
    input_video_path = f"input_{update.message.chat_id}.mp4"
    await file.download_to_drive(input_video_path)
    
    context.user_data['video_path'] = input_video_path

    # Create 8 languages inline buttons in a grid format (2 columns)
    keyboard = []
    row = []
    for code, name in LANGUAGES.items():
        row.append(InlineKeyboardButton(name, callback_data=code))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await status_msg.edit_text(
        "Video received successfully! 🎬\n"
        "Please select the language you want to translate and dub into:",
        reply_markup=reply_markup
    )

# Process button click and dub video
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    callback_data = query.data
    lang_name = LANGUAGES.get(callback_data)
    target_lang_code = callback_data.replace("lang_", "")
    
    video_path = context.user_data.get('video_path')

    if not video_path or not os.path.exists(video_path):
        await query.edit_message_text("Video file lost. Please send the video again.")
        return

    await query.edit_message_text(f"⏳ Dubbing video into {lang_name}. Please wait a moment...")

    try:
        # 1. Extract audio from video
        audio_path = f"audio_{query.message.chat_id}.mp3"
        video_clip = VideoFileClip(video_path)
        video_clip.audio.write_audiofile(audio_path, logger=None)
        
        # 2. Translate audio using Whisper API
        with open(audio_path, "rb") as audio_file:
            transcript = client.audio.translations.create(model="whisper-1", file=audio_file)
        translated_text = transcript.text

        # 3. Convert translated text to voice using gTTS
        output_audio_path = f"output_audio_{query.message.chat_id}.mp3"
        tts = gTTS(text=translated_text, lang=target_lang_code, slow=False)
        tts.save(output_audio_path)

        # 4. Merge new audio with the video
        new_audio = VideoFileClip(output_audio_path)
        final_video_clip = video_clip.set_audio(new_audio)
        output_video_path = f"output_video_{query.message.chat_id}.mp4"
        final_video_clip.write_videofile(output_video_path, codec="libx264", audio_codec="aac", logger=None)

        video_clip.close()
        new_audio.close()

        # 5. Send the dubbed video back to the user
        with open(output_video_path, "rb") as vid:
            await context.bot.send_video(
                chat_id=query.message.chat_id, 
                video=vid, 
                caption=f"✨ Successfully dubbed into {lang_name}!"
            )

        # Clean up temporary files
        for p in [input_video_path, audio_path, output_audio_path, output_video_path]:
            if os.path.exists(p):
                os.remove(p)

    except Exception as e:
        await query.message.reply_text(f"❌ An error occurred during processing: {str(e)}")

def main():
    keep_alive()

    application = Application.builder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, handle_video))
    application.add_handler(CallbackQueryHandler(button_callback))

    print("🤖 Bot is up and running...")
    application.run_polling()

if __name__ == "__main__":
    main()
