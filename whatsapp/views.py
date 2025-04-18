from django.shortcuts import render, redirect
from django.conf import settings
import google.generativeai as genai
from .models import Syllabus, Question
from PIL import Image
import pytesseract

from django.core.files.base import ContentFile


def handle_upload(request):
    if request.method == 'POST':
        syllabus_file = request.FILES.get('syllabus')
        question_image = request.FILES.get('question')

        if syllabus_file and question_image:
            # Read file content ONCE
            syllabus_raw = syllabus_file.read()
            syllabus_content = syllabus_raw.decode('utf-8', errors='ignore')

            # Create syllabus object and save content and file
            syllabus = Syllabus.objects.create(content=syllabus_content)
            syllabus.file.save(syllabus_file.name, ContentFile(syllabus_raw))

            # Configure Gemini
            genai.configure(api_key=settings.GEMINI_API_KEY)
            model = genai.GenerativeModel('gemini-1.5-flash')

            # Process image for Gemini
            img = Image.open(question_image)

            # Extract only question
            response = model.generate_content([
                "Please extract only the question text from this image. Do not answer it. Return the question in Arabic if it's in Arabic, otherwise return it as-is.",
                img
            ])
            question_text = response.text.strip()

            # Get custom prompt or use default
            custom_prompt = request.POST.get('prompt', "Extract and answer the question from this image based on the syllabus content")
            
            # Generate answer
            response = model.generate_content([
                custom_prompt + "\n\nSyllabus content:\n" + syllabus_content, 
                img
            ])
            answer = response.text.strip()

            # Save question
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
