from urllib.parse import urlparse
from rest_framework import serializers

class RepoRequestSerializer(serializers.Serializer):
    """Validates the data sent by the user."""
    repo_url = serializers.URLField(
        help_text="Example: https://github.com/tiangolo/fastapi"
    )
    branch = serializers.CharField(max_length=100, default="main", required=False)
    
    # NEW: Add fields for tone and additional instructions
    tone = serializers.ChoiceField(
        choices=["technical", "beginner-friendly", "comprehensive"], 
        default="technical", 
        required=False
    )
    additional_instructions = serializers.CharField(
        allow_blank=True, 
        default="", 
        required=False
    )

    def validate(self, data):
        """Extracts 'owner' and 'repo' from the URL."""
        repo_url = data.get('repo_url')
        parsed_url = urlparse(repo_url)

        if parsed_url.netloc != "github.com":
            raise serializers.ValidationError({"repo_url": "Must be a valid github.com link."})

        path_parts = parsed_url.path.strip("/").split("/")
        if len(path_parts) < 2:
            raise serializers.ValidationError({"repo_url": "URL must contain both the owner and repository name."})

        data['owner'] = path_parts[0]
        data['repo'] = path_parts[1]

        return data

from .models import GeneratedReadme

class GeneratedReadmeSerializer(serializers.ModelSerializer):
    class Meta:
        model = GeneratedReadme
        fields = ['id', 'repo_url', 'owner', 'repo', 'branch', 'readme_content', 'tone', 'files_analyzed', 'created_at']
        read_only_fields = ['id', 'created_at']