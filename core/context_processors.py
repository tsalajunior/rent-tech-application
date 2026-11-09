from .models import Notification


def unread_notifications(request):
    user = request.user
    if not user.is_authenticated:
        return {"unread_notifications_count": 0}
    return {
        "unread_notifications_count": Notification.objects.filter(
            recipient=user, read_at__isnull=True
        ).count()
    }
