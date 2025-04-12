
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
import requests
from PIL import Image
import pytesseract
from io import BytesIO
from twilio.twiml.messaging_response import MessagingResponse
import openai

openai.api_key = 'your_openai_api_key'  # You'll need to set this using Replit Secrets

@csrf_exempt
def whatsapp_webhook(request):
    if request.method == 'POST':
        media_url = request.POST.get('MediaUrl0')
        sender = request.POST.get('From')

        if media_url:
            image = requests.get(media_url).content
            img = Image.open(BytesIO(image))
            question = pytesseract.image_to_string(img)

            print("Extracted Text:", question)
            answer = ask_gpt(question)

            resp = MessagingResponse()
            resp.message(answer)
            return HttpResponse(str(resp))

    return HttpResponse("No image found")

def ask_gpt(question):
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": question}]
    )
    return response['choices'][0]['message']['content']
