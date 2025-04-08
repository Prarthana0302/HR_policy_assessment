from django.urls import path
from django.contrib.auth import views as auth_views
from . import views  # Correct Import
from policy_assessment.views import forgot_password, reset_password, take_test ,start_test


urlpatterns = [
    path('', views.login_view, name='login'),  # Default login page
    path('logout/', views.logout_view, name='logout'),

    # Role-Based Dashboards
    path('admin_dashboard/', views.welcome_admin, name='welcome_admin'),
    path('employee_dashboard/', views.welcome_employee, name='welcome_employee'),

    # Employee Actions
    path("take-test/", views.take_test, name="take_test"),
    path('start_test/', views.start_test, name='start_test'),
    path("previous_result/", views.previous_result, name="previous_result"),

    # Admin Actions
    path("manage_tests/", views.manage_tests, name="manage_tests"),
    path("view_results/", views.view_results, name="view_results"),
    path("manage_employees/", views.manage_employees, name="manage_employees"),
     # ✅ Password Reset URLs (Add These)
    path("forgot-password/", forgot_password, name="forgot_password"),
    path("reset-password/<uidb64>/<token>/", reset_password, name="reset_password"),


]
