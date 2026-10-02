from datetime import datetime, time

from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render
from django.db.models import Count, Q
from django.urls import reverse
from django.utils import timezone
from django.contrib import messages
from django.shortcuts import redirect
from django.utils.text import slugify
from django.contrib.auth.hashers import check_password, identify_hasher, make_password
from django.contrib.auth import logout as django_logout
from django.conf import settings
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import BasePermission
from rest_framework.response import Response

from pydantic import BaseModel, Field
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

from .models import (
    AppUser,
    Category,
    Event,
    EventSession,
    Registration,
    RegistrationSession,
    Subscriber,
    SubscriberOfficialLink,
    SubscriberStaff,
)
from .serializers import (
    EventSerializer,
    EventSessionSerializer,
    RegistrationSerializer,
    SubscriberSerializer,
    SubscriberStaffSerializer,
)


class SubscriberCopySuggestion(BaseModel):
    tagline: str = Field(description="Short lead paragraph / tagline")
    description: str = Field(description="About us paragraph")


class SubscriberCopySuggestions(BaseModel):
    suggestions: list[SubscriberCopySuggestion] = Field(description="List of copy suggestions")


class EventCopySuggestion(BaseModel):
    tagline: str = Field(description="Short tagline / lead sentence")
    description: str = Field(description="Full event description")
    bullets: list[str] = Field(description="Highlight bullets (one per line)")


class EventCopySuggestions(BaseModel):
    suggestions: list[EventCopySuggestion] = Field(description="List of event copy suggestions")


class IndexRecommendation(BaseModel):
    event_id: int = Field(description="Event primary key")
    reason: str = Field(description="Short personalised reason (one line)")


class IndexRecommendations(BaseModel):
    recommendations: list[IndexRecommendation] = Field(description="List of recommendations")


def _llm():
    if not getattr(settings, "OPENAI_API_KEY", ""):
        return None
    return ChatOpenAI(api_key=settings.OPENAI_API_KEY, model="gpt-5.4-mini", temperature=0.7)


def ai_suggest_subscriber_copy_view(request, subscriber_id):
    _, denied = _require_admin_membership(request)
    if denied:
        return denied
    if request.method != "POST":
        return redirect("dashboard_organizations")
    if not getattr(request, "htmx", False):
        return redirect("dashboard_organizations")

    subscriber = get_object_or_404(Subscriber, pk=subscriber_id)
    llm = _llm()
    if not llm:
        return render(
            request,
            "partials/_ai_suggestions_list.html",
            {"error": "OPENAI_API_KEY is not configured on the server.", "suggestions": [], "apply_url": "", "target_id": "uq-ai-subscriber-suggestions"},
        )

    parser = JsonOutputParser(pydantic_object=SubscriberCopySuggestions)
    prompt = PromptTemplate(
        template=(
            "You write copy for university host organisation profiles.\n"
            "Generate 4 alternative taglines (1 sentence) and matching 1-paragraph 'About us' descriptions.\n"
            "Keep it professional, friendly, and suitable for students.\n\n"
            "Organisation name: {name}\n"
            "Website: {website}\n"
            "Current tagline: {tagline}\n"
            "Current description: {description}\n\n"
            "{format_instructions}"
        ),
        input_variables=["name", "website", "tagline", "description"],
        partial_variables={"format_instructions": parser.get_format_instructions()},
    )
    chain = prompt | llm | parser
    try:
        result = chain.invoke(
            {
                "name": subscriber.name,
                "website": subscriber.website_url or "",
                "tagline": subscriber.tagline or "",
                "description": subscriber.description or "",
            }
        )
        suggestions = result.get("suggestions", [])
    except Exception as e:
        return render(
            request,
            "partials/_ai_suggestions_list.html",
            {"error": f"Could not generate suggestions: {e}", "suggestions": [], "apply_url": "", "target_id": "uq-ai-subscriber-suggestions"},
        )

    ui_suggestions = []
    for s in suggestions[:6]:
        ui_suggestions.append(
            {
                "title": s.get("tagline", "")[:160],
                "subtitle": "Tagline + About us",
                "body": (s.get("description", "") or "").strip()[:500],
                "hidden": {"tagline": s.get("tagline", ""), "description": s.get("description", "")},
            }
        )

    return render(
        request,
        "partials/_ai_suggestions_list.html",
        {"suggestions": ui_suggestions, "apply_url": reverse("ai_subscriber_apply_copy", args=[subscriber.id]), "target_id": "uq-ai-subscriber-suggestions"},
    )


def ai_apply_subscriber_copy_view(request, subscriber_id):
    _, denied = _require_admin_membership(request)
    if denied:
        return denied
    if request.method != "POST":
        return redirect("dashboard_organizations")
    if not getattr(request, "htmx", False):
        return redirect("dashboard_organizations")

    subscriber = get_object_or_404(Subscriber, pk=subscriber_id)
    tagline = (request.POST.get("tagline") or "").strip()
    description = (request.POST.get("description") or "").strip()
    if tagline:
        subscriber.tagline = tagline
    if description:
        subscriber.description = description
    subscriber.save(update_fields=["tagline", "description"])
    return render(
        request,
        "partials/_ai_apply_subscriber_oob.html",
        {"target_id": "uq-ai-subscriber-suggestions", "tagline": subscriber.tagline, "description": subscriber.description},
    )


def ai_suggest_event_copy_view(request, event_id):
    context, response = _staff_session_context(request)
    if response:
        return response
    if request.method != "POST":
        return redirect("dashboard_event_sessions", event_id=event_id)
    if not getattr(request, "htmx", False):
        return redirect("dashboard_event_sessions", event_id=event_id)

    event = get_object_or_404(Event, pk=event_id, subscriber=context["dashboard_current_subscriber"])
    llm = _llm()
    if not llm:
        return render(
            request,
            "partials/_ai_suggestions_list.html",
            {"error": "OPENAI_API_KEY is not configured on the server.", "suggestions": [], "apply_url": "", "target_id": "uq-ai-event-suggestions"},
        )

    parser = JsonOutputParser(pydantic_object=EventCopySuggestions)
    prompt = PromptTemplate(
        template=(
            "You write event listings for university students.\n"
            "Generate 3 alternative sets of copy for this event: a tagline (<= 140 chars), a full description (2-4 short paragraphs), "
            "and 3-5 highlight bullets.\n"
            "Keep it accurate and avoid inventing specific dates/locations that aren't provided.\n\n"
            "Event title: {title}\n"
            "Host organisation: {host}\n"
            "When: {when}\n"
            "Where: {where}\n"
            "Current tagline: {tagline}\n"
            "Current description: {description}\n"
            "Current bullets: {bullets}\n\n"
            "{format_instructions}"
        ),
        input_variables=["title", "host", "when", "where", "tagline", "description", "bullets"],
        partial_variables={"format_instructions": parser.get_format_instructions()},
    )
    chain = prompt | llm | parser
    when = event.time_summary or (event.start_at.isoformat() if event.start_at else "")
    where = event.venue_display or (event.venue.name if event.venue else "") or ("Online" if event.is_online else "")
    try:
        result = chain.invoke(
            {
                "title": event.title,
                "host": event.subscriber.name if event.subscriber else "",
                "when": when,
                "where": where,
                "tagline": event.tagline or "",
                "description": event.description or "",
                "bullets": event.highlight_bullets or "",
            }
        )
        suggestions = result.get("suggestions", [])
    except Exception as e:
        return render(
            request,
            "partials/_ai_suggestions_list.html",
            {"error": f"Could not generate suggestions: {e}", "suggestions": [], "apply_url": "", "target_id": "uq-ai-event-suggestions"},
        )

    ui_suggestions = []
    for s in suggestions[:6]:
        bullets = s.get("bullets", []) or []
        bullet_text = "\n".join([b.strip() for b in bullets if b and str(b).strip()])
        ui_suggestions.append(
            {
                "title": s.get("tagline", "")[:160],
                "subtitle": "Tagline + description + bullets",
                "body": (s.get("description", "") or "").strip()[:700],
                "hidden": {"tagline": s.get("tagline", ""), "description": s.get("description", ""), "bullets": bullet_text},
            }
        )

    return render(
        request,
        "partials/_ai_suggestions_list.html",
        {"suggestions": ui_suggestions, "apply_url": reverse("ai_event_apply_copy", args=[event.id]), "target_id": "uq-ai-event-suggestions"},
    )


