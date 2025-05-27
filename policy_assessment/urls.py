from django.urls import path
from policy_assessment import views

urlpatterns = [
    path('', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('welcome_admin/', views.welcome_admin, name='welcome_admin'),
    path('welcome_employee/', views.welcome_employee, name='welcome_employee'),
    path('previous_result/', views.previous_result, name='previous_result'),
    path('manage_tests/', views.manage_tests, name='manage_tests'),
    path('delete_document/<str:filename>/', views.delete_document, name='delete_document'),
    path('view_results/', views.view_results, name='view_results'),
    path('delete-result/<int:result_id>/', views.delete_result, name='delete_result'),
    path('manage_employees/', views.manage_employees, name='manage_employees'),
    path('forgot_password/', views.forgot_password, name='forgot_password'),
    path('reset-password/<str:uidb64>/<str:token>/', views.reset_password, name='reset_password'),
    path('take_test/', views.take_test, name='take_test'),
    path('start_test/', views.start_test, name='start_test'),
    path('submit_test/', views.submit_test, name='submit_test'),
    path('acknowledge_policy/<str:policy_name>/', views.acknowledge_policy, name='acknowledge_policy'),
    path('send_invites/', views.send_invites, name='send_invites'),
    path('employee_signup/', views.employee_signup, name='employee_signup'),
    path('admin_policy_documents/', views.admin_policy_documents, name='admin_policy_documents'),
    path('employee_policy_documents/', views.employee_policy_documents, name='employee_policy_documents'),
    path('view_policy/<str:filename>/', views.view_policy, name='view_policy'),
    path('acknowledge_and_start_test/<str:filename>/', views.acknowledge_and_start_test, name='acknowledge_and_start_test'),
    path('view_acknowledgements/', views.view_acknowledgements, name='view_acknowledgements'),  # New URL
]