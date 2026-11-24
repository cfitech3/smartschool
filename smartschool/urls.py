from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.views.static import serve
from django.views.generic import TemplateView
from core.views_media import protected_media_serve

urlpatterns = [
    path(settings.ADMIN_URL_PATH, admin.site.urls),
    path('', include('core.urls')),
    path('auth/', include('accounts.urls')),
    path('etablissements/', include('etablissements.urls')),
    path('eleves/', include('eleves.urls')),
    path('finances/', include('finances.urls')),
    path('notes/', include('notes.urls')),

    # PWA Routes
    path('sw.js', TemplateView.as_view(template_name='pwa/sw.js', content_type='application/javascript'), name='sw'),
    path('manifest.json', TemplateView.as_view(template_name='pwa/manifest.json', content_type='application/json'), name='manifest'),
    path('offline/', TemplateView.as_view(template_name='pwa/offline.html'), name='offline'),

    # Médias servis via contrôle d'accès multi-tenant (logos publics, photos d'élèves/staff privées)
    re_path(r'^media/(?P<path>.*)$', protected_media_serve, name='protected_media'),
]

if not settings.DEBUG:
    urlpatterns += [
        re_path(r'^static/(?P<path>.*)$', serve, {'document_root': settings.STATIC_ROOT}),
    ]
