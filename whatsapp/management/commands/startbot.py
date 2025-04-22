from django.core.management.base import BaseCommand
from whatsapp.telegram_bot import TelegramBot  # Update with your app name
from django.conf import settings

class Command(BaseCommand):
    help = 'Start the Telegram bot'

    def handle(self, *args, **options):
        bot = TelegramBot(token=settings.TELEGRAM_BOT_TOKEN)  # Pass the token here
        bot.start()
