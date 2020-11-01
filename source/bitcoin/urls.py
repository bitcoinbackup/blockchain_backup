'''
    Bitcoin  urls.

    Copyright 2018-2019 DeNova
    Last modified: 2019-12-12
'''
from django.conf.urls import re_path
from django.urls import path

from blockchain_backup.bitcoin import views

# do *not* "name" non-searchable patterns
non_searchable_urlpatterns = [

    path('interrupt_update/', views.InterruptUpdate.as_view()),
    path('interrupt_backup/', views.InterruptBackup.as_view()),
    path('interrupt_restore/', views.InterruptRestore.as_view()),

    path('change_backup_status/', views.ChangeBackupStatus.as_view()),

    path('init_data_dir/', views.InitDataDir.as_view()),

    path('ajax/', views.Ajax.as_view()),
]

# "name" all patterns you want included in the sitemap.xml
searchable_urlpatterns = [
    path('access_wallet/', views.AccessWallet.as_view(), name='access_wallet'),

    path('update/', views.Update.as_view(), name='update_blockchain'),
    path('backup/', views.Backup.as_view(), name='backup_blockchain'),
    path('restore/', views.Restore.as_view(), name='restore_blockchain'),

    path('preferences/', views.ChangePreferences.as_view(), name='change_preferences'),

    re_path(r'^$', views.Home.as_view(), name='home'),
]

urlpatterns = non_searchable_urlpatterns
urlpatterns += searchable_urlpatterns
