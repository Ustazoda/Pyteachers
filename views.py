from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from .models import Course, Lesson, Assignment
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
    completed_assignments = Assignment.objects.filter(
        student=request.user,
        lesson__course=course,
        status='checked'
    ).values_list('lesson_id', flat=True)
    
    completed_lessons_ids = list(completed_assignments)
    
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
    lesson = get_object_or_404(Lesson, id=lesson_id, course_id=course_id)
    
    # Vazifa yuklash logikasi
    if request.method == 'POST' and 'assignment_file' in request.FILES or 'assignment_image' in request.FILES:
        image = request.FILES.get('assignment_image')
        file = request.FILES.get('assignment_file')
        comment = request.POST.get('comment')
        
        Assignment.objects.create(
            student=request.user,
            lesson=lesson,
            image=image,
            file=file,
            comment=comment
        )
        messages.success(request, "Vazifa yuborildi!")
        return redirect('courses:lesson_detail', course_id=course_id, lesson_id=lesson_id)

    # Eski yuklangan vazifalarni ko'rsatish
    my_assignments = Assignment.objects.filter(student=request.user, lesson=lesson)
    
    # Dars tugatilganligini tekshirish (YANGI QISM)
    is_completed = UserCourseProgress.objects.filter(student=request.user, lesson=lesson, is_completed=True).exists()

    # Keyingi/Oldingi darsni topish
    next_lesson = Lesson.objects.filter(course_id=course_id, order__gt=lesson.order).first()
    prev_lesson = Lesson.objects.filter(course_id=course_id, order__lt=lesson.order).last()

    return render(request, 'courses/lesson_detail.html', {
        'lesson': lesson,
        'telegram_embed': lesson.get_telegram_embed_data(),
        'my_assignments': my_assignments,
        'next_lesson': next_lesson,
        'prev_lesson': prev_lesson,
        'is_completed': is_completed, # <--- Shablonga yuboramiz
    })

# --- YANGI FUNKSIYA ---
@login_required
def mark_lesson_complete(request, lesson_id):
    lesson = get_object_or_404(Lesson, id=lesson_id)
    
    # Progressni saqlash
    UserCourseProgress.objects.get_or_create(
        student=request.user,
        lesson=lesson,
        defaults={'is_completed': True}
    )
    
    return redirect('courses:lesson_detail', course_id=lesson.course.id, lesson_id=lesson.id)


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