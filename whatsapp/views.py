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

            # Configure Gemini
            genai.configure(api_key=settings.GEMINI_API_KEY)
            model = genai.GenerativeModel('gemini-1.5-flash')

            # Read syllabus content
            syllabus_content = syllabus_file.read().decode('utf-8')
            syllabus.content = syllabus_content
            syllabus.save()

            # Process image for Gemini
            img = Image.open(question_image)

            response = model.generate_content([
                "Please extract only the question text from this image. Do not answer it. Return the question in Arabic if it's in Arabic, otherwise return it as-is.",
                img
            ])
            question_text = response.text
            
            # Generate content with both image and text
            response = model.generate_content([
                "استخرج السؤال من هذه الصورة، ثم أجب عليه باللغة العربية بالاعتماد فقط على محتوى المنهج التالي. إذا لم تجد إجابة حرفية، استخدم أقرب محتوى متعلق للإجابة بشكل منطقي. لا تخرج عن نطاق المنهج.\n\n"
                + syllabus_content, img
            ])



            # Extract answer
            answer = response.text

            # Use only this:
            question = Question.objects.create(
                syllabus=syllabus,
                image=question_image,
                extracted_text=question_text.strip(),
                answer=answer.strip()
            )

            return redirect('results', question_id=question.id)

    return render(request, 'upload.html')


def results(request, question_id):
    question = Question.objects.get(id=question_id)
    return render(request, 'results.html', {'question': question})


def history(request):
    questions = Question.objects.all().order_by('-created_at')
    return render(request, 'history.html', {'questions': questions})
