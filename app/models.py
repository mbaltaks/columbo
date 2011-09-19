from django.db import models

class GithubAPIResult(models.Model):
    date_created = models.DateTimeField(auto_now=False, auto_now_add=True)
    date_modified = models.DateTimeField()
    lifetime = models.IntegerField() # This file expires after lifetime seconds.
    address = models.CharField(max_length=500)
    data = models.TextField()
    ordering = ['address']


class OAuthToken(models.Model):
    date_created = models.DateTimeField(auto_now=False, auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True, auto_now_add=True)
    token = models.TextField()


class BasicCredential(models.Model):
    date_created = models.DateTimeField(auto_now=False, auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True, auto_now_add=True)
    username = models.TextField()
    password = models.TextField()
