from django.urls import path
from .views import ocr_pdf_view

urlpatterns = [
    path('', ocr_pdf_view, name='upload_pdf'),
]
