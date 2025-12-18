from django.db import models
from django.contrib.auth.models import User
import re

class Course(models.Model):
    title = models.CharField(max_length=200, verbose_name="Kurs nomi")
    description = models.TextField(verbose_name="Kurs haqida")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class Lesson(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='lessons')
    title = models.CharField(max_length=200, verbose_name="Qaysi oy uchun")
    
    # Asosiy video yoki post uchun (ixtiyoriy)
    telegram_url = models.URLField(verbose_name="Telegram Link", blank=True, null=True)
    
    order = models.PositiveIntegerField(default=1, verbose_name="Tartib raqami")
    has_assignment = models.BooleanField(default=False, verbose_name="Vazifa bormi?")
    assignment_text = models.TextField(blank=True, verbose_name="Vazifa sharti")

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.title

    def get_telegram_embed_data(self):
        if self.telegram_url:
            match = re.search(r"t\.me/([^/]+)/(\d+)", self.telegram_url)
            if match:
                return f"{match.group(1)}/{match.group(2)}"
        return None


class QuizItem(models.Model):
    """Darsga viktorina va qo'shimcha postlar qo'shish uchun"""
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='quiz_items')
    telegram_link = models.URLField(verbose_name="Viktorina Linki", help_text="https://t.me/PyTeachers/4")
    order = models.PositiveIntegerField(default=1, verbose_name="Ketma-ketlik")

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.lesson.title} - Quiz {self.order}"

    def get_embed_url(self):
        """Linkdan embed kodini yasaydi"""
        match = re.search(r"t\.me/([^/]+)/(\d+)", self.telegram_link)
        if match:
            return f"{match.group(1)}/{match.group(2)}"
        return None


class UserCourseProgress(models.Model):
    """Foydalanuvchi qaysi darsni tugatganini saqlash"""
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='progress')
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE)
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['student', 'lesson']
        verbose_name = "Foydalanuvchi progressi"
        verbose_name_plural = "Foydalanuvchilar progressi"

    def __str__(self):
        return f"{self.student.username} - {self.lesson.title}"


class Assignment(models.Model):
    """Talabalar vazifalarini saqlash"""
    STATUS_CHOICES = [
        ('new', 'Yangi'),
        ('checked', 'Tekshirildi'),
        ('rejected', 'Rad etildi'),
    ]
    
    student = models.ForeignKey(User, on_delete=models.CASCADE)
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE)
    
    # Talaba yuklaydigan fayllar
    image = models.ImageField(upload_to='assignments/img/', blank=True, null=True, verbose_name="Screenshot")
    file = models.FileField(upload_to='assignments/files/', blank=True, null=True, verbose_name="Kod fayli")
    comment = models.TextField(blank=True, verbose_name="Izoh")
    
    submitted_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    teacher_feedback = models.TextField(blank=True, verbose_name="O'qituvchi fikri")

    class Meta:
        ordering = ['-submitted_at']

    def __str__(self):
        return f"{self.student.username} - {self.lesson.title}"
