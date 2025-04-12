
from flask import Flask, request
import requests
from PIL import Image
import pytesseract
from io import BytesIO
from twilio.twiml.messaging_response import MessagingResponse
import openai

app = Flask(__name__)
openai.api_key = 'your_openai_api_key'  # You'll need to set this using Replit Secrets

@app.route("/whatsapp", methods=['POST'])
def whatsapp():
    media_url = request.form.get('MediaUrl0')
    sender = request.form.get('From')

    if media_url:
        image = requests.get(media_url).content
        img = Image.open(BytesIO(image))
        question = pytesseract.image_to_string(img)

        print("Extracted Text:", question)

        answer = ask_gpt(question)

        resp = MessagingResponse()
        resp.message(answer)
        return str(resp)

    return "No image found"

def ask_gpt(question):
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": question}]
    )
    return response['choices'][0]['message']['content']

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
