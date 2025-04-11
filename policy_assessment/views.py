from django.shortcuts import render, redirect
from django.contrib.auth.hashers import check_password
from django.contrib.auth import logout
from policy_assessment.models import User , Question, Answer, Result
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_decode
from django.contrib.auth.hashers import make_password
from django.conf import settings
from django.urls import reverse
from django.contrib import messages
from django.core.signing import TimestampSigner, BadSignature, SignatureExpired
from .utils import custom_token_generator
from .models import Question

def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')  # Get email from form
        password = request.POST.get('password')  # Get password from form

        try:
            user = User.objects.get(email=email)  # Fetch user from DB
            
            if check_password(password, user.password):  # Verify password
                request.session['user_id'] = user.email  # Store session manually
                request.session['role'] = user.role.strip().lower()  # Normalize role

                print(f"User role detected: {user.role}")  # Debugging

                if request.session['role'] == 'admin':
                    return redirect('welcome_admin')  # Redirect to Admin page
                else:
                    return redirect('welcome_employee')  # Redirect to Employee page
            else:
                return render(request, 'policy_assessment/login.html', {'error': 'Invalid credentials'})

        except User.DoesNotExist:
            return render(request, 'policy_assessment/login.html', {'error': 'Invalid credentials'})

    return render(request, 'policy_assessment/login.html')
# Role-Based Views

def welcome_admin(request):
    if not request.session.get('role'):  # Ensure user is logged in
        return redirect('login')
    if request.session.get('role') != 'admin':
        return redirect('welcome_employee')  # Redirect non-admins
    return render(request, 'policy_assessment/welcome_admin.html')

def welcome_employee(request):
    if not request.session.get('role'):  # Ensure user is logged in
        return redirect('login')
    if request.session.get('role') != 'employee':
        return redirect('welcome_admin')  # Redirect non-employees
    return render(request, 'policy_assessment/welcome_employee.html')

def logout_view(request):
    request.session.flush()  # Clears all session data
    return redirect('login')

# Employee Views

def previous_result(request):
    return render(request, "policy_assessment/previous_result.html")

# Admin Views
def manage_tests(request):
    if request.session.get('role') != 'admin':
        return redirect('login')

    questions = Question.objects.all()
    return render(request, 'policy_assessment/manage_tests.html', {
        'questions': questions
    })

def add_question(request):
    if request.method == 'POST':
        question_text = request.POST.get('question_text')
        option_a = request.POST.get('option_a')
        option_b = request.POST.get('option_b')
        option_c = request.POST.get('option_c')
        option_d = request.POST.get('option_d')
        correct_option = request.POST.get('correct_option')

        Question.objects.create(
            question_text=question_text,
            option_a=option_a,
            option_b=option_b,
            option_c=option_c,
            option_d=option_d,
            correct_option=correct_option
        )

        return redirect('manage_tests')
    return redirect('manage_tests')

def delete_question(request, question_id):
    if request.session.get('role') != 'admin':
        return redirect('login')

    Question.objects.filter(id=question_id).delete()
    return redirect('manage_tests')

def view_results(request):
    if request.session.get('role') != 'admin':
        return redirect('login')  # Prevent unauthorized access
    return render(request, "policy_assessment/view_results.html")

def manage_employees(request):
    if request.session.get('role') != 'admin':
        return redirect('login')

    message = ""
    error = ""

    if request.method == "POST":
        action = request.POST.get("action")
        email = request.POST.get("email")

        if action == "add":
            name = request.POST.get("name")
            password = request.POST.get("password")

            if User.objects.filter(email=email).exists():
                error = "User with this email already exists."
            else:
                User.objects.create(
                    email=email,
                    name=name,
                    role='employee',
                    password=make_password(password)
                )
                message = "Employee added successfully."

        elif action == "delete":
            try:
                user = User.objects.get(email=email)
                user.delete()
                message = "Employee deleted successfully."
            except User.DoesNotExist:
                error = "User does not exist."

    employees = User.objects.filter(role='employee')
    return render(request, "policy_assessment/manage_employees.html", {
        'employees': employees,
        'message': message,
        'error': error
    })

