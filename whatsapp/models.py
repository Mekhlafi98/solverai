
from django.db import models
from django.utils import timezone

class Syllabus(models.Model):
    file = models.FileField(upload_to='syllabi/')
    content = models.TextField(blank=True, null=True)
    uploaded_at = models.DateTimeField(default=timezone.now)
    
class Question(models.Model):
    syllabus = models.ForeignKey(Syllabus, on_delete=models.CASCADE)
    image = models.ImageField(upload_to='questions/')
    prompt = models.TextField(default="Extract and answer the question from this image based on the syllabus content")
    extracted_text = models.TextField()
    answer = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Question {self.id} - {self.extracted_text[:50]}"


class AppSettings(models.Model):
    # Prompt Settings
    extraction_prompt = models.TextField(
        default="Please extract only the question text from this image. Do not answer it. Return the question in Arabic if it's in Arabic, otherwise return it as-is."
    )

    answer_generation_prompt = models.TextField(
        default="استخرج السؤال من هذه الصورة، ثم أجب عليه باللغة العربية بالاعتماد فقط على محتوى المنهج التالي. إذا لم تجد إجابة دقيقة، استخدم أقرب محتوى متعلق بالإجابة بطريقة منطقية وضمن نطاق المنهج. حاول إعطاء إجابة مقاربة لأكثر محتوى مرتبط بالسؤال."
    )

    # Model Settings
    gemini_model_name = models.CharField(
        max_length=100,
        default="gemini-1.5-flash"
    )

    # System Settings
    max_questions_to_keep = models.PositiveIntegerField(
        default=100,
        help_text="Maximum number of questions to keep in history (oldest will be deleted)"
    )

    class Meta:
        verbose_name_plural = "Application Settings"

    def save(self, *args, **kwargs):
        # Ensure only one settings instance exists
        self.__class__.objects.exclude(id=self.id).delete()
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        try:
            return cls.objects.get()
        except cls.DoesNotExist:
            return cls.objects.create()
