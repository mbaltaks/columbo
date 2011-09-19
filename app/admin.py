from django.contrib import admin
from app.models import *

class GithubAPIResultAdmin(admin.ModelAdmin):
    list_display = ['id', 'address', 'date_modified', 'lifetime', 'date_created']
    ordering = ['address']
admin.site.register(GithubAPIResult, GithubAPIResultAdmin)


class OAuthTokenAdmin(admin.ModelAdmin):
    list_display = ['id', 'date_modified', 'token', 'date_created']
    ordering = ['date_modified']
admin.site.register(OAuthToken, OAuthTokenAdmin)


class BasicCredentialAdmin(admin.ModelAdmin):
    list_display = ['id', 'date_modified', 'username', 'date_created']
    ordering = ['date_modified']
admin.site.register(BasicCredential, BasicCredentialAdmin)
