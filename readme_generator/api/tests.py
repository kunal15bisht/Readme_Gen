import json
from unittest.mock import patch, MagicMock
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from api.serializers import RepoRequestSerializer

class RepoRequestSerializerTests(APITestCase):
    def test_valid_github_url(self):
        data = {
            "repo_url": "https://github.com/tiangolo/fastapi",
            "branch": "main",
            "tone": "technical",
            "additional_instructions": "Focus on Docker"
        }
        serializer = RepoRequestSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["owner"], "tiangolo")
        self.assertEqual(serializer.validated_data["repo"], "fastapi")
        self.assertEqual(serializer.validated_data["branch"], "main")
        self.assertEqual(serializer.validated_data["tone"], "technical")
        self.assertEqual(serializer.validated_data["additional_instructions"], "Focus on Docker")

    def test_invalid_github_url(self):
        data = {"repo_url": "https://notgithub.com/tiangolo/fastapi"}
        serializer = RepoRequestSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("repo_url", serializer.errors)

    def test_missing_repo_name(self):
        data = {"repo_url": "https://github.com/tiangolo"}
        serializer = RepoRequestSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("repo_url", serializer.errors)

    def test_default_values(self):
        data = {"repo_url": "https://github.com/tiangolo/fastapi"}
        serializer = RepoRequestSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data.get("branch"), "main")
        self.assertEqual(serializer.validated_data.get("tone"), "technical")
        self.assertEqual(serializer.validated_data.get("additional_instructions"), "")


