from django.urls import path
from .views import login_view, welcome_admin, welcome_employee, logout_view

urlpatterns = [
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('admin_dashboard/', welcome_admin, name='welcome_admin'),
    path('employee_dashboard/', welcome_employee, name='welcome_employee'),
]
