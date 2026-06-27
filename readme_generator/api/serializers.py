from urllib.parse import urlparse
from rest_framework import serializers

class RepoRequestSerializer(serializers.Serializer):
    """Validates the data sent by the user."""
    # We ask the user for a single URL instead of separate fields
    repo_url = serializers.URLField(
        help_text="Example: https://github.com/tiangolo/fastapi"
    )
    branch = serializers.CharField(max_length=100, default="main", required=False)
    tone = serializers.CharField(max_length=50, default="technical", required=False)
    additional_instructions = serializers.CharField(max_length=1000, default="", required=False, allow_blank=True)

    def validate(self, data):
        """
        Custom validation to extract 'owner' and 'repo' from the URL.
        This runs automatically when serializer.is_valid() is called in the view.
        """
        repo_url = data.get('repo_url')
        
        # urlparse breaks the URL into pieces (scheme, netloc, path, etc.)
        parsed_url = urlparse(repo_url)

        # 1. Ensure it's actually a GitHub link
        if parsed_url.netloc != "github.com":
            raise serializers.ValidationError({"repo_url": "Must be a valid github.com link."})

        # 2. Remove trailing slashes and split the path 
        # Example: "/tiangolo/fastapi/" becomes ["tiangolo", "fastapi"]
        path_parts = parsed_url.path.strip("/").split("/")
        
        if len(path_parts) < 2:
            raise serializers.ValidationError({"repo_url": "URL must contain both the owner and repository name."})

        # 3. Inject the extracted parts into the data dictionary!
        # Now our view can simply call serializer.validated_data.get('owner')
        data['owner'] = path_parts[0]
        data['repo'] = path_parts[1]

        return data