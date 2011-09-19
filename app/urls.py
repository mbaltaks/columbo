from django.conf.urls.defaults import *

urlpatterns = patterns('app.views',
    # Issues report
    (r'^login$','github_login'),
    (r'^github-callback$','github_callback'),
    (r'^[/]*$','index'),
    (r'^burndown$','burndown'),
    (r'^schedule$','schedule'),
)