def forgot_password(request):
    if request.method == "POST":
        email = request.POST.get("email")
        try:
            user = User.objects.get(email=email)
            token = custom_token_generator.make_token(user)  # ✅ Use custom token
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            reset_url = request.build_absolute_uri(f"/reset-password/{uid}/{token}/")

            # Send reset email
            send_mail(
                "Password Reset Request",
                f"Click the link to reset your password: {reset_url}",
                "admin@example.com",
                [email],
                fail_silently=False,
            )

            return render(request, "policy_assessment/forgot_password.html", {"message": "Password reset email sent!"})

        except User.DoesNotExist:
            return render(request, "policy_assessment/forgot_password.html", {"error": "No user with that email found."})

    return render(request, "policy_assessment/forgot_password.html")

def reset_password(request, uidb64, token):
    try:
        # Decode the base64-encoded email
        email = urlsafe_base64_decode(uidb64).decode()
        user = User.objects.get(email=email)

        # Check if the token is valid
        if not custom_token_generator.check_token(user, token):
            messages.error(request, "The password reset link is invalid or expired.")
            return render(request, "policy_assessment/reset_password.html", {"valid": False}) 

        if request.method == "POST":
            new_password = request.POST.get("password")

            # Hash the password before saving
            user.password = make_password(new_password)
            user.save()

            messages.success(request, "Your password has been reset successfully!")
            return redirect("login")

        return render(request, "policy_assessment/reset_password.html", {"valid": True})

    except (User.DoesNotExist, TypeError, ValueError, OverflowError):
        messages.error(request, "Invalid reset link.")
        return render(request, "policy_assessment/reset_password.html", {"valid": False})
    
def take_test(request):
    # Show the instructions first
    return render(request, "policy_assessment/instructions.html")


def start_test(request):
    user_email = request.session.get('user_id')
    user = User.objects.get(email=user_email)
    questions = Question.objects.all()
    return render(request, "policy_assessment/start_test.html", {
        'user_name': user.name,
        'questions': questions
    })

def submit_test(request):
    if request.method == "POST":
        user = User.objects.get(email=request.session.get('user_id'))
        total_questions = Question.objects.count()
        correct_answers = 0
        total_score = 0

        for q in Question.objects.all():
            selected = request.POST.get(f'question_{q.id}')
            is_correct = selected == q.correct_option

            if selected:  # Only evaluate if answered
                if is_correct:
                    correct_answers += 1
                    total_score += 4  # +4 for correct
                else:
                    total_score -= 1  # -1 for incorrect

                Answer.objects.create(
                    user=user,
                    question=q,
                    selected_option=selected,
                    is_correct=is_correct
                )

        max_score = total_questions * 4
        percentage = (total_score / max_score) * 100 if max_score > 0 else 0

        Result.objects.create(email=user, result_percentage=percentage)

        return redirect("previous_result")
    

PENDING_EMPLOYEES = [
    {'name': 'Parthana', 'email': 'prarthana.j@translab.io'},
    {'name': 'Jayesh', 'email': 'jayesh.d@translab.io'},
   
]

signer = TimestampSigner()

def send_invites(request):
    if request.method == 'POST':
        for employee in PENDING_EMPLOYEES:
            email = employee['email']
            name = employee['name']
            token = signer.sign(email)  # Generates a secure signed token
            signup_url = request.build_absolute_uri(
                reverse('employee_signup') + f'?token={token}&name={name.replace(" ", "+")}'
            )
            subject = 'Complete Your Registration'
            message = f'Hi {name},\n\nPlease complete your signup by clicking this link:\n\n{signup_url}'
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [email])
        return render(request, 'policy_assessment/manage_employees.html', {
            'message': 'Invitations sent successfully.'
        })

def employee_signup(request):
    if request.method == "POST":
        email = request.POST.get("email")
        name = request.POST.get("name")
        password = request.POST.get("password")

        if User.objects.filter(email=email).exists():
            messages.error(request, "An account with this email already exists.")
            return redirect("employee_signup")  # or wherever your form is rendered

        user = User(email=email, name=name, password=make_password(password), role='employee')
        user.save()

        messages.success(request, "Account created successfully! Please log in.")
        return redirect("login")

    return render(request, "policy_assessment/signup.html")
