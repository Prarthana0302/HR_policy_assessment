from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from .models import CustomUser

def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            if user.role == 'admin':
                return redirect('welcome_admin')
            else:
                return redirect('welcome_employee')
        else:
            return render(request, 'policy_assessment/login.html', {'error': 'Invalid credentials'})
    return render(request, 'policy_assessment/login.html')

@login_required
def welcome_admin(request):
    return render(request, 'policy_assessment/welcome_admin.html')

@login_required
def welcome_employee(request):
    return render(request, 'policy_assessment/welcome_employee.html')

def logout_view(request):
    logout(request)
    return redirect('login')