class GenerateReadmeAPITests(APITestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.url = reverse('generate_readme')
        self.valid_payload = {
            "repo_url": "https://github.com/tiangolo/fastapi",
            "branch": "main",
            "tone": "technical",
            "additional_instructions": ""
        }

    @patch('api.views.requests.get')
    @patch('api.views.requests.post')
    def test_successful_generation_gemini(self, mock_post, mock_get):
        # Mock GitHub Repo Tree
        mock_tree_response = MagicMock()
        mock_tree_response.status_code = 200
        mock_tree_response.json.return_value = {
            "tree": [
                {"path": "package.json", "type": "blob"},
                {"path": "README.md", "type": "blob"},
                {"path": "src/index.js", "type": "blob"}
            ]
        }

        # Mock GitHub File Content
        mock_file_response = MagicMock()
        mock_file_response.status_code = 200
        mock_file_response.json.return_value = {
            "content": "eyAibmFtZSI6ICJmYXN0YXBpIiB9"  # base64 encoded '{ "name": "fastapi" }'
        }

        # Set up mock_get side_effect
        mock_get.side_effect = [mock_tree_response, mock_file_response]

        # Mock LLM API response (Gemini)
        mock_llm_response = MagicMock()
        mock_llm_response.status_code = 200
        mock_llm_response.json.return_value = {
            "candidates": [{
                "content": {
                    "parts": [{"text": "# Mocked README Output"}]
                }
            }]
        }
        mock_post.return_value = mock_llm_response

        # Execute request
        response = self.client.post(self.url, self.valid_payload, format='json')

        # Assertions
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("readme", response.data)
        self.assertEqual(response.data["readme"], "# Mocked README Output")
        self.assertEqual(response.data["owner"], "tiangolo")
        self.assertEqual(response.data["repo"], "fastapi")
        self.assertIn("package.json", response.data["files_analyzed"])

    @patch('api.views.requests.get')
    def test_github_repo_not_found(self, mock_get):
        # Mock GitHub Repo Tree return 404
        mock_tree_response = MagicMock()
        mock_tree_response.status_code = 404
        mock_get.return_value = mock_tree_response

        # Execute request
        response = self.client.post(self.url, self.valid_payload, format='json')

        # Assertions
        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertIn("error", response.data)
        self.assertIn("Failed to fetch repository structure", response.data["error"])

    @patch('api.views.requests.get')
    @patch('api.views.requests.post')
    def test_llm_api_failure(self, mock_post, mock_get):
        # Mock GitHub Repo Tree
        mock_tree_response = MagicMock()
        mock_tree_response.status_code = 200
        mock_tree_response.json.return_value = {"tree": []}
        mock_get.return_value = mock_tree_response

        # Mock LLM API response failing with 500
        mock_llm_response = MagicMock()
        mock_llm_response.status_code = 500
        mock_llm_response.text = "Internal Server Error"
        mock_post.return_value = mock_llm_response

        # Execute request
        response = self.client.post(self.url, self.valid_payload, format='json')

        # Assertions
        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertIn("error", response.data)

    @patch('api.views.requests.get')
    @patch('api.views.requests.post')
    def test_rate_limiting_trigger(self, mock_post, mock_get):
        from django.core.cache import cache
        cache.clear()
        
        # Mock GitHub Repo Tree
        mock_tree_response = MagicMock()
        mock_tree_response.status_code = 200
        mock_tree_response.json.return_value = {"tree": []}
        mock_get.return_value = mock_tree_response
        
        # Mock LLM response
        mock_llm_response = MagicMock()
        mock_llm_response.status_code = 200
        mock_llm_response.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": "readme"}]}}]
        }
        mock_post.return_value = mock_llm_response
        
        # Make 10 successful requests
        for i in range(10):
            response = self.client.post(self.url, self.valid_payload, format='json')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            
        # 11th request should fail with 429
        response = self.client.post(self.url, self.valid_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn("Rate limit exceeded", response.data["error"])

from django.contrib.auth.models import User
from api.models import GeneratedReadme

class AuthAndHistoryAPITests(APITestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.signup_url = reverse('auth_signup')
        self.login_url = reverse('auth_login')
        self.logout_url = reverse('auth_logout')
        self.status_url = reverse('auth_status')
        self.history_url = reverse('user_readme_history')
        self.credentials = {"username": "testuser", "password": "testpassword123"}

    def test_signup_successful(self):
        response = self.client.post(self.signup_url, self.credentials, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], "testuser")
        self.assertEqual(response.data["status"], "success")

    def test_signup_username_exists(self):
        User.objects.create_user(username="testuser", password="testpassword123")
        response = self.client.post(self.signup_url, self.credentials, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    def test_login_successful(self):
        User.objects.create_user(username="testuser", password="testpassword123")
        response = self.client.post(self.login_url, self.credentials, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], "testuser")
        
        # Test status endpoint is now authenticated
        status_res = self.client.get(self.status_url)
        self.assertTrue(status_res.data["is_authenticated"])
        self.assertEqual(status_res.data["username"], "testuser")

    def test_login_invalid_credentials(self):
        response = self.client.post(self.login_url, self.credentials, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    def test_logout_successful(self):
        user = User.objects.create_user(username="testuser", password="testpassword123")
        self.client.force_authenticate(user=user)
        response = self.client.post(self.logout_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_history_anonymous_rejected(self):
        response = self.client.get(self.history_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_history_authenticated_retrieval_and_delete(self):
        user = User.objects.create_user(username="testuser", password="testpassword123")
        self.client.force_authenticate(user=user)
        
        # Create a mock readme entry
        readme_entry = GeneratedReadme.objects.create(
            user=user,
            repo_url="https://github.com/django/django",
            owner="django",
            repo="django",
            readme_content="# Django README",
            tone="technical"
        )

        # Retrieve history
        response = self.client.get(self.history_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["owner"], "django")
        self.assertEqual(response.data[0]["readme_content"], "# Django README")

        # Delete entry
        delete_url = reverse('delete_user_readme', kwargs={'pk': readme_entry.pk})
        del_response = self.client.delete(delete_url)
        self.assertEqual(del_response.status_code, status.HTTP_200_OK)
        self.assertEqual(GeneratedReadme.objects.filter(user=user).count(), 0)
