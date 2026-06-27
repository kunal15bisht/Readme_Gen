from django.db import models
from django.contrib.auth.models import User

class GeneratedReadme(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="readmes")
    repo_url = models.URLField(max_length=500)
    owner = models.CharField(max_length=255)
    repo = models.CharField(max_length=255)
    branch = models.CharField(max_length=100, default="main")
    readme_content = models.TextField()
    tone = models.CharField(max_length=50, default="technical")
    files_analyzed = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.owner}/{self.repo} ({self.user.username})"
