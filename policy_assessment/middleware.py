# policy_assessment/middleware.py

from django.http import HttpResponse
from django.utils.deprecation import MiddlewareMixin

class AllowFrameOptions(MiddlewareMixin):
    def process_response(self, request, response):
        response['X-Frame-Options'] = 'ALLOWALL'
        return response
