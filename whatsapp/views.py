import logging
from io import BytesIO
from PIL import Image as PILImage
from PyPDF2 import PdfReader
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
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
        return render(request, 'upload.html', {
            'syllabi': syllabi,
            'error': 'Question image is required'
        })

    genai.configure(api_key=settings.GEMINI_API_KEY)
    model_name = "gemini-2.5-pro-exp-03-25"
    # model_name = "gemini-1.5-flash"
    model = genai.GenerativeModel(model_name)

    question_image = None
    try:
        question_image = PILImage.open(question_image_file)
        # Convert PIL Image to Django InMemoryUploadedFile
        image_io = BytesIO()
        question_image.save(image_io, question_image.format)
        image_file = InMemoryUploadedFile(image_io, None,
                                          question_image_file.name,
                                          question_image_file.content_type,
                                          image_io.tell(), None)
    except Exception as e:
        logger.error(f"Error processing question image: {e}")
        return render(
            request, 'upload.html', {
                'syllabi': syllabi,
                'error': f'Error processing question image: {str(e)}'
            })

    syllabus = None
    syllabus_content = ""

    if syllabus_file:
        try:
            syllabus_content, syllabus_raw = process_syllabus_file(
                syllabus_file)
            syllabus = Syllabus.objects.create(content=syllabus_content)
            syllabus.file.save(syllabus_file.name, ContentFile(syllabus_raw))
        except Exception as e:
            logger.error(f"Error processing uploaded syllabus: {e}")
            return render(
                request, 'upload.html', {
                    'syllabi': syllabi,
                    'error': f'Error processing syllabus file: {str(e)}'
                })
    elif existing_syllabus_id:
        try:
            syllabus = Syllabus.objects.get(id=existing_syllabus_id)
            syllabus_content = syllabus.content
        except Syllabus.DoesNotExist:
            return render(request, 'upload.html', {
                'syllabi': syllabi,
                'error': 'Selected syllabus not found'
            })
    else:
        return render(request, 'upload.html', {
            'syllabi': syllabi,
            'error': 'Please select or upload a syllabus'
        })

    extracted_question_text = ""
    try:
        # Convert uploaded file to PIL Image for Gemini API
        pil_image = PILImage.open(question_image_file)

        # Direct API calls
        question_extraction_response = model.generate_content([
            "Extract only the question text from this image. Do not answer it. Extract exactly as shown, preserving the original language.",
            pil_image
        ])
        extracted_question_text = question_extraction_response.text.strip()
    except Exception as e:
        logger.error(f"Error during question extraction from image: {e}")
        return render(request, 'upload.html', {
            'syllabi': syllabi,
            'error': f'Error extracting question: {str(e)}'
        })

    if not custom_prompt:
        custom_prompt = """
        For the following multiple-choice question, provide the answer in the exact format: "Answer: X) Correct Answer Text", where X is the letter of the correct choice.
        """

    answer_text = ""
    try:
        # Convert uploaded file to PIL Image for Gemini API
        pil_image = PILImage.open(question_image_file)

        answer_response = model.generate_content([
            f"{custom_prompt}\n\nSyllabus content: {syllabus_content}",
            pil_image
        ])
        answer_text = answer_response.text.strip()
    except Exception as e:
        logger.error(f"Error generating answer: {e}")
        return render(request, 'upload.html', {
            'syllabi': syllabi,
            'error': f'Error generating answer: {str(e)}'
        })

    try:
        question = Question.objects.create(
            syllabus=syllabus,
            image=image_file,  # Save the Django file object
            extracted_text=extracted_question_text,
            answer=answer_text,
            prompt=custom_prompt)
        return redirect('results', question_id=question.id)
    except Exception as e:
        logger.error(f"Error saving question to database: {e}")
        return render(request, 'upload.html', {
            'syllabi': syllabi,
            'error': f'Error saving question: {str(e)}'
        })


@csrf_exempt
def api_upload_image_and_syllabus(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST requests are allowed.'}, status=405)

    question_image_file = request.FILES.get('image')
    syllabus_file = request.FILES.get('syllabus')
    custom_prompt = request.POST.get('prompt', 
    """For the following multiple-choice question, provide the answer in the exact format: "Answer: X) Correct Answer Text", where X is the letter of the correct choice.
    """)
    # "Extract and answer the question from this image based on the syllabus content")

    if not question_image_file or not syllabus_file:
        return JsonResponse({'error': 'Both image and syllabus files are required.'}, status=400)

    # Process image
    try:
        question_image = PILImage.open(question_image_file)
        image_io = BytesIO()
        question_image.save(image_io, question_image.format)
        image_file = InMemoryUploadedFile(image_io, None,
                                          question_image_file.name,
                                          question_image_file.content_type,
                                          image_io.tell(), None)
        print(f"Question image processed successfully.")
    except Exception as e:
        logger.error(f"Error processing question image: {e}")
        return JsonResponse({'error': f'Error processing question image: {str(e)}'}, status=400)

    # Process syllabus
    try:
        syllabus_content, syllabus_raw = process_syllabus_file(syllabus_file)
        syllabus = Syllabus.objects.create(content=syllabus_content)
        syllabus.file.save(syllabus_file.name, ContentFile(syllabus_raw))
        print(f"file sssssssssssssssssssssssssssssssssssssss")

    except Exception as e:
        logger.error(f"Error processing syllabus: {e}")
        return JsonResponse({'error': f'Error processing syllabus: {str(e)}'}, status=400)

    # Extract question text
    try:
        pil_image = PILImage.open(question_image_file)
        model_name = "gemini-1.5-flash"
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel(model_name)
        question_extraction_response = model.generate_content([
            "Extract only the question text from this image. Do not answer it. Extract exactly as shown, preserving the original language.",
            pil_image
        ])
        extracted_question_text = question_extraction_response.text.strip()
        print(f"file {extracted_question_text}")

    except Exception as e:
        logger.error(f"Error extracting question: {e}")
        return JsonResponse({'error': f'Error extracting question: {str(e)}'}, status=400)

    # Generate answer
    try:
        pil_image = PILImage.open(question_image_file)
        answer_response = model.generate_content([
            f"{custom_prompt}\n\nSyllabus content: {syllabus_content}",
            pil_image
        ])
        answer_text = answer_response.text.strip()
        print(answer_text, "jjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjj")
        print(answer_text, "jjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjj")
        print(answer_text, "jjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjj")
        print(answer_text, "jjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjj")
        print(answer_text, "jjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjj")
        print(answer_text, "jjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjj")
    except Exception as e:
        logger.error(f"Error generating answer: {e}")
        return JsonResponse({'error': f'Error generating answer: {str(e)}'}, status=400)

    # Save question
    try:
        question = Question.objects.create(
            syllabus=syllabus,
            image=image_file,
            extracted_text=extracted_question_text,
            answer=answer_text,
            prompt=custom_prompt)
        return JsonResponse({'success': True, 'answer': answer_text})
        # return JsonResponse({'success': True, 'question_id': question.id})
    except Exception as e:
        logger.error(f"Error saving question: {e}")
        return JsonResponse({'error': f'Error saving question: {str(e)}'}, status=500)


def results(request, question_id):
    try:
        question = Question.objects.get(id=question_id)
        return render(request, 'results.html', {'question': question})
    except Question.DoesNotExist:
        logger.error(f"Question with ID {question_id} not found.")
        return render(request, 'error.html',
                      {'message': 'Question not found.'})


def history(request):
    questions = Question.objects.all().order_by('-created_at')
    return render(request, 'history.html', {'questions': questions})
