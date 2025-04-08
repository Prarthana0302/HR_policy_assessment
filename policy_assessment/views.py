from django.shortcuts import render, redirect
from django.contrib.auth.hashers import check_password
from django.contrib.auth import logout
from policy_assessment.models import User
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_decode
from django.contrib.auth.hashers import make_password
from django.conf import settings
from django.urls import reverse
from django.contrib import messages
from .utils import custom_token_generator

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
        return redirect('login')  # Prevent unauthorized access
    return render(request, "policy_assessment/manage_tests.html")

def view_results(request):
    if request.session.get('role') != 'admin':
        return redirect('login')  # Prevent unauthorized access
    return render(request, "policy_assessment/view_results.html")

def manage_employees(request):
    if request.session.get('role') != 'admin':
        return redirect('login')  # Prevent unauthorized access
    return render(request, "policy_assessment/manage_employees.html")

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
    # Show the welcome/start page
    user_email = request.session.get('user_id')
    user = User.objects.get(email=user_email)
    return render(request, "policy_assessment/start_test.html", {'user_name': user.name})