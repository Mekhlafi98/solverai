from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', views.handle_upload, name='upload'),
    path('api/upload/', views.api_upload_image_and_syllabus, name='api_upload_image_and_syllabus'),
    path('results/<int:question_id>/', views.results, name='results'),
    path('history/', views.history, name='history'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
