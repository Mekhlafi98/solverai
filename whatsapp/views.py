import logging
from io import BytesIO
from PIL import Image as PILImage
from PyPDF2 import PdfReader
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.shortcuts import render, redirect
from .models import Syllabus, Question
import google.generativeai as genai
from typing import Optional

logger = logging.getLogger(__name__)

def extract_text_from_pdf(pdf_file) -> Optional[str]:
    """Extracts text content from a PDF file."""
    try:
        pdf_reader = PdfReader(pdf_file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
        return text
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {e}")
        return None

def process_syllabus_file(syllabus_file):
    """Processes the uploaded syllabus file (PDF or other text)."""
    syllabus_raw = syllabus_file.read()
    if syllabus_file.name.lower().endswith('.pdf'):
        syllabus_content = extract_text_from_pdf(BytesIO(syllabus_raw))
        if syllabus_content is None:
            raise Exception("Failed to extract text from PDF.")
    else:
        syllabus_content = syllabus_raw.decode('utf-8', errors='ignore')
    return syllabus_content, syllabus_raw

def handle_upload(request):
    syllabi = Syllabus.objects.all().order_by('-uploaded_at')

    if request.method != 'POST':
        return render(request, 'upload.html', {'syllabi': syllabi})

    question_image_file = request.FILES.get('question')
    syllabus_file = request.FILES.get('syllabus')
    existing_syllabus_id = request.POST.get('existing_syllabus')
    custom_prompt = request.POST.get(
        'prompt',
        "Extract and answer the question from this image based on the syllabus content"
    )

    if not question_image_file:
        return render(request, 'upload.html', {'syllabi': syllabi, 'error': 'Question image is required'})

    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')

    question_image = None
    try:
        question_image = PILImage.open(question_image_file)
        # Convert PIL Image to Django InMemoryUploadedFile
        image_io = BytesIO()
        question_image.save(image_io, question_image.format)
        image_file = InMemoryUploadedFile(
            image_io,
            None,
            question_image_file.name,
            question_image_file.content_type,
            image_io.tell(),
            None
        )
    except Exception as e:
        logger.error(f"Error processing question image: {e}")
        return render(request, 'upload.html', {'syllabi': syllabi, 'error': f'Error processing question image: {str(e)}'})

    syllabus = None
    syllabus_content = ""

    if syllabus_file:
        try:
            syllabus_content, syllabus_raw = process_syllabus_file(syllabus_file)
            syllabus = Syllabus.objects.create(content=syllabus_content)
            syllabus.file.save(syllabus_file.name, ContentFile(syllabus_raw))
        except Exception as e:
            logger.error(f"Error processing uploaded syllabus: {e}")
            return render(request, 'upload.html', {'syllabi': syllabi, 'error': f'Error processing syllabus file: {str(e)}'})
    elif existing_syllabus_id:
        try:
            syllabus = Syllabus.objects.get(id=existing_syllabus_id)
            syllabus_content = syllabus.content
        except Syllabus.DoesNotExist:
            return render(request, 'upload.html', {'syllabi': syllabi, 'error': 'Selected syllabus not found'})
    else:
        return render(request, 'upload.html', {'syllabi': syllabi, 'error': 'Please select or upload a syllabus'})

    extracted_question_text = ""
    try:
        question_extraction_response = model.generate_content([
            "Extract only the question text from this image. Do not answer it. Extract exactly as shown, preserving the original language.",
            question_image_file  # Pass the Django file object here
        ])
        extracted_question_text = question_extraction_response.text.strip()
    except Exception as e:
        logger.error(f"Error during question extraction from image: {e}")
        return render(request, 'upload.html', {'syllabi': syllabi, 'error': f'Error extracting question: {str(e)}'})

    if not custom_prompt:
        custom_prompt = "Please analyze the following question image and provide a detailed answer based on the provided syllabus content. If specific information is not found, use the most relevant content from the syllabus to construct a logical answer."

    answer_text = ""
    try:
        answer_response = model.generate_content([
            f"{custom_prompt}\n\nSyllabus content: {syllabus_content}",
            question_image_file  # Pass the Django file object here
        ])
        answer_text = answer_response.text.strip()
    except Exception as e:
        logger.error(f"Error generating answer: {e}")
        return render(request, 'upload.html', {'syllabi': syllabi, 'error': f'Error generating answer: {str(e)}'})

    try:
        question = Question.objects.create(
            syllabus=syllabus,
            image=image_file,  # Save the Django file object
            extracted_text=extracted_question_text,
            answer=answer_text,
            prompt=custom_prompt
        )
        return redirect('results', question_id=question.id)
    except Exception as e:
        logger.error(f"Error saving question to database: {e}")
        return render(request, 'upload.html', {'syllabi': syllabi, 'error': f'Error saving question: {str(e)}'})

def results(request, question_id):
    try:
        question = Question.objects.get(id=question_id)
        return render(request, 'results.html', {'question': question})
    except Question.DoesNotExist:
        logger.error(f"Question with ID {question_id} not found.")
        return render(request, 'error.html', {'message': 'Question not found.'})

def history(request):
    questions = Question.objects.all().order_by('-created_at')
    return render(request, 'history.html', {'questions': questions})