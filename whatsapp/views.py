from django.shortcuts import render, redirect
from django.conf import settings
import google.generativeai as genai
from .models import Syllabus, Question
from PIL import Image
import pytesseract

from django.core.files.base import ContentFile


def handle_upload(request):
    syllabi = Syllabus.objects.all().order_by('-uploaded_at')
    
    if request.method == 'POST':
        syllabus_file = request.FILES.get('syllabus')
        existing_syllabus_id = request.POST.get('existing_syllabus')
        question_image = request.FILES.get('question')

        if not question_image:
            return render(request, 'upload.html', {'syllabi': syllabi, 'error': 'Question image is required'})

        # Configure Gemini first
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Process image
        img = Image.open(question_image)
        
        # Get or create syllabus
        if syllabus_file:
            try:
                syllabus_raw = syllabus_file.read()
                # Check if it's a PDF file
                if syllabus_file.name.lower().endswith('.pdf'):
                    import PyPDF2
                    from io import BytesIO
                    pdf_reader = PyPDF2.PdfReader(BytesIO(syllabus_raw))
                    syllabus_content = ""
                    for page in pdf_reader.pages:
                        syllabus_content += page.extract_text() + "\n"
                else:
                    syllabus_content = syllabus_raw.decode('utf-8', errors='ignore')
                
                syllabus = Syllabus.objects.create(content=syllabus_content)
                syllabus.file.save(syllabus_file.name, ContentFile(syllabus_raw))
            except Exception as e:
                return render(request, 'upload.html', {
                    'syllabi': syllabi,
                    'error': f'Error processing file: {str(e)}'
                })
        elif existing_syllabus_id:
            try:
                syllabus = Syllabus.objects.get(id=existing_syllabus_id)
                syllabus_content = syllabus.content
            except Syllabus.DoesNotExist:
                return render(request, 'upload.html', {'syllabi': syllabi, 'error': 'Selected syllabus not found'})
        else:
            return render(request, 'upload.html', {'syllabi': syllabi, 'error': 'Please select or upload a syllabus'})

        # Get custom prompt
        custom_prompt = request.POST.get('prompt', "Extract and answer the question from this image based on the syllabus content")
        
        # Direct API calls
        question_response = model.generate_content([
            "Extract only the question text from this image. Do not answer it. Extract exactly as shown, preserving the original language.",
            img
        ])
        
        if not custom_prompt:
            custom_prompt = "Please analyze the following question image and provide a detailed answer based on the provided syllabus content. If specific information is not found, use the most relevant content from the syllabus to construct a logical answer."
            
        answer_response = model.generate_content([
            f"{custom_prompt}\n\nSyllabus content:\n{syllabus_content}",
            img
        ])

        # Create question
        question = Question.objects.create(
            syllabus=syllabus,
            image=question_image,
            extracted_text=question_response.text.strip(),
            answer=answer_response.text.strip(),
            prompt=custom_prompt
        )

        return redirect('results', question_id=question.id)

    return render(request, 'upload.html', {'syllabi': syllabi})


def results(request, question_id):
    question = Question.objects.get(id=question_id)
    return render(request, 'results.html', {'question': question})


def history(request):
    questions = Question.objects.all().order_by('-created_at')
    return render(request, 'history.html', {'questions': questions})