def ai_apply_event_copy_view(request, event_id):
    context, response = _staff_session_context(request)
    if response:
        return response
    if request.method != "POST":
        return redirect("dashboard_event_sessions", event_id=event_id)
    if not getattr(request, "htmx", False):
        return redirect("dashboard_event_sessions", event_id=event_id)

    event = get_object_or_404(Event, pk=event_id, subscriber=context["dashboard_current_subscriber"])
    tagline = (request.POST.get("tagline") or "").strip()
    description = (request.POST.get("description") or "").strip()
    bullets = (request.POST.get("bullets") or "").strip()
    changed_fields = []
    if tagline:
        event.tagline = tagline
        changed_fields.append("tagline")
    if description:
        event.description = description
        changed_fields.append("description")
    if bullets:
        event.highlight_bullets = bullets
        changed_fields.append("highlight_bullets")
    if changed_fields:
        event.save(update_fields=changed_fields + ["updated_at"])
    return render(
        request,
        "partials/_ai_apply_event_oob.html",
        {"target_id": "uq-ai-event-suggestions", "tagline": event.tagline, "description": event.description, "bullets": event.highlight_bullets},
    )


def ai_index_recommendations_view(request):
    if request.method != "POST":
        return redirect("index")
    if not getattr(request, "htmx", False):
        return redirect("index")

    _bootstrap_session_from_django_user(request)
    user_id = request.session.get("app_user_id")

    # Candidate pool: upcoming public events
    now = timezone.now()
    candidates_qs = list(_public_events().filter(start_at__gte=now).order_by("start_at")[:30])

    # Past signal: the user's confirmed registrations (titles + categories only)
    past_titles = []
    past_categories = []
    signals = []
    if user_id:
        past_regs = (
            Registration.objects.select_related("event", "event__category")
            .filter(user_id=user_id, status=Registration.Status.CONFIRMED)
            .order_by("-created_at")[:10]
        )
        for reg in past_regs:
            if reg.event:
                past_titles.append(reg.event.title)
                if reg.event.category:
                    past_categories.append(reg.event.category.name)
        if past_categories:
            signals.append(f"Past categories: {', '.join(sorted(set(past_categories))[:3])}")
        if past_titles:
            signals.append(f"Past events: {', '.join(past_titles[:2])}")

    if not candidates_qs:
        return render(request, "partials/_ai_index_recommendations.html", {"recs": [], "signals": signals, "error": "No upcoming events to recommend yet."})

    llm = _llm()
    if not llm:
        # Fallback: top 3 upcoming
        recs = [{"event": e, "reason": "Upcoming on campus"} for e in candidates_qs[:3]]
        return render(request, "partials/_ai_index_recommendations.html", {"recs": recs, "signals": signals, "error": None})

    # Build lightweight candidate list for prompt
    candidate_lines = []
    for e in candidates_qs:
        category = e.category.name if e.category else "General"
        host = e.subscriber.name if e.subscriber else "Unknown host"
        when = e.start_at.strftime("%Y-%m-%d") if e.start_at else ""
        where = "Online" if e.is_online else (e.venue_display or (e.venue.name if e.venue else "TBA"))
        candidate_lines.append(f"- id={e.id} | {e.title} | {category} | {host} | {when} | {where}")

    parser = JsonOutputParser(pydantic_object=IndexRecommendations)
    prompt = PromptTemplate(
        template=(
            "You are an event recommendation assistant for university students.\n"
            "Choose exactly 3 events from the candidate list that best match the user's past registrations.\n"
            "Return a short reason for each (<= 80 characters). Do not mention private data.\n\n"
            "User past registrations (event titles): {past_titles}\n"
            "User past categories: {past_categories}\n\n"
            "Candidate events:\n"
            "{candidates}\n\n"
            "{format_instructions}"
        ),
        input_variables=["past_titles", "past_categories", "candidates"],
        partial_variables={"format_instructions": parser.get_format_instructions()},
    )
    chain = prompt | llm | parser
    try:
        result = chain.invoke(
            {
                "past_titles": ", ".join(past_titles) if past_titles else "None",
                "past_categories": ", ".join(sorted(set(past_categories))) if past_categories else "None",
                "candidates": "\n".join(candidate_lines),
            }
        )
        rec_items = result.get("recommendations", []) or []
    except Exception:
        rec_items = []

    # Map back to event objects; keep stable fallback if model returns nothing/invalid
    by_id = {e.id: e for e in candidates_qs}
    recs = []
    used = set()
    for item in rec_items:
        try:
            eid = int(item.get("event_id"))
        except Exception:
            continue
        if eid in used or eid not in by_id:
            continue
        used.add(eid)
        reason = (item.get("reason") or "Recommended for you").strip()[:90]
        recs.append({"event": by_id[eid], "reason": reason})
        if len(recs) >= 3:
            break

    if not recs:
        recs = [{"event": e, "reason": "Upcoming on campus"} for e in candidates_qs[:3]]

    return render(request, "partials/_ai_index_recommendations.html", {"recs": recs, "signals": signals, "error": None})


class HasAppSessionOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        return bool(request.session.get("app_user_id"))


class EventViewSet(viewsets.ModelViewSet):
    serializer_class = EventSerializer
    permission_classes = [HasAppSessionOrReadOnly]

    def get_queryset(self):
        queryset = Event.objects.select_related("subscriber", "venue", "category").prefetch_related("sessions")
        membership = _staff_membership_for_request(self.request)
        if membership:
            queryset = queryset.filter(subscriber=membership.subscriber)
        else:
            queryset = queryset.filter(status=Event.Status.PUBLISHED, subscriber__status=Subscriber.Status.ACTIVE)
        subscriber_id = self.request.query_params.get("subscriber_id")
        if subscriber_id:
            queryset = queryset.filter(subscriber_id=subscriber_id)
        return queryset.order_by("start_at", "created_at")

    def perform_create(self, serializer):
        membership = _staff_membership_for_request(self.request)
        if not membership:
            raise PermissionDenied("Staff access is required to create events.")
        serializer.save(subscriber=membership.subscriber, created_by=membership.user)


