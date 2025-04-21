from django.contrib import admin
from .models import Question, Syllabus, AppSettings

# Register your models here.
admin.site.register(Question)
admin.site.register(Syllabus)
admin.site.register(AppSettings)
