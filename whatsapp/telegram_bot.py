import logging
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters
from django.conf import settings
import httpx 
import io

# Optional logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

class TelegramBot:
    def __init__(self, token):
        self.token = token
        self.webhook_url = settings.TELEGRAM_WEBHOOK_URL  # Optional
        self.django_url = settings.DJANGO_IMAGE_UPLOAD_URL

    async def start_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "👋 Welcome! To get an answer from your syllabus:\n\n"
            "1️⃣ Send the syllabus file (PDF)\n"
            "2️⃣ Then send a photo of the question.\n\n"
            "📌 You can switch the order too!"
        )

    async def document_handler(self, update, context):
        document = update.message.document
        if not document:
            await update.message.reply_text("No document found.")
            return
        if document.file_size > MAX_FILE_SIZE:
            await update.message.reply_text("❌ File too large. Please upload a file under 10MB.")
            return
        if not document.file_name.lower().endswith('.pdf'):
            await update.message.reply_text("⚠️ Only PDF syllabus files are supported.")
            return
        try:
            # Await the get_file() call
            doc_file = await document.get_file()
            doc_data = await doc_file.download_as_bytearray()
        except Exception as e:
            logger.error(f"Error downloading document: {e}")
            await update.message.reply_text("⚠️ Failed to download the file. Please try again.")
            return
        doc_filename = document.file_name or 'syllabus_file.pdf'
        context.user_data['syllabus_file'] = (doc_filename, doc_data, document.mime_type)
        # Save for retry
        context.user_data['last_action'] = 'document'
        context.user_data['last_payload'] = {'syllabus_file': context.user_data['syllabus_file']}
        if 'question_image' in context.user_data:
            await self.send_to_django(update, context)
        else:
            await update.message.reply_text("✅ Syllabus file received. Now send the question image.")

    async def photo_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            # 'get_file' is asynchronous, so we need to await it
            photo_file = await update.message.photo[-1].get_file()
            # 'download_as_bytearray' is also asynchronous, so we need to await it
            image_data = await photo_file.download_as_bytearray()
        except Exception as e:
            logger.error(f"Error downloading image: {e}")
            await update.message.reply_text("⚠️ Failed to download the image. Please try again.")
            return
        context.user_data['question_image'] = ('question.jpg', image_data, 'image/jpeg')
        # Save for retry
        context.user_data['last_action'] = 'photo'
        context.user_data['last_payload'] = {'question_image': context.user_data['question_image']}
        if 'syllabus_file' in context.user_data:
            await self.send_to_django(update, context)
        else:
            await update.message.reply_text("✅ Question image received. Now send the syllabus file (PDF).")

     # make sure this is imported at the top

    import io

    async def send_to_django(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            # Extract file tuples from user_data
            image_file = context.user_data['question_image']
            syllabus_file = context.user_data['syllabus_file']

            # Convert bytearrays to file-like objects
            files = {
                'image': (image_file[0], io.BytesIO(image_file[1]), image_file[2]),
                'syllabus': (syllabus_file[0], io.BytesIO(syllabus_file[1]), syllabus_file[2])
            }

            # Use requests instead of await, since it's not async by default
            import requests
            response = requests.post(
                self.django_url,
                files=files,
                headers={'Authorization': f'Token {settings.TELEGRAM_AUTH_TOKEN}'}
            )

            if response.status_code == 200:
                data = response.json()
                answer = data.get("answer", "✅ Files processed successfully.")
                await update.message.reply_text(f"{answer}")
                # context.user_data.clear()
            else:
                await update.message.reply_text(
                    f"❌ Failed to process files: {response.status_code}\n{response.text}\n\nSend /retry to try again."
                )

        except Exception as e:
            logger.error(f"Error sending to Django: {e}")
            await update.message.reply_text("⚠️ Error sending files to the server. Send /retry to try again.")

    async def retry_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        retry_count = context.user_data.get('retry_count', 0)
        last_action = context.user_data.get('last_action')
        last_payload = context.user_data.get('last_payload')
        if not last_action or not last_payload:
            await update.message.reply_text("Nothing to retry. Please send your files again.")
            return
        if retry_count >= 3:
            await update.message.reply_text("❌ Retry limit reached. Please start again by sending your files.")
            context.user_data.clear()
            return
        await update.message.reply_text("🔄 Retrying your last action...")
        # Resend last action
        if last_action == 'send_to_django':
            context.user_data['question_image'] = last_payload['image']
            context.user_data['syllabus_file'] = last_payload['syllabus']
            await self.send_to_django(update, context)
        elif last_action == 'photo':
            context.user_data['question_image'] = last_payload['question_image']
            if 'syllabus_file' in context.user_data:
                await self.send_to_django(update, context)
            else:
                await update.message.reply_text("Send the syllabus file to continue.")
        elif last_action == 'document':
            context.user_data['syllabus_file'] = last_payload['syllabus_file']
            if 'question_image' in context.user_data:
                await self.send_to_django(update, context)
            else:
                await update.message.reply_text("Send the question image to continue.")
        else:
            await update.message.reply_text("Nothing to retry. Please send your files again.")

    def start(self):
        app = ApplicationBuilder().token(self.token).build()

        # Start command handler
        app.add_handler(CommandHandler("start", self.start_handler))
        # Retry command handler
        app.add_handler(CommandHandler("retry", self.retry_handler))
        # Photo handler
        app.add_handler(MessageHandler(filters.PHOTO, self.photo_handler))
        # Document handler
        app.add_handler(MessageHandler(filters.ATTACHMENT, self.document_handler))

        app.run_polling()