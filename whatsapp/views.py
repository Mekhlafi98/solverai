from django.shortcuts import render, redirect
from django.conf import settings
import google.generativeai as genai
from .models import Syllabus, Question
from PIL import Image
import pytesseract


def handle_upload(request):
    if request.method == 'POST':
        syllabus_file = request.FILES.get('syllabus')
        question_image = request.FILES.get('question')

        if syllabus_file and question_image:
            # Save syllabus
            syllabus = Syllabus.objects.create(file=syllabus_file)

            # Extract text from image
            img = Image.open(question_image)
            question_text = pytesseract.image_to_string(img)

            # Process with Gemini
            genai.configure(api_key=settings.GEMINI_API_KEY)
            model = genai.GenerativeModel('gemini-2.0-flash')

            # Read syllabus content
            syllabus_content = syllabus_file.read().decode('utf-8')

            prompt = f"""
            Based on this arabic syllabus content: {syllabus_content}
            Answer this question: {question_text}
            """

            response = model.generate_content(prompt)
            answer = response.text

            # Save question and response
            question = Question.objects.create(syllabus=syllabus,
                                               image=question_image,
                                               extracted_text=question_text,
                                               answer=answer)

            return redirect('results', question_id=question.id)

    return render(request, 'upload.html')


def results(request, question_id):
    question = Question.objects.get(id=question_id)
    return render(request, 'results.html', {'question': question})


def history(request):
    questions = Question.objects.all().order_by('-created_at')
    return render(request, 'history.html', {'questions': questions})
