from django.conf import settings
from django.shortcuts import render
from .forms import PDFUploadForm
import requests


def ocr_pdf_view(request):
    extracted_text = None
    error = None

    if request.method == 'POST':
        form = PDFUploadForm(request.POST, request.FILES)
        if form.is_valid():
            file = request.FILES['file']
            if not file.name.endswith('.pdf'):
                error = "Only PDF files are supported."
            else:
                response = requests.post(
                    'https://api.ocr.space/parse/image',
                    files={'file': file},
                    data={
                        'apikey': settings.
                        OCR_API_TOKEN,  # Replace with your OCR.space API key
                        'language': 'auto',
                        'filetype': 'pdf',
                        'OCREngine': 2,
                        'isOverlayRequired': False,
                    })
                result = response.json()
                if result.get('IsErroredOnProcessing'):
                    error = result.get('ErrorMessage', 'Unknown error')
                else:
                    extracted_text = result['ParsedResults'][0]['ParsedText']
    else:
        form = PDFUploadForm()

    return render(request, 'ocr_upload.html', {
        'form': form,
        'text': extracted_text,
        'error': error,
    })
