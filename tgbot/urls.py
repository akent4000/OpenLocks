from django.urls import path

from django.views.generic import RedirectView
from OpenLocks import settings

app_name = 'tgbot'

urlpatterns = [
    path('favicon.ico', RedirectView.as_view(url=settings.STATIC_URL + 'favicon.ico')),
]