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