class EventSessionViewSet(viewsets.ModelViewSet):
    serializer_class = EventSessionSerializer
    permission_classes = [HasAppSessionOrReadOnly]

    def get_queryset(self):
        queryset = EventSession.objects.select_related("event", "event__subscriber")
        membership = _staff_membership_for_request(self.request)
        if membership:
            queryset = queryset.filter(event__subscriber=membership.subscriber)
        else:
            queryset = queryset.filter(event__status=Event.Status.PUBLISHED, event__subscriber__status=Subscriber.Status.ACTIVE)
        event_id = self.request.query_params.get("event_id")
        if event_id:
            queryset = queryset.filter(event_id=event_id)
        return queryset.order_by("event_id", "order_index", "start_at")


class RegistrationViewSet(viewsets.ModelViewSet):
    serializer_class = RegistrationSerializer
    permission_classes = [HasAppSessionOrReadOnly]

    def perform_create(self, serializer):
        user_id = self.request.session.get("app_user_id")
        if not user_id:
            raise PermissionDenied("Sign in is required to create a registration.")
        serializer.save(user_id=user_id, status=Registration.Status.CONFIRMED)

    def get_queryset(self):
        queryset = Registration.objects.select_related("event", "user").prefetch_related("registration_sessions__event_session")
        membership = _staff_membership_for_request(self.request)
        if membership:
            return queryset.filter(event__subscriber=membership.subscriber).order_by("-created_at")
        user_id = self.request.session.get("app_user_id")
        if user_id:
            return queryset.filter(user_id=user_id).order_by("-created_at")
        return queryset.none()

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        registration = self.get_object()
        user_id = request.session.get("app_user_id")
        membership = _staff_membership_for_request(request)
        if not membership and registration.user_id != user_id:
            return Response({"detail": "Not allowed."}, status=status.HTTP_403_FORBIDDEN)
        registration.status = Registration.Status.CANCELLED
        registration.save(update_fields=["status", "updated_at"])
        return Response(self.get_serializer(registration).data)


class SubscriberViewSet(viewsets.ModelViewSet):
    serializer_class = SubscriberSerializer
    permission_classes = [HasAppSessionOrReadOnly]

    def get_queryset(self):
        queryset = Subscriber.objects.prefetch_related("official_links", "staff_memberships")
        membership = _staff_membership_for_request(self.request)
        if membership:
            return queryset.filter(pk=membership.subscriber_id)
        return queryset.filter(status=Subscriber.Status.ACTIVE)

    def perform_create(self, serializer):
        membership = _staff_membership_for_request(self.request)
        if not membership or membership.role != SubscriberStaff.Role.ADMIN:
            raise PermissionDenied("Admin staff access is required.")
        serializer.save()

    def perform_update(self, serializer):
        membership = _staff_membership_for_request(self.request)
        if not membership or membership.role != SubscriberStaff.Role.ADMIN:
            raise PermissionDenied("Admin staff access is required.")
        serializer.save()

    def perform_destroy(self, instance):
        membership = _staff_membership_for_request(self.request)
        if not membership or membership.role != SubscriberStaff.Role.ADMIN:
            raise PermissionDenied("Admin staff access is required.")
        instance.status = Subscriber.Status.SUSPENDED
        instance.suspended_at = timezone.now()
        instance.save(update_fields=["status", "suspended_at"])


def _subscriber_has_other_active_admin(*, subscriber_id, exclude_staff_pk):
    return (
        SubscriberStaff.objects.filter(
            subscriber_id=subscriber_id,
            role=SubscriberStaff.Role.ADMIN,
            is_active=True,
        )
        .exclude(pk=exclude_staff_pk)
        .exists()
    )


