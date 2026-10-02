from django.urls import include, path
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r"events", views.EventViewSet, basename="api-events")
router.register(r"event-sessions", views.EventSessionViewSet, basename="api-event-sessions")
router.register(r"registrations", views.RegistrationViewSet, basename="api-registrations")
router.register(r"subscribers", views.SubscriberViewSet, basename="api-subscribers")
router.register(r"staff", views.SubscriberStaffViewSet, basename="api-staff")

urlpatterns = [
    path("api/", include(router.urls)),
    path("", views.index_view, name="index"),
    path("events/", views.events_view, name="events"),
    path("events/<int:event_id>/", views.event_detail_view, name="event_detail"),
    path("hosts/", views.hosts_view, name="hosts"),
    path("hosts/<slug:slug>/", views.host_profile_view, name="host_detail"),
    path("login-user/", views.login_user_view, name="login_user"),
    path("login-staff/", views.login_staff_view, name="login_staff"),
    path("register-account/", views.register_account_view, name="register_account"),
    path("register-host/", views.register_host_view, name="register_host"),
    path(
        "register-host-pending/",
        views.page,
        {"template_name": "register-host-pending"},
        name="register_host_pending",
    ),
    path("forgot-password/", views.forgot_password_view, name="forgot_password"),
    path("logout/", views.logout_view, name="logout"),
    path("account/", views.account_view, name="account"),
    path("account/registrations/<int:registration_id>/cancel/", views.cancel_registration_view, name="cancel_registration"),
    path("dashboard-staff/", views.dashboard_staff_view, name="dashboard_staff"),
    path("dashboard-staff/invite/", views.dashboard_staff_invite_view, name="dashboard_staff_invite"),
    path("dashboard-staff/<int:staff_id>/toggle/", views.dashboard_staff_toggle_view, name="dashboard_staff_toggle"),
    path(
        "dashboard-organizations/",
        views.dashboard_organizations_view,
        name="dashboard_organizations",
    ),
    path(
        "dashboard-organizations/new/",
        views.dashboard_organization_create_view,
        name="dashboard_organization_create",
    ),
    path(
        "dashboard-organizations/<int:subscriber_id>/update/",
        views.dashboard_organization_update_view,
        name="dashboard_organization_update",
    ),
    path(
        "dashboard-organizations/<int:subscriber_id>/delete/",
        views.dashboard_organization_delete_view,
        name="dashboard_organization_delete",
    ),
    path("dashboard-events/", views.dashboard_events_view, name="dashboard_events"),
    path(
        "dashboard-event-new/",
        views.dashboard_event_new_view,
        name="dashboard_event_new",
    ),
    path("dashboard-events/<int:event_id>/edit/", views.dashboard_event_sessions_view, name="dashboard_event_sessions"),
    path(
        "dashboard-events/<int:event_id>/archive/",
        views.dashboard_event_archive_view,
        name="dashboard_event_archive",
    ),
    path(
        "dashboard-events/<int:event_id>/delete/",
        views.dashboard_event_delete_view,
        name="dashboard_event_delete",
    ),
    path("ai/subscribers/<int:subscriber_id>/suggest-copy/", views.ai_suggest_subscriber_copy_view, name="ai_subscriber_suggest_copy"),
    path("ai/subscribers/<int:subscriber_id>/apply-copy/", views.ai_apply_subscriber_copy_view, name="ai_subscriber_apply_copy"),
    path("ai/events/<int:event_id>/suggest-copy/", views.ai_suggest_event_copy_view, name="ai_event_suggest_copy"),
    path("ai/events/<int:event_id>/apply-copy/", views.ai_apply_event_copy_view, name="ai_event_apply_copy"),
    path("ai/recommendations/", views.ai_index_recommendations_view, name="ai_index_recommendations"),
]
