
from django.db import models
from django.utils import timezone

class Syllabus(models.Model):
    file = models.FileField(upload_to='syllabi/')
    uploaded_at = models.DateTimeField(default=timezone.now)
    
class Question(models.Model):
    syllabus = models.ForeignKey(Syllabus, on_delete=models.CASCADE)
    image = models.ImageField(upload_to='questions/')
    extracted_text = models.TextField()
    answer = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)
