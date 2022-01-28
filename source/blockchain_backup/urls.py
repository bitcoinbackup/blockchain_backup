'''
    Urls for Blockchain Backup.

    Copyright 2018-2022 DeNova
    Last modified: 2022-01-10
'''

from django.urls import include, re_path

from blockchain_backup import views
from blockchain_backup.bitcoin.views import Home
from denova.django_addons.views import catch_all

non_searchable_urlpatterns = [
    re_path(r'.*?bootstrap.min.js.map$', views.empty_response),
    re_path(r'^csrf_failure/?(.*?)', views.csrf_failure),
]

searchable_urlpatterns = [
    re_path(r'^bitcoin/?', include('blockchain_backup.bitcoin.urls')),

    # nginx usually serves favicon.ico, but selenium doesn't go through nginx
    re_path(r'^favicon.ico', views.StaticView.as_view(),
         dict(filepath='/var/local/blockchain-backup/packages/blockchain_backup/static/images/favicon.ico')),

    re_path(r'^about/?$', views.About.as_view(), name='about'),

    re_path(r'^$', Home.as_view(), name='home'),
]

catch_all_urlpatterns = [

    # template matching catch all
    re_path(r'^(.*)$', catch_all),
]

urlpatterns = non_searchable_urlpatterns
urlpatterns += searchable_urlpatterns
urlpatterns += catch_all_urlpatterns
