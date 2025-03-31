from django.urls import path
import policy_assessment.views as views
from policy_assessment.views import (
    login_view,
    logout_view,
    welcome_admin,
    welcome_employee,
    take_test,
    previous_result,
    manage_tests,
    view_results,
    manage_employees
)
urlpatterns = [
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('admin_dashboard/', welcome_admin, name='welcome_admin'),
    path('employee_dashboard/', welcome_employee, name='welcome_employee'),

    path("take_test/", take_test, name="take_test"),
    path("previous_result/", previous_result, name="previous_result"),

    # Admin URLs
    path("manage_tests/", manage_tests, name="manage_tests"),
    path("view_results/", view_results, name="view_results"),
    path("manage_employees/", manage_employees, name="manage_employees")
]
