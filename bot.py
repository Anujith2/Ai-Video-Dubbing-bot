import os
import threading
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from moviepy.video.io.VideoFileClip import VideoFileClip
from gtts import gTTS
import speech_recognition as sr
from googletrans import Translator

# ----------------- RENDER KEEP-ALIVE (FLASK APP) -----------------
app = Flask('')

@app.route('/')
def home():
    return "Telegram Free AI Dubbing Bot is running!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = threading.Thread(target=run_web)
    t.start()
# -----------------------------------------------------------------

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")

# 8 Languages List (gTTS language codes)
LANGUAGES = {
    "lang_te": ("Telugu", "te"),
    "lang_kn": ("Kannada", "kn"),
    "lang_hi": ("Hindi", "hi"),
    "lang_ta": ("Tamil", "ta"),
    "lang_bn": "Bengali", # note: handled below
    "lang_mr": ("Marathi", "mr"),
    "lang_en": ("English", "en"),
    "lang_ml": ("Malayalam", "ml")
}

# Safer mapping for gtts codes
LANG_CODES = {
    "lang_te": "te",
    "lang_kn": "kn",
    "lang_hi": "hi",
    "lang_ta": "ta",
    "lang_bn": "bn",
    "lang_mr": "mr",
    "lang_en": "en",
    "lang_ml": "ml"
}

LANG_NAMES = {
    "lang_te": "Telugu",
    "lang_kn": "Kannada",
    "lang_hi": "Hindi",
    "lang_ta": "Tamil",
    "lang_bn": "Bengali",
    "lang_mr": "Marathi",
    "lang_en": "English",
    "lang_ml": "Malayalam"
}

# /start Command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("💬 Contact Admin", url="https://t.me/anujith1238")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "Hello! 👋\n"
        "I am a Free AI Dubbing Bot. Send me any short video, and I can translate and dub it into your preferred language!\n\n"
        "Send your video now to get started.",
        reply_markup=reply_markup
    )

# Handle incoming video
async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    video = update.message.video or update.message.document
    if not video:
        await update.message.reply_text("Please send a valid video file.")
        return

    status_msg = await update.message.reply_text("📥 Downloading video, please wait...")
    
    try:
        file = await context.bot.get_file(video.file_id)
        input_video_path = f"input_{update.message.chat_id}.mp4"
        await file.download_to_drive(input_video_path)
        
        context.user_data['video_path'] = input_video_path

        keyboard = []
        row = []
        for code, name in LANG_NAMES.items():
            row.append(InlineKeyboardButton(name, callback_data=code))
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await status_msg.edit_text(
            "✅ Video received successfully! 🎬\n"
            "Please select the language you want to translate and dub into:",
            reply_markup=reply_markup
        )
    except Exception as e:
        await status_msg.edit_text(f"❌ Failed to download video: {str(e)}")

# Process button click and dub video for FREE
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    callback_data = query.data
    lang_name = LANG_NAMES.get(callback_data)
    target_lang_code = LANG_CODES.get(callback_data)
    
    video_path = context.user_data.get('video_path')

    if not video_path or not os.path.exists(video_path):
        await query.edit_message_text("❌ Video file lost. Please send the video again.")
        return

    await query.edit_message_text(f"⏳ Dubbing video into {lang_name} (Free Mode). Please wait...")

    try:
        # 1. Extract audio from video (as WAV for Speech Recognition)
        audio_path = f"audio_{query.message.chat_id}.wav"
        video_clip = VideoFileClip(video_path)
        
        # Check if video has audio
        if video_clip.audio is None:
            await query.edit_message_text("❌ The video does not contain any audio!")
            return
            
        video_clip.audio.write_audiofile(audio_path, fps=16000, nbytes=2, codec='pcm_s16le', logger=None)
        
        # 2. Convert Speech to Text using Free Google Speech Recognition (Malayalam source)
        recognizer = sr.Recognizer()
        with sr.AudioFile(audio_path) as source:
            audio_data = recognizer.record(source)
            try:
                # Assuming input video is in Malayalam ('ml-IN')
                recognized_text = recognizer.recognize_google(audio_data, language="ml-IN")
            except sr.UnknownValueError:
                recognized_text = "Could not understand audio"
            except sr.RequestError:
                recognized_text = "Speech service error"

        # 3. Translate text to target language using Google Translator
        translator = Translator()
        translated = translator.translate(recognized_text, dest=target_lang_code)
        final_text = translated.text

        if not final_text or final_text == "Could not understand audio":
            final_text = "Hello, this is a dubbed video test."

        # 4. Convert translated text to voice using gTTS
        output_audio_path = f"output_audio_{query.message.chat_id}.mp3"
        tts = gTTS(text=final_text, lang=target_lang_code, slow=False)
        tts.save(output_audio_path)

        # 5. Merge new audio with the video
        new_audio = VideoFileClip(output_audio_path)
        final_video_clip = video_clip.set_audio(new_audio)
        output_video_path = f"output_video_{query.message.chat_id}.mp4"
        final_video_clip.write_videofile(output_video_path, codec="libx264", audio_codec="aac", logger=None)

        video_clip.close()
        new_audio.close()

        # 6. Send the dubbed video back to the user
        with open(output_video_path, "rb") as vid:
            await context.bot.send_video(
                chat_id=query.message.chat_id, 
                video=vid, 
                caption=f"✨ Successfully dubbed into {lang_name} (Free Version)!"
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

    print("🤖 Free Bot is up and running...")
    application.run_polling()

if __name__ == "__main__":
    main()
