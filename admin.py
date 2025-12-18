from django.contrib import admin
from .models import Course, Lesson, Assignment, QuizItem, UserCourseProgress

class LessonInline(admin.StackedInline):
    model = Lesson
    extra = 1

class QuizItemInline(admin.TabularInline):
    """Darsga viktorinalar qo'shish uchun"""
    model = QuizItem
    extra = 1

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    inlines = [LessonInline]
    list_display = ('title', 'created_at')

@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    inlines = [QuizItemInline]
    list_display = ('title', 'course', 'order', 'has_assignment')
    list_filter = ('course', 'has_assignment')

@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ('student', 'lesson', 'submitted_at', 'status')
    list_filter = ('status', 'lesson')
    search_fields = ('student__username', 'lesson__title')

@admin.register(UserCourseProgress)
class ProgressAdmin(admin.ModelAdmin):
    list_display = ('student', 'lesson', 'is_completed', 'completed_at')
    list_filter = ('is_completed', 'lesson__course')
    search_fields = ('student__username',)


# ============================================
# courses/views.py (TO'LIQ TUZATILGAN)
# ============================================
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from .models import Course, Lesson, Assignment, UserCourseProgress

def is_teacher(user):
    """O'qituvchini tekshirish"""
    return user.is_superuser or user.is_staff


@login_required
def course_list(request):
    """Barcha kurslarni ko'rsatish"""
    courses = Course.objects.prefetch_related('lessons').all()
    return render(request, 'courses/course_list.html', {'courses': courses})


@login_required
def course_detail(request, course_id):
    """Kurs tafsilotlari va darslar ro'yxati"""
    course = get_object_or_404(Course, id=course_id)
    lessons = course.lessons.all().order_by('order')
    
    # Foydalanuvchining tugatgan darslarini topish
    completed_lessons = UserCourseProgress.objects.filter(
        student=request.user,
        lesson__course=course,
        is_completed=True
    ).values_list('lesson_id', flat=True)
    
    completed_lessons_ids = list(completed_lessons)
    
    # Progress hisoblash
    total_lessons = lessons.count()
    completed_count = len(completed_lessons_ids)
    progress_percentage = int((completed_count / total_lessons * 100)) if total_lessons > 0 else 0
    
    # Har bir dars uchun ochiq/yopiqligini aniqlash
    lessons_with_status = []
    prev_completed = False
    
    for lesson in lessons:
        is_completed = lesson.id in completed_lessons_ids
        is_unlocked = (lesson.order == 1) or prev_completed or is_completed
        
        lessons_with_status.append({
            'lesson': lesson,
            'is_completed': is_completed,
            'is_unlocked': is_unlocked,
        })
        
        prev_completed = is_completed
    
    context = {
        'course': course,
        'lessons': lessons,
        'lessons_with_status': lessons_with_status,
        'completed_lessons_ids': completed_lessons_ids,
        'progress_percentage': progress_percentage,
    }
    
    return render(request, 'courses/course_detail.html', context)


@login_required
def lesson_detail(request, course_id, lesson_id):
    """Dars tafsilotlari"""
    lesson = get_object_or_404(Lesson, id=lesson_id, course_id=course_id)
    
    # Vazifa yuklash logikasi
    if request.method == 'POST' and lesson.has_assignment:
        image = request.FILES.get('image')
        file = request.FILES.get('file')
        comment = request.POST.get('comment', '')
        
        if image or file:
            Assignment.objects.create(
                student=request.user,
                lesson=lesson,
                image=image,
                file=file,
                comment=comment
            )
            messages.success(request, "Vazifa muvaffaqiyatli yuborildi!")
            return redirect('courses:lesson_detail', course_id=course_id, lesson_id=lesson_id)
        else:
            messages.error(request, "Iltimos, kamida bitta fayl yoki rasm yuklang!")

    # Talabaning yuklagan vazifalarini olish
    my_assignments = Assignment.objects.filter(
        student=request.user, 
        lesson=lesson
    ).order_by('-submitted_at')
    
    # Dars tugatilganligini tekshirish
    is_completed = UserCourseProgress.objects.filter(
        student=request.user, 
        lesson=lesson, 
        is_completed=True
    ).exists()

    # Keyingi va oldingi darslarni topish
    next_lesson = Lesson.objects.filter(
        course_id=course_id, 
        order__gt=lesson.order
    ).order_by('order').first()
    
    prev_lesson = Lesson.objects.filter(
        course_id=course_id, 
        order__lt=lesson.order
    ).order_by('-order').first()

    context = {
        'lesson': lesson,
        'telegram_embed': lesson.get_telegram_embed_data(),
        'my_assignments': my_assignments,
        'next_lesson': next_lesson,
        'prev_lesson': prev_lesson,
        'is_completed': is_completed,
    }
    
    return render(request, 'courses/lesson_detail.html', context)


@login_required
def mark_lesson_complete(request, lesson_id):
    """Darsni tugatilgan deb belgilash"""
    if request.method == 'POST':
        lesson = get_object_or_404(Lesson, id=lesson_id)
        
        # Progressni saqlash
        UserCourseProgress.objects.get_or_create(
            student=request.user,
            lesson=lesson,
            defaults={'is_completed': True}
        )
        
        messages.success(request, f"'{lesson.title}' darsi tugatildi!")
        return redirect('courses:lesson_detail', course_id=lesson.course.id, lesson_id=lesson.id)
    
    return redirect('courses:course_list')


@user_passes_test(is_teacher)
def teacher_dashboard(request):
    """O'qituvchi paneli"""
    # Statusni o'zgartirish
    if request.method == 'POST':
        assignment_id = request.POST.get('assignment_id')
        new_status = request.POST.get('status')
        feedback = request.POST.get('feedback', '')
        
        if assignment_id and new_status:
            assignment = get_object_or_404(Assignment, id=assignment_id)
            assignment.status = new_status
            assignment.teacher_feedback = feedback
            assignment.save()
            messages.success(request, f"{assignment.student.username}ning vazifasi yangilandi!")
            return redirect('courses:teacher_dashboard')
    
    # Barcha vazifalarni olish
    status_filter = request.GET.get('status', 'all')
    
    assignments = Assignment.objects.select_related(
        'student', 'lesson', 'lesson__course'
    ).all()
    
    if status_filter != 'all':
        assignments = assignments.filter(status=status_filter)
    
    assignments = assignments.order_by('-submitted_at')
    
    # Statistika
    stats = {
        'total': Assignment.objects.count(),
        'new': Assignment.objects.filter(status='new').count(),
        'checked': Assignment.objects.filter(status='checked').count(),
        'rejected': Assignment.objects.filter(status='rejected').count(),
    }
    
    context = {
        'assignments': assignments,
        'status_filter': status_filter,
        'stats': stats,
    }
    
    return render(request, 'courses/teacher_dashboard.html', context)