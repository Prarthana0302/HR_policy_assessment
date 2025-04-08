from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('policy_assessment.urls')),  # This should be here, not in `HR_policy_assessment/urls.py`
]
