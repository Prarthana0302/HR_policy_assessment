from django.urls import path
from django.contrib.auth import views as auth_views
from . import views  # Correct Import
from policy_assessment.views import forgot_password, reset_password, take_test ,start_test ,submit_test,manage_employees,add_question,delete_question


urlpatterns = [
    path('', views.login_view, name='login'),  # Default login page
    path('logout/', views.logout_view, name='logout'),
    path('send-invites/', views.send_invites, name='send_invites'),
    path('signup/', views.employee_signup, name='employee_signup'),

    # Role-Based Dashboards
    path('admin_dashboard/', views.welcome_admin, name='welcome_admin'),
    path('employee_dashboard/', views.welcome_employee, name='welcome_employee'),

    # Employee Actions
    path("take-test/", views.take_test, name="take_test"),
    path('start_test/', views.start_test, name='start_test'),
    path('submit_test/', views.submit_test, name='submit_test'),
    path("previous_result/", views.previous_result, name="previous_result"),

    # Admin Actions
    path("manage_tests/", views.manage_tests, name="manage_tests"),
    path('add-question/', views.add_question, name='add_question'),
    path('delete-question/<int:question_id>/', views.delete_question, name='delete_question'),
    path("view_results/", views.view_results, name="view_results"),
    path("manage_employees/", views.manage_employees, name="manage_employees"),
     # ✅ Password Reset URLs (Add These)
    path("forgot-password/", forgot_password, name="forgot_password"),
    path("reset-password/<uidb64>/<token>/", reset_password, name="reset_password"),


]
