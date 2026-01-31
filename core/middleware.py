"""
Error logging and tracking middleware for ARTIFA FEST
Tracks all HTTP errors and stores them in database and logs
"""

import logging
import json
from django.utils.timezone import now
from django.http import JsonResponse
from .models import ErrorLog

logger = logging.getLogger(__name__)


class ErrorLogMiddleware:
    """Middleware to log all HTTP errors"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        try:
            response = self.get_response(request)
            
            # Log errors (4xx and 5xx)
            if response.status_code >= 400:
                self.log_error(request, response)
                
                # Render custom error pages even when DEBUG=True
                from django.conf import settings
                if settings.DEBUG:
                    return self.render_error_page(request, response)
            
            return response
        except Exception as e:
            # Log exceptions
            logger.error(
                f"Exception: {str(e)}",
                exc_info=True,
                extra={
                    'request_path': request.path,
                    'request_method': request.method,
                    'client_ip': self.get_client_ip(request),
                }
            )
            
            # Try to save to database
            try:
                ErrorLog.objects.create(
                    status_code=500,
                    method=request.method,
                    path=request.path,
                    query_string=request.GET.urlencode() if request.GET else '',
                    client_ip=self.get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', 'Unknown'),
                    error_message=str(e),
                    error_type='Exception',
                )
            except Exception as db_error:
                logger.error(f"Failed to log error to database: {str(db_error)}")
            
            # Re-raise for traceback in DEBUG mode
            from django.conf import settings
            if settings.DEBUG:
                raise e
                
            # Render error page for 500 errors
            from django.shortcuts import render
            return render(request, '500.html', {'error_id': 'unknown'}, status=500)

    
    def log_error(self, request, response):
        """Log HTTP errors to database and file"""
        try:
            error_message = self.get_error_message(response)
            error_type = self.get_error_type(response.status_code)
            
            # Log to file
            logger.error(
                f"{response.status_code} {error_type}: {request.method} {request.path}",
                extra={
                    'status_code': response.status_code,
                    'request_path': request.path,
                    'request_method': request.method,
                    'client_ip': self.get_client_ip(request),
                }
            )
            
            # Save to database
            ErrorLog.objects.create(
                status_code=response.status_code,
                method=request.method,
                path=request.path,
                query_string=request.GET.urlencode() if request.GET else '',
                client_ip=self.get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', 'Unknown'),
                error_message=error_message,
                error_type=error_type,
            )
        except Exception as e:
            logger.error(f"Failed to log error: {str(e)}", exc_info=True)
    
    @staticmethod
    def get_client_ip(request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    @staticmethod
    def get_error_type(status_code):
        """Get error type from status code"""
        error_types = {
            400: 'Bad Request',
            401: 'Unauthorized',
            403: 'Forbidden',
            404: 'Not Found',
            405: 'Method Not Allowed',
            408: 'Request Timeout',
            429: 'Too Many Requests',
            500: 'Internal Server Error',
            502: 'Bad Gateway',
            503: 'Service Unavailable',
            504: 'Gateway Timeout',
        }
        return error_types.get(status_code, 'Unknown Error')
    
    @staticmethod
    def get_error_message(response):
        """Extract error message from response"""
        try:
            if hasattr(response, 'content'):
                return response.content.decode('utf-8')[:500]
        except:
            pass
        return f"HTTP {response.status_code}"    
    @staticmethod
    def render_error_page(request, response):
        """Render custom error pages for DEBUG=True"""
        try:
            from django.shortcuts import render
            
            status_code = response.status_code
            context = {
                'status_code': status_code,
                'request_path': request.path,
            }
            
            template_map = {
                400: '400.html',
                403: '403.html',
                404: '404.html',
                500: '500.html',
            }
            
            template_name = template_map.get(status_code, '404.html')
            return render(request, template_name, context, status=status_code)
        except Exception as e:
            logger.error(f"Error rendering error page: {str(e)}")
            return response