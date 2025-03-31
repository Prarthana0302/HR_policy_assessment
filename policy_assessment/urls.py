from django.urls import path
import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('admin_dashboard/', views.welcome_admin, name='welcome_admin'),
    path('employee_dashboard/', views.welcome_employee, name='welcome_employee'),

    path("take_test/", views.take_test, name="take_test"),
    path("previous_result/", views.previous_result, name="previous_result"),

    path("manage_tests/", views.manage_tests, name="manage_tests"),
    path("view_results/", views.view_results, name="view_results"),
    path("manage_employees/", views.manage_employees, name="manage_employees"),
]
