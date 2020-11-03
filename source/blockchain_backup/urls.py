'''
    Urls for Blockchain Backup.

    Copyright 2018-2020 DeNova
    Last modified: 2020-09-21
'''

from django.conf.urls import include, re_path

from blockchain_backup import views
from blockchain_backup.bitcoin.views import Home
from denova.django_addons.views import catch_all

non_searchable_urlpatterns = [
    re_path(r'.*?bootstrap.min.js.map$', views.empty_response),
]

searchable_urlpatterns = [
    re_path(r'^bitcoin/?', include('blockchain_backup.bitcoin.urls')),

    re_path(r'^$', Home.as_view(), name='home'),

    re_path(r'^about/?$', views.About.as_view(), name='about'),
]

catch_all_urlpatterns = [

    # template matching catch all
    re_path(r'^(.*)$', catch_all),
]

urlpatterns = non_searchable_urlpatterns
urlpatterns += searchable_urlpatterns
urlpatterns += catch_all_urlpatterns
