from django.urls import path
from . import views

urlpatterns = [
    path('', views.intro, name='intro'),
    path('home/', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('events/', views.events, name='events'),
    path('schedule/', views.schedule, name='schedule'),
    path('register/', views.register, name='register'),
    path('register/success/', views.registration_success, name='registration_success'),
    path('team/<int:registration_id>/', views.team_details, name='team_details'),
    path('contact/', views.contact, name='contact'),
    
    # Team Login Routes (Team Access Control)
    path('team/login/', views.team_login, name='team_login'),
    path('team/logout/', views.team_logout, name='team_logout'),
    path('team/dashboard/', views.team_dashboard, name='team_dashboard'),
    
    # Team Management Routes
    path('team/view/<int:team_id>/', views.view_team, name='view_team'),
    path('team/create/<int:event_id>/', views.create_team, name='create_team'),
    path('team/<int:team_id>/add-members/', views.team_add_members, name='team_add_members'),
    path('team/<int:team_id>/add-member/', views.add_team_member, name='add_team_member'),
    path('team/<int:team_id>/member/<int:member_id>/edit/', views.edit_team_member, name='edit_team_member'),
    path('team/<int:team_id>/member/<int:member_id>/remove/', views.remove_team_member, name='remove_team_member'),
    path('team/<int:team_id>/accept-invite/', views.accept_team_invite, name='accept_team_invite'),
    path('team/<int:team_id>/decline-invite/', views.decline_team_invite, name='decline_team_invite'),
    path('registration/<int:registration_id>/add-members/', views.add_team_members_after_registration, name='add_team_members_registration'),
    
    path('login/', views.contact, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('error-logs/', views.view_error_logs, name='view_error_logs'),
    path('manage-competitions/', views.manage_competitions, name='manage_competitions'),
    path('add-competition/', views.add_competition, name='add_competition'),
    path('edit-competition/<int:comp_id>/', views.edit_competition, name='edit_competition'),
    path('delete-competition/<int:comp_id>/', views.delete_competition, name='delete_competition'),
    path('add-admin/', views.add_admin, name='add_admin'),
    path('manage-schedule/', views.manage_schedule, name='manage_schedule'),
    path('add-schedule/', views.add_schedule, name='add_schedule'),
    path('edit-schedule/<int:sched_id>/', views.edit_schedule, name='edit_schedule'),
    path('delete-schedule/<int:sched_id>/', views.delete_schedule, name='delete_schedule'),
    path('view-registrations/', views.view_registrations, name='view_registrations'),
    path('export-registrations/', views.export_registrations, name='export_registrations'),
    path('edit-registration/<int:registration_id>/', views.edit_registration, name='edit_registration'),
    path('delete-registration/<int:registration_id>/', views.delete_registration, name='delete_registration'),
    path('manage-event/', views.manage_event, name='add_event'),
    path('manage-event/<int:event_id>/', views.manage_event, name='edit_event'),
    path('manage-coordinators/', views.manage_coordinators, name='manage_coordinators'),
    path('manage-coordinators/<int:event_id>/', views.manage_coordinators, name='manage_coordinators_for_event'),
    path('add-coordinator/', views.add_coordinator, name='add_coordinator'),
    path('add-coordinator/<int:event_id>/', views.add_coordinator, name='add_coordinator_for_event'),
    path('edit-coordinator/<int:coordinator_id>/', views.edit_coordinator, name='edit_coordinator'),
    path('delete-coordinator/<int:coordinator_id>/', views.delete_coordinator, name='delete_coordinator'),
    path('api/check-registration/', views.check_registration, name='check_registration'),
    path('api/chatbot/', views.chatbot_response, name='chatbot_response'),
    path('send-alert/', views.send_alert, name='send_alert'),
    
    # Chatbot Training Routes (Admin Only)
    path('chatbot/training/', views.chatbot_training, name='chatbot_training'),
    path('chatbot/training/<int:training_id>/edit/', views.edit_training, name='edit_training'),
    path('chatbot/training/<int:training_id>/delete/', views.delete_training, name='delete_training'),
    path('chatbot/training/add/', views.chatbot_training, name='add_training'),
    
    # Test error pages (for development)
    path('test-500/', views.test_500_error, name='test_500'),
    path('test-403/', views.test_403_error, name='test_403'),
    path('test-400/', views.test_400_error, name='test_400'),
    path('migrate/', views.migrate_db, name='migrate_db'),
]

# Error handlers
handler404 = views.error_404
handler500 = views.error_500
handler403 = views.error_403
handler400 = views.error_400