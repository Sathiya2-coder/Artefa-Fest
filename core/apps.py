from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    
    def ready(self):
        """Initialize the app"""
        import os
        if 'VERCEL' in os.environ:
            return
            
        try:
            from .scheduler import start_log_cleaner_scheduler
            start_log_cleaner_scheduler()
        except Exception as e:
            import logging
            logging.getLogger('core').warning(f'Could not start log cleaner scheduler: {str(e)}')