class SubscriberStaffViewSet(viewsets.ModelViewSet):
    serializer_class = SubscriberStaffSerializer
    permission_classes = [HasAppSessionOrReadOnly]

    def get_queryset(self):
        membership = _staff_membership_for_request(self.request)
        if not membership:
            return SubscriberStaff.objects.none()
        return (
            SubscriberStaff.objects.select_related("user", "subscriber")
            .filter(subscriber=membership.subscriber)
            .order_by("-role", "user__username")
        )

    def create(self, request, *args, **kwargs):
        membership = _staff_membership_for_request(request)
        if not membership:
            return Response({"detail": "Staff access is required."}, status=status.HTTP_403_FORBIDDEN)
        if membership.role != SubscriberStaff.Role.ADMIN:
            return Response({"detail": "Only admins can invite staff."}, status=status.HTTP_403_FORBIDDEN)
        email = (request.data.get("email") or "").strip().lower()
        name = (request.data.get("name") or "").strip()
        if not email:
            return Response({"email": ["This field is required."]}, status=status.HTTP_400_BAD_REQUEST)
        user, created = AppUser.objects.get_or_create(
            email=email,
            defaults={
                "username": name or _unique_username(email),
                "password_hash": make_password("changeme123"),
                "is_active": True,
                "is_superuser": False,
            },
        )
        if created and name:
            user.username = name
            user.save(update_fields=["username", "updated_at"])
        staff, _ = SubscriberStaff.objects.update_or_create(
            user=user,
            subscriber=membership.subscriber,
            defaults={"role": SubscriberStaff.Role.EDITOR, "is_active": True},
        )
        return Response(self.get_serializer(staff).data, status=status.HTTP_201_CREATED)

    def perform_destroy(self, staff):
        membership = _staff_membership_for_request(self.request)
        if not membership or membership.role != SubscriberStaff.Role.ADMIN:
            raise PermissionDenied("Only admins can remove staff from the team.")
        if staff.subscriber_id != membership.subscriber_id:
            raise PermissionDenied("Invalid staff record.")
        if staff.role == SubscriberStaff.Role.ADMIN:
            if not _subscriber_has_other_active_admin(
                subscriber_id=staff.subscriber_id,
                exclude_staff_pk=staff.pk,
            ):
                raise ValidationError(
                    "Cannot remove the only active admin for this host. Promote another editor to admin first."
                )
        staff.delete()

    @action(detail=True, methods=["post"])
    def toggle(self, request, pk=None):
        membership = _staff_membership_for_request(request)
        if not membership or membership.role != SubscriberStaff.Role.ADMIN:
            return Response({"detail": "Only admins can update staff access."}, status=status.HTTP_403_FORBIDDEN)
        staff = self.get_object()
        if staff.role == SubscriberStaff.Role.ADMIN and staff.user_id == request.session.get("app_user_id"):
            return Response({"detail": "You cannot suspend your own admin access."}, status=status.HTTP_400_BAD_REQUEST)
        if staff.is_active and staff.role == SubscriberStaff.Role.ADMIN:
            if not _subscriber_has_other_active_admin(
                subscriber_id=staff.subscriber_id,
                exclude_staff_pk=staff.pk,
            ):
                return Response(
                    {"detail": "Cannot archive access for the only active admin."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        staff.is_active = not staff.is_active
        staff.save(update_fields=["is_active", "updated_at"])
        return Response(self.get_serializer(staff).data)


def page(request, template_name):
    context = base_context()
    return render(request, f"{template_name}.html", context)


def _username_from_email(email):
    return email.split("@")[0] if "@" in email else email


def _unique_username(email):
    base = _username_from_email(email) or "user"
    username = base
    suffix = 1
    while AppUser.objects.filter(username=username).exists():
        suffix += 1
        username = f"{base}{suffix}"
    return username


def _password_matches(user, raw_password):
    stored = user.password_hash or ""
    if not stored:
        return False
    try:
        if check_password(raw_password, stored):
            return True
    except Exception:
        pass
    return stored == raw_password


def _ensure_hashed_password(user, raw_password):
    try:
        identify_hasher(user.password_hash or "")
        return
    except Exception:
        user.password_hash = make_password(raw_password)
        user.save(update_fields=["password_hash", "updated_at"])


def _login_app_user(request, user, *, is_staff=False):
    request.session["app_user_id"] = user.id
    request.session["app_user_email"] = user.email
    request.session["app_user_is_staff"] = is_staff
    if not is_staff:
        # Drop host-org context so a student login cannot reuse a stale subscriber_id.
        request.session.pop("subscriber_id", None)


def _bootstrap_session_from_django_user(request):
    """
    Bridge django-allauth login to custom app session keys.
    """
    if request.session.get("app_user_id"):
        return
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return
    email = (request.user.email or "").strip().lower()
    if not email:
        return
    app_user = AppUser.objects.filter(email=email, is_active=True).first()
    if not app_user:
        return
    request.session["app_user_id"] = app_user.id
    request.session["app_user_email"] = app_user.email
    membership = (
        SubscriberStaff.objects.select_related("subscriber")
        .filter(user=app_user, is_active=True, subscriber__status=Subscriber.Status.ACTIVE)
        .first()
    )
    if membership:
        request.session["app_user_is_staff"] = True
        request.session["subscriber_id"] = membership.subscriber_id
    else:
        request.session["app_user_is_staff"] = False
        request.session.pop("subscriber_id", None)


def logout_view(request):
    # allauth OAuth logout may not clear Django's auth session for this project,
    # but our base.html relies on `request.user.is_authenticated`.
    django_logout(request)
    # django.contrib.auth.logout already flushes the session (including app_user_* keys).
    return redirect("index")


def _public_events():
    return (
        Event.objects.select_related("subscriber", "venue", "category")
        .prefetch_related("sessions")
        .filter(status=Event.Status.PUBLISHED, subscriber__status=Subscriber.Status.ACTIVE)
        .order_by("start_at", "created_at")
    )


def _staff_session_context(request):
    _bootstrap_session_from_django_user(request)
    user_id = request.session.get("app_user_id")
    subscriber_id = request.session.get("subscriber_id")
    if not user_id or not subscriber_id:
        messages.error(request, "Please sign in with an active host account.")
        return None, redirect("login_staff")

    membership = (
        SubscriberStaff.objects.select_related("user", "subscriber")
        .filter(
            user_id=user_id,
            subscriber_id=subscriber_id,
            is_active=True,
            subscriber__status=Subscriber.Status.ACTIVE,
        )
        .first()
    )
    if not membership:
        for key in ("app_user_is_staff", "subscriber_id"):
            request.session.pop(key, None)
        messages.error(request, "Your host access is not active.")
        return None, redirect("login_staff")

    context = base_context()
    context.update(
        {
            "dashboard_current_user": membership.user,
            "dashboard_current_subscriber": membership.subscriber,
            "dashboard_primary_subscriber": membership.subscriber,
            "dashboard_staff_membership": membership,
        }
    )
    return context, None


def _staff_membership_for_request(request):
    _bootstrap_session_from_django_user(request)
    user_id = request.session.get("app_user_id")
    subscriber_id = request.session.get("subscriber_id")
    if not user_id or not subscriber_id:
        return None
    return (
        SubscriberStaff.objects.select_related("user", "subscriber")
        .filter(
            user_id=user_id,
            subscriber_id=subscriber_id,
            is_active=True,
            subscriber__status=Subscriber.Status.ACTIVE,
        )
        .first()
    )


def _require_admin_membership(request):
    membership = _staff_membership_for_request(request)
    if not membership:
        return None, redirect("login_staff")
    if membership.role != SubscriberStaff.Role.ADMIN:
        messages.error(request, "Only admin staff can perform this action.")
        return membership, redirect("dashboard_events")
    return membership, None


def _category_from_slug_or_name(value):
    value = (value or "").strip()
    if not value:
        return None
    slug = slugify(value)
    category, _ = Category.objects.get_or_create(slug=slug, defaults={"name": value.replace("-", " ").title()})
    return category


def _parse_event_datetime(date_value):
    date_value = (date_value or "").strip()
    if not date_value:
        return None
    try:
        date_obj = datetime.strptime(date_value, "%Y-%m-%d").date()
    except ValueError:
        return None
    return timezone.make_aware(datetime.combine(date_obj, time(hour=9)))


def _campus_label(value):
    labels = {
        "st-lucia": "St Lucia",
        "gatton": "Gatton",
        "herston": "Herston",
        "online": "Online",
        "other": "Other",
    }
    return labels.get((value or "").strip().lower(), (value or "").strip())


def _clean_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _save_event_from_post(request, subscriber, event=None):
    title = (request.POST.get("title") or "").strip()
    if not title:
        messages.error(request, "Event title is required.")
        return None

    start_at = _parse_event_datetime(request.POST.get("event_date"))
    status = request.POST.get("status")
    if status not in Event.Status.values:
        status = Event.Status.DRAFT

    campus = _campus_label(request.POST.get("campus_line"))
    if event is None:
        event = Event(subscriber=subscriber, created_by_id=request.session.get("app_user_id"))

    event.title = title
    event.tagline = (request.POST.get("lead") or "").strip()
    event.description = (request.POST.get("about") or "").strip() or event.tagline or title
    event.category = _category_from_slug_or_name(request.POST.get("listing_type"))
    event.cost_badge = (request.POST.get("cost_badge") or "").strip()
    event.cost_detail = (request.POST.get("cost_detail") or "").strip()
    event.hero_image_url = (request.POST.get("image_url") or "").strip()
    event.start_at = start_at
    event.time_summary = (request.POST.get("time_summary") or "").strip()
    event.venue_display = (request.POST.get("venue") or "").strip()
    event.campus = campus
    event.is_online = campus.lower() == "online"
    event.maps_url = (request.POST.get("maps_url") or "").strip()
    event.sessions_intro = (request.POST.get("sessions_intro") or "").strip()
    event.highlight_bullets = (request.POST.get("bullets") or "").strip()
    event.status = status
    event.visibility = Event.Visibility.PUBLIC
    event.save()

    # Fine-grained sessions CRUD:
    # - If session{n}_id exists -> update that row
    # - If missing/blank id -> create new row
    # - Rows not present in POST -> delete (unless registrations exist)
    existing = {s.id: s for s in EventSession.objects.filter(event=event)}
    seen_ids = set()
    for index in range(1, 31):
        sid_raw = (request.POST.get(f"session{index}_id") or "").strip()
        title_value = (request.POST.get(f"session{index}_title") or "").strip()
        desc = (request.POST.get(f"session{index}_desc") or "").strip()
        time_label = (request.POST.get(f"session{index}_time") or "").strip()
        location_label = (request.POST.get(f"session{index}_place") or "").strip()
        capacity = _clean_int(request.POST.get(f"session{index}_capacity"))
        registration_kind = request.POST.get(f"session{index}_registration") or EventSession.RegistrationKind.NONE
        if registration_kind not in EventSession.RegistrationKind.values:
            registration_kind = EventSession.RegistrationKind.NONE

        # End of dynamic list (no fields posted at all)
        has_any_field = (
            f"session{index}_title" in request.POST
            or f"session{index}_desc" in request.POST
            or f"session{index}_time" in request.POST
            or f"session{index}_place" in request.POST
            or f"session{index}_registration" in request.POST
            or f"session{index}_capacity" in request.POST
            or f"session{index}_id" in request.POST
        )
        if not has_any_field:
            break

        # Skip empty placeholder blocks
        if not title_value and not desc and not time_label and not location_label:
            continue

        if sid_raw:
            try:
                sid = int(sid_raw)
            except Exception:
                sid = None
            session = existing.get(sid) if sid else None
            if session:
                session.title = title_value or session.title or f"Session {index}"
                session.abstract = desc
                session.time_label = time_label
                session.location_label = location_label
                session.capacity = capacity
                session.registration_kind = registration_kind
                session.order_index = index
                session.save()
                seen_ids.add(session.id)
                continue

        # Create new
        new_session = EventSession.objects.create(
            event=event,
            title=title_value or f"Session {index}",
            abstract=desc,
            time_label=time_label,
            location_label=location_label,
            capacity=capacity,
            registration_kind=registration_kind,
            order_index=index,
        )
        seen_ids.add(new_session.id)

    # Delete sessions removed from the form submission.
    to_delete = [s for s in existing.values() if s.id not in seen_ids]
    for s in to_delete:
        if s.session_registrations.exists():
            messages.warning(
                request,
                f"Could not delete session '{s.title}' because it already has registrations. "
                "Edit it instead or cancel registrations first.",
            )
            # Keep it, but push it to the end so it doesn't conflict
            # with the newly submitted ordering.
            s.order_index = 1000 + s.id
            s.save(update_fields=["order_index", "updated_at"])
            continue
        s.delete()
    return event


def login_user_view(request):
    if request.method != "POST":
        return page(request, "login-user")

    email = (request.POST.get("email") or "").strip().lower()
    password = (request.POST.get("password") or "").strip()
    user = AppUser.objects.filter(email=email, is_active=True).first()

    if not user or not _password_matches(user, password):
        messages.error(request, "Invalid email or password.")
        return redirect("login_user")

    _ensure_hashed_password(user, password)
    _login_app_user(request, user, is_staff=False)
    return redirect("account")


def login_staff_view(request):
    if request.method != "POST":
        return page(request, "login-staff")

    email = (request.POST.get("email") or "").strip().lower()
    password = (request.POST.get("password") or "").strip()
    user = AppUser.objects.filter(email=email, is_active=True).first()

    if not user or not _password_matches(user, password):
        messages.error(request, "Invalid staff email or password.")
        return redirect("login_staff")

    staff_membership = (
        SubscriberStaff.objects.select_related("subscriber")
        .filter(user=user, is_active=True, subscriber__status=Subscriber.Status.ACTIVE)
        .first()
    )
    if not staff_membership:
        request.session.pop("subscriber_id", None)
        request.session["app_user_is_staff"] = False
        messages.error(request, "Your host access is not active yet.")
        return redirect("login_staff")

    _ensure_hashed_password(user, password)
    _login_app_user(request, user, is_staff=True)
    request.session["subscriber_id"] = staff_membership.subscriber_id
    return redirect("dashboard_events")


def register_account_view(request):
    if request.method != "POST":
        return page(request, "register-account")

    first_name = (request.POST.get("firstName") or "").strip()
    last_name = (request.POST.get("lastName") or "").strip()
    email = (request.POST.get("email") or "").strip().lower()
    password = (request.POST.get("password") or "").strip()
    password2 = (request.POST.get("password2") or "").strip()

    if not email or not password:
        messages.error(request, "Email and password are required.")
        return redirect("register_account")
    if password != password2:
        messages.error(request, "Passwords do not match.")
        return redirect("register_account")

    obj, created = AppUser.objects.get_or_create(
        email=email,
        defaults={
            "username": _unique_username(email),
            "password_hash": make_password(password),
            "is_active": True,
            "is_superuser": False,
        },
    )
    if created:
        messages.success(request, f"Account created for {first_name or obj.username} {last_name}".strip())
        _login_app_user(request, obj, is_staff=False)
    else:
        messages.info(request, "This email already exists. Try sign in or use Google/GitHub.")
    return redirect("account")


def register_host_view(request):
    if request.method != "POST":
        return page(request, "register-host")

    org_name = (request.POST.get("orgName") or "").strip()
    org_email = (request.POST.get("orgEmail") or "").strip().lower()
    description = (request.POST.get("description") or "").strip()
    first_name = (request.POST.get("contactFirstName") or "").strip()
    last_name = (request.POST.get("contactLastName") or "").strip()
    contact_email = (request.POST.get("contactEmail") or "").strip().lower()
    password = (request.POST.get("password") or "").strip()
    password2 = (request.POST.get("password2") or "").strip()

    if not org_name or not org_email or not contact_email or not password:
        messages.error(request, "Organization, contact email, and password are required.")
        return redirect("register_host")
    if password != password2:
        messages.error(request, "Passwords do not match.")
        return redirect("register_host")

    user, user_created = AppUser.objects.get_or_create(
        email=contact_email,
        defaults={
            "username": _unique_username(contact_email),
            "password_hash": make_password(password),
            "is_active": True,
            "is_superuser": False,
        },
    )
    if not user_created:
        user.password_hash = make_password(password)
        user.is_active = True
        user.save(update_fields=["password_hash", "is_active", "updated_at"])

    subscriber, _ = Subscriber.objects.get_or_create(
        contact_email=org_email,
        defaults={
            "name": org_name,
            "slug": _unique_subscriber_slug(org_name),
            "status": Subscriber.Status.SUSPENDED,
            "tagline": f"Pending host application from {first_name} {last_name}".strip(),
            "description": description,
            "suspended_at": timezone.now(),
        },
    )

    SubscriberStaff.objects.get_or_create(
        user=user,
        subscriber=subscriber,
        defaults={"role": SubscriberStaff.Role.ADMIN, "is_active": False},
    )

    messages.success(request, "Host application submitted. An admin can activate your organization and staff access from Django Admin.")
    return redirect("register_host_pending")


def base_context():
    db_events = _public_events()
    subscribers = (
        Subscriber.objects.prefetch_related("official_links", "staff_memberships")
        .filter(status=Subscriber.Status.ACTIVE)
        .order_by("name")
    )
    return {
        "db_events": db_events,
        "subscribers": subscribers,
    }


def _unique_subscriber_slug(name, existing_subscriber=None):
    base = slugify(name) or "subscriber"
    slug = base
    suffix = 1
    queryset = Subscriber.objects.all()
    if existing_subscriber:
        queryset = queryset.exclude(pk=existing_subscriber.pk)
    while queryset.filter(slug=slug).exists():
        suffix += 1
        slug = f"{base}-{suffix}"
    return slug


def _save_subscriber_from_post(request, subscriber=None):
    name = (request.POST.get("display_name") or request.POST.get("name") or "").strip()
    contact_email = (request.POST.get("contact_email") or "").strip()
    tagline = (request.POST.get("lead") or "").strip()
    description = (request.POST.get("about_paragraph_1") or "").strip()
    website_url = (request.POST.get("website_url") or "").strip()
    status_value = request.POST.get("host_status") or Subscriber.Status.ACTIVE

    if not name:
        messages.error(request, "Organization name is required.")
        return None

    if not contact_email:
        contact_email = "contact@example.com"

    if status_value in {"draft", "hidden", "suspended"}:
        status = Subscriber.Status.SUSPENDED
    else:
        status = Subscriber.Status.ACTIVE

    if subscriber is None:
        subscriber = Subscriber(slug=_unique_subscriber_slug(name))
    elif subscriber.name != name:
        subscriber.slug = _unique_subscriber_slug(name, subscriber)

    subscriber.name = name
    subscriber.contact_email = contact_email
    subscriber.tagline = tagline
    subscriber.description = description
    subscriber.website_url = website_url
    subscriber.status = status
    subscriber.suspended_at = timezone.now() if status == Subscriber.Status.SUSPENDED else None
    subscriber.save()

    SubscriberOfficialLink.objects.filter(subscriber=subscriber).delete()
    channel_index = 1
    sort_order = 0
    while True:
        label = (request.POST.get(f"channel{channel_index}_label") or "").strip()
        url = (request.POST.get(f"channel{channel_index}_url") or "").strip()
        if channel_index > 20:
            break
        if label or url:
            if label and url:
                SubscriberOfficialLink.objects.create(
                    subscriber=subscriber,
                    label=label,
                    url=url,
                    sort_order=sort_order,
                )
                sort_order += 1
        elif f"channel{channel_index}_label" not in request.POST and f"channel{channel_index}_url" not in request.POST:
            break
        channel_index += 1

    return subscriber


def index_view(request):
    context = base_context()
    db_events = context["db_events"]

    q = (request.GET.get("q") or "").strip()
    location = (request.GET.get("location") or "").strip().lower()
    category = (request.GET.get("category") or "").strip().lower()
    dates = (request.GET.get("dates") or "").strip()

    if q:
        db_events = db_events.filter(
            Q(title__icontains=q)
            | Q(tagline__icontains=q)
            | Q(description__icontains=q)
            | Q(subscriber__name__icontains=q)
            | Q(venue_display__icontains=q)
        )

    if location:
        if location == "online":
            db_events = db_events.filter(is_online=True)
        else:
            db_events = db_events.filter(
                Q(campus__icontains=location)
                | Q(venue_display__icontains=location)
                | Q(venue__campus__icontains=location)
            )

    if category:
        db_events = db_events.filter(Q(category__slug__iexact=category) | Q(category__name__iexact=category))

    if dates:
        parts = [p.strip() for p in dates.split("to")]
        if len(parts) == 2 and parts[0] and parts[1]:
            try:
                db_events = db_events.filter(start_at__date__range=[parts[0], parts[1]])
            except Exception:
                pass
        else:
            try:
                db_events = db_events.filter(start_at__date=dates)
            except Exception:
                pass

    context["featured_events"] = list(db_events[:12])
    context["filter_values"] = {
        "q": q,
        "location": location,
        "category": category,
        "dates": dates,
    }
    context["filter_categories"] = (
        _public_events()
        .exclude(category__isnull=True)
        .values_list("category__name", "category__slug")
        .distinct()
        .order_by("category__name")
    )
    return render(request, "index.html", context)


def events_view(request):
    context = base_context()
    db_events = context["db_events"]

    q = (request.GET.get("q") or "").strip()
    location = (request.GET.get("location") or "").strip().lower()
    category = (request.GET.get("category") or "").strip().lower()
    dates = (request.GET.get("dates") or "").strip()

    if q:
        db_events = db_events.filter(
            Q(title__icontains=q)
            | Q(tagline__icontains=q)
            | Q(description__icontains=q)
            | Q(subscriber__name__icontains=q)
            | Q(venue_display__icontains=q)
        )

    if location:
        if location == "online":
            db_events = db_events.filter(is_online=True)
        else:
            db_events = db_events.filter(
                Q(campus__icontains=location)
                | Q(venue_display__icontains=location)
                | Q(venue__campus__icontains=location)
            )

    if category:
        db_events = db_events.filter(Q(category__slug__iexact=category) | Q(category__name__iexact=category))

    if dates:
        parts = [p.strip() for p in dates.split("to")]
        if len(parts) == 2 and parts[0] and parts[1]:
            try:
                db_events = db_events.filter(start_at__date__range=[parts[0], parts[1]])
            except Exception:
                pass
        else:
            try:
                db_events = db_events.filter(start_at__date=dates)
            except Exception:
                pass

    paginator = Paginator(db_events, 9)
    page_obj = paginator.get_page(request.GET.get("page"))
    context["db_events"] = page_obj
    context["events_page_obj"] = page_obj
    context["filter_values"] = {
        "q": q,
        "location": location,
        "category": category,
        "dates": dates,
    }
    context["filter_categories"] = (
        _public_events()
        .exclude(category__isnull=True)
        .values_list("category__name", "category__slug")
        .distinct()
        .order_by("category__name")
    )

    calendar_events = []
    for event in db_events:
        if not event.start_at:
            continue
        calendar_events.append(
            {
                "date": event.start_at.date().isoformat(),
                "title": event.title,
                "href": reverse("event_detail", args=[event.id]),
            }
        )
    context["calendar_events"] = calendar_events
    now = timezone.localtime(timezone.now())
    context["calendar_initial_year"] = now.year
    context["calendar_initial_month"] = now.month
    return render(request, "events.html", context)


def event_detail_view(request, event_id):
    context = base_context()
    event = get_object_or_404(
        _public_events(),
        pk=event_id,
    )
    # If the user logged in via OAuth (allauth), we may need to bridge
    # request.user -> our custom session keys before allowing registration.
    _bootstrap_session_from_django_user(request)
    if request.method == "POST":
        user_id = request.session.get("app_user_id")
        if not user_id:
            messages.error(request, "Please sign in before registering for an event.")
            return redirect("login_user")

        registration, created = Registration.objects.get_or_create(
            event=event,
            user_id=user_id,
            defaults={"status": Registration.Status.CONFIRMED},
        )
        if not created and registration.status == Registration.Status.CANCELLED:
            registration.status = Registration.Status.CONFIRMED
            registration.save(update_fields=["status", "updated_at"])

        selected_session_ids = request.POST.getlist("sessions")
        if selected_session_ids:
            RegistrationSession.objects.filter(registration=registration).delete()
            sessions = event.sessions.filter(id__in=selected_session_ids)
            for session in sessions:
                taken = session.session_registrations.filter(
                    registration__status=Registration.Status.CONFIRMED
                ).count()
                if session.capacity is not None and taken >= session.capacity:
                    messages.error(request, f"{session.title} is already full.")
                    return redirect("event_detail", event_id=event.id)
                RegistrationSession.objects.get_or_create(registration=registration, event_session=session)

        messages.success(request, f"You are registered for {event.title}.")
        return redirect("account")

    sessions_qs = (
        event.sessions.annotate(
            taken=Count(
                "session_registrations",
                filter=Q(session_registrations__registration__status=Registration.Status.CONFIRMED),
            )
        )
        .order_by("order_index", "start_at")
    )
    for s in sessions_qs:
        if s.capacity is not None:
            s.places_remaining = max(0, s.capacity - s.taken)
            s.session_is_full = s.taken >= s.capacity
        else:
            s.places_remaining = None
            s.session_is_full = False

    context["event"] = event
    context["event_sessions"] = sessions_qs
    return render(request, "event-detail.html", context)


def hosts_view(request):
    context = base_context()
    subscribers = context["subscribers"]
    q = (request.GET.get("q") or "").strip()
    if q:
        subscribers = subscribers.filter(
            Q(name__icontains=q) | Q(tagline__icontains=q) | Q(description__icontains=q)
        )
    paginator = Paginator(subscribers, 9)
    page_obj = paginator.get_page(request.GET.get("page"))
    context["subscribers"] = page_obj
    context["hosts_page_obj"] = page_obj
    context["hosts_filter_q"] = q
    return render(request, "hosts.html", context)


def host_profile_view(request, slug="uq-union"):
    context = base_context()
    host = get_object_or_404(
        Subscriber.objects.prefetch_related("official_links"),
        slug=slug,
        status=Subscriber.Status.ACTIVE,
    )
    host_events = _public_events().filter(subscriber=host)
    now = timezone.now()
    context["host_profile"] = host
    context["host_upcoming_events"] = [e for e in host_events if (e.end_at or e.start_at or now) >= now]
    context["host_past_events"] = [e for e in host_events if (e.end_at or e.start_at or now) < now]
    return render(request, "host-uq-union.html", context)


def account_view(request):
    context = base_context()
    _bootstrap_session_from_django_user(request)
    app_user = request.session.get("app_user_id")
    if not app_user and getattr(request, "user", None) and request.user.is_authenticated:
        app_user = AppUser.objects.filter(email=request.user.email).values_list("id", flat=True).first()

    registrations = (
        Registration.objects.select_related("event")
        .prefetch_related("registration_sessions__event_session")
        .exclude(status=Registration.Status.CANCELLED)
    )
    cancelled_registrations = (
        Registration.objects.select_related("event")
        .prefetch_related("registration_sessions__event_session")
        .filter(status=Registration.Status.CANCELLED)
    )
    if app_user:
        registrations = registrations.filter(user_id=app_user)
        cancelled_registrations = cancelled_registrations.filter(user_id=app_user)
    else:
        registrations = registrations.none()
        cancelled_registrations = cancelled_registrations.none()

    now = timezone.now()
    upcoming_regs = [r for r in registrations if (r.event.end_at or r.event.start_at or now) >= now]
    past_regs = [r for r in registrations if (r.event.end_at or r.event.start_at or now) < now]

    context["upcoming_regs"] = upcoming_regs
    context["past_regs"] = past_regs
    context["cancelled_regs"] = list(cancelled_registrations.order_by("-updated_at", "-created_at"))
    context["live_upcoming_regs"] = upcoming_regs
    context["app_user"] = AppUser.objects.filter(pk=app_user).first() if app_user else None
    return render(request, "account.html", context)


def cancel_registration_view(request, registration_id):
    _bootstrap_session_from_django_user(request)
    user_id = request.session.get("app_user_id")
    if request.method == "POST" and user_id:
        registration = get_object_or_404(Registration, pk=registration_id, user_id=user_id)
        registration.status = Registration.Status.CANCELLED
        registration.save(update_fields=["status", "updated_at"])
        messages.success(request, f"Cancelled registration for {registration.event.title}.")
    else:
        messages.error(request, "Please sign in to manage registrations.")
    return redirect("account")


def forgot_password_view(request):
    if request.method != "POST":
        return page(request, "forgot-password")

    email = (request.POST.get("email") or "").strip().lower()
    user = AppUser.objects.filter(email=email, is_active=True).first()
    if user:
        temp_password = f"uqeventhub-{timezone.now().strftime('%H%M%S')}"
        user.password_hash = make_password(temp_password)
        user.save(update_fields=["password_hash", "updated_at"])
        messages.success(request, f"Temporary password for {email}: {temp_password}")
    else:
        messages.info(request, "If that account exists, password reset instructions will be available.")
    return redirect("forgot_password")


def dashboard_events_view(request):
    context, response = _staff_session_context(request)
    if response:
        return response
    subscriber = context["dashboard_current_subscriber"]
    events = list(
        Event.objects.select_related("subscriber", "venue", "category")
        .prefetch_related("sessions")
        .filter(subscriber=subscriber)
        .order_by("-updated_at", "-created_at")
    )
    total_regs = sum(e.registrations.count() for e in events)
    active_events = len([e for e in events if e.status == "published"])
    capacities = [e.capacity for e in events if e.capacity]
    avg_capacity = int(sum(capacities) / len(capacities)) if capacities else 0
    context["dashboard_events"] = events
    context["dashboard_total_regs"] = total_regs
    context["dashboard_active_events"] = active_events
    context["dashboard_avg_capacity"] = avg_capacity
    return render(request, "dashboard-events.html", context)


def dashboard_organizations_view(request):
    context, response = _staff_session_context(request)
    if response:
        return response
    q = (request.GET.get("q") or "").strip()
    selected_id = request.GET.get("subscriber")
    current_subscriber = context["dashboard_current_subscriber"]
    subscribers = Subscriber.objects.prefetch_related("official_links").filter(pk=current_subscriber.pk).order_by("name")
    if q:
        subscribers = subscribers.filter(
            Q(name__icontains=q)
            | Q(slug__icontains=q)
            | Q(contact_email__icontains=q)
            | Q(tagline__icontains=q)
            | Q(description__icontains=q)
        )

    paginator = Paginator(subscribers, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    host = subscribers.filter(pk=selected_id).first() if selected_id else current_subscriber
    context["dashboard_subscribers"] = page_obj.object_list
    context["dashboard_subscribers_page"] = page_obj
    context["dashboard_subscriber_q"] = q
    context["dashboard_primary_subscriber"] = host
    context["dashboard_official_links"] = host.official_links.all().order_by("sort_order", "id") if host else []
    return render(request, "dashboard-organizations.html", context)


def dashboard_organization_create_view(request):
    _, denied = _require_admin_membership(request)
    if denied:
        return denied
    context, response = _staff_session_context(request)
    if response:
        return response
    if request.method == "POST":
        subscriber = _save_subscriber_from_post(request)
        if subscriber:
            messages.success(request, f"{subscriber.name} was created.")
            return redirect(f"{reverse('dashboard_organizations')}?subscriber={subscriber.id}")
    context["dashboard_subscribers"] = Subscriber.objects.filter(pk=context["dashboard_current_subscriber"].pk).order_by("name")
    context["dashboard_subscriber_q"] = ""
    context["dashboard_primary_subscriber"] = None
    context["dashboard_official_links"] = []
    context["dashboard_is_create"] = True
    return render(request, "dashboard-organizations.html", context)


def dashboard_organization_update_view(request, subscriber_id):
    _, denied = _require_admin_membership(request)
    if denied:
        return denied
    context, response = _staff_session_context(request)
    if response:
        return response
    if subscriber_id != context["dashboard_current_subscriber"].pk:
        messages.error(request, "You can only edit your own organization.")
        return redirect("dashboard_organizations")
    subscriber = context["dashboard_current_subscriber"]
    if request.method != "POST":
        return redirect(f"{reverse('dashboard_organizations')}?subscriber={subscriber.id}")

    updated = _save_subscriber_from_post(request, subscriber)
    if updated:
        messages.success(request, f"{updated.name} was updated.")
        return redirect(f"{reverse('dashboard_organizations')}?subscriber={updated.id}")
    return redirect(f"{reverse('dashboard_organizations')}?subscriber={subscriber.id}")


def dashboard_organization_delete_view(request, subscriber_id):
    _, denied = _require_admin_membership(request)
    if denied:
        return denied
    context, response = _staff_session_context(request)
    if response:
        return response
    if subscriber_id != context["dashboard_current_subscriber"].pk:
        messages.error(request, "You can only delete your own organization.")
        return redirect("dashboard_organizations")
    subscriber = context["dashboard_current_subscriber"]
    if request.method == "POST":
        subscriber.status = Subscriber.Status.SUSPENDED
        subscriber.suspended_at = timezone.now()
        subscriber.save(update_fields=["status", "suspended_at"])
        messages.success(request, f"{subscriber.name} was archived (suspended).")
    return redirect("dashboard_organizations")


def dashboard_event_new_view(request):
    context, response = _staff_session_context(request)
    if response:
        return response
    if request.method == "POST":
        event = _save_event_from_post(request, context["dashboard_current_subscriber"])
        if event:
            messages.success(request, f"{event.title} was saved.")
            return redirect("dashboard_event_sessions", event_id=event.id)
    event_qs = Event.objects.filter(subscriber=context["dashboard_current_subscriber"]).select_related("category", "venue")
    context["dashboard_categories"] = {e.category.name for e in event_qs if e.category}
    context["dashboard_venues"] = {e.venue_display or (e.venue.name if e.venue else "") for e in event_qs}
    return render(request, "dashboard-event-new.html", context)


def dashboard_event_sessions_view(request, event_id):
    context, response = _staff_session_context(request)
    if response:
        return response
    event = get_object_or_404(
        Event.objects.select_related("subscriber", "category", "venue").prefetch_related("sessions"),
        pk=event_id,
        subscriber=context["dashboard_current_subscriber"],
    )
    if request.method == "POST":
        saved = _save_event_from_post(request, context["dashboard_current_subscriber"], event)
        if saved:
            messages.success(request, f"{saved.title} was updated.")
            return redirect("dashboard_event_sessions", event_id=saved.id)
    context["dashboard_edit_event"] = event
    context["dashboard_edit_sessions"] = event.sessions.all().order_by("order_index", "start_at") if event else []
    return render(request, "dashboard-event-sessions.html", context)


def dashboard_event_archive_view(request, event_id):
    """Hide event from public listings (soft archive). Any active staff may archive."""
    context, response = _staff_session_context(request)
    if response:
        return response
    if request.method != "POST":
        return redirect("dashboard_event_sessions", event_id=event_id)
    event = get_object_or_404(
        Event,
        pk=event_id,
        subscriber=context["dashboard_current_subscriber"],
    )
    event.status = Event.Status.ARCHIVED
    event.save()
    messages.success(request, f"{event.title} was archived and is no longer shown on the public site.")
    return redirect("dashboard_events")


def dashboard_event_delete_view(request, event_id):
    """Hard delete only when there are no registrations (admin only)."""
    _, denied = _require_admin_membership(request)
    if denied:
        return denied
    context, response = _staff_session_context(request)
    if response:
        return response
    if request.method != "POST":
        return redirect("dashboard_event_sessions", event_id=event_id)
    event = get_object_or_404(
        Event,
        pk=event_id,
        subscriber=context["dashboard_current_subscriber"],
    )
    if event.registrations.exists():
        messages.error(
            request,
            "Cannot delete this event because it has registrations. Archive it instead, or cancel registrations first.",
        )
        return redirect("dashboard_event_sessions", event_id=event_id)
    title = event.title
    event.delete()
    messages.success(request, f"{title} was deleted.")
    return redirect("dashboard_events")


def dashboard_staff_view(request):
    context, response = _staff_session_context(request)
    if response:
        return response
    primary_subscriber = context["dashboard_current_subscriber"]
    staff_rows = (
        SubscriberStaff.objects.select_related("user", "subscriber")
        .filter(subscriber=primary_subscriber)
        .order_by("-role", "user__username")
    )
    context["dashboard_staff_rows"] = staff_rows
    context["dashboard_staff_total"] = staff_rows.count()
    context["dashboard_staff_active"] = staff_rows.filter(is_active=True).count()
    context["dashboard_primary_subscriber"] = primary_subscriber
    return render(request, "dashboard-staff.html", context)


def dashboard_staff_invite_view(request):
    _, denied = _require_admin_membership(request)
    if denied:
        return denied
    context, response = _staff_session_context(request)
    if response:
        return response
    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        email = (request.POST.get("email") or "").strip().lower()
        if not email:
            messages.error(request, "Staff email is required.")
            return redirect("dashboard_staff")
        user, created = AppUser.objects.get_or_create(
            email=email,
            defaults={
                "username": slugify(name) or _unique_username(email),
                "password_hash": make_password("changeme123"),
                "is_active": True,
                "is_superuser": False,
            },
        )
        if created and name:
            user.username = name
            user.save(update_fields=["username", "updated_at"])
        SubscriberStaff.objects.update_or_create(
            user=user,
            subscriber=context["dashboard_current_subscriber"],
            defaults={"role": SubscriberStaff.Role.EDITOR, "is_active": True},
        )
        messages.success(request, f"{email} now has editor access. Temporary password: changeme123")
    return redirect("dashboard_staff")


def dashboard_staff_toggle_view(request, staff_id):
    _, denied = _require_admin_membership(request)
    if denied:
        return denied
    context, response = _staff_session_context(request)
    if response:
        return response
    staff = get_object_or_404(SubscriberStaff, pk=staff_id, subscriber=context["dashboard_current_subscriber"])
    if request.method == "POST":
        current_uid = request.session.get("app_user_id")
        if staff.role == SubscriberStaff.Role.ADMIN and staff.user_id == current_uid:
            messages.error(request, "You cannot suspend your own admin access.")
            return redirect("dashboard_staff")
        if staff.is_active and staff.role == SubscriberStaff.Role.ADMIN:
            if not _subscriber_has_other_active_admin(
                subscriber_id=staff.subscriber_id,
                exclude_staff_pk=staff.pk,
            ):
                messages.error(request, "Cannot archive access for the only active admin.")
                return redirect("dashboard_staff")
        staff.is_active = not staff.is_active
        staff.save(update_fields=["is_active", "updated_at"])
        messages.success(request, f"{staff.user.username} access is now {'active' if staff.is_active else 'archived'}.")
    return redirect("dashboard_staff")
