import os
import base64
import requests
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from .serializers import RepoRequestSerializer

def fetch_repo_tree(owner, repo, branch="main"):
    headers = {"Accept": "application/vnd.github.v3+json"}
    url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            return response.json().get("tree", [])
    except Exception:
        pass
    return None

def fetch_file_content(owner, repo, path, branch="main"):
    headers = {"Accept": "application/vnd.github.v3+json"}
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}?ref={branch}"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        if data.get("encoding") == "base64":
            try:
                return base64.b64decode(data["content"]).decode("utf-8")
            except Exception:
                return ""
    return ""

@csrf_exempt
@api_view(['POST'])
def generate_readme_api(request):
    serializer = RepoRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    owner = serializer.validated_data.get("owner")
    repo = serializer.validated_data.get("repo")
    branch = serializer.validated_data.get("branch")
    tone = serializer.validated_data.get("tone", "technical")
    additional_instructions = serializer.validated_data.get("additional_instructions", "")

    tree = fetch_repo_tree(owner, repo, branch)
    if tree is None:
        return Response({
            "error": "Failed to fetch repository structure. Please verify that the repository is public and the branch name is correct."
        }, status=status.HTTP_502_BAD_GATEWAY)

    all_paths = [item["path"] for item in tree if item["type"] == "blob"]

    important_files = ["requirements.txt", "package.json", "dockerfile", "setup.py", "pyproject.toml", "cargo.toml", "go.mod", "pipfile", "composer.json"]
    found_important_paths = [
        path for path in all_paths 
        if any(path.lower().endswith(f) or path.lower().split("/")[-1] == f for f in important_files)
    ]

    file_contexts = []
    for file_path in found_important_paths[:5]: 
        content = fetch_file_content(owner, repo, file_path, branch)
        if content:
            file_contexts.append(f"--- File: {file_path} ---\n{content[:2000]}")

    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        return Response({"error": "GEMINI_API_KEY was found in the environment. Please configure at least one API key in your .env file!"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    context_string = "\n\n".join(file_contexts)
    tree_string = "\n".join(all_paths[:100])

    tone_guidelines = {
        "technical": "Write with a professional, developer-focused, and highly technical tone. Emphasize codebase architecture, installation steps, configuration files, and API endpoints.",
        "beginner-friendly": "Write in a welcoming, clear, and beginner-friendly tone. Provide simple explanations, step-by-step guides, and explain concepts without assuming prior knowledge.",
        "comprehensive": "Write a highly detailed, comprehensive README.md. Cover all aspects, including prerequisites, installation, usage examples, configuration, folder structure, contribution guidelines, and tests."
    }
    selected_tone = tone_guidelines.get(tone, tone_guidelines["technical"])

    prompt = f"""
    You are an expert technical writer. Write a professional README.md file for the GitHub repository: {owner}/{repo}.
    
    Here is the Repository Folder Structure:
    {tree_string}
    
    Here is the code inside the configuration files:
    {context_string}
    
    Guidelines:
    - Tone/Style: {selected_tone}
    """

    if additional_instructions:
        prompt += f"\n- Additional user instructions to incorporate: {additional_instructions}\n"

    prompt += "\nGenerate a complete README.md in Markdown format. Do not include conversational text before or after the markdown. Output only the README content."

    generated_markdown = ""
    error_details = []

    # Try both APIs in order (Gemini first, then Groq as fallback)
    attempts = []
    if gemini_key:
        attempts.append(("gemini", gemini_key))

    for api_type, api_key in attempts:
        if api_type == "gemini":
            gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
            payload = {"contents": [{"parts": [{"text": prompt}]}]}
            try:
                llm_response = requests.post(gemini_url, json=payload, headers={"Content-Type": "application/json"}, timeout=30)
                if llm_response.status_code == 200:
                    generated_markdown = llm_response.json()["candidates"][0]["content"]["parts"][0]["text"]
                    break
                else:
                    error_details.append(f"Gemini API Error (Status {llm_response.status_code}): {llm_response.text}")
            except Exception as e:
                error_details.append(f"Failed to connect to Gemini API: {str(e)}")

    if generated_markdown:
        if request.user.is_authenticated:
            try:
                GeneratedReadme.objects.create(
                    user=request.user,
                    repo_url=serializer.validated_data.get("repo_url"),
                    owner=owner,
                    repo=repo,
                    branch=branch,
                    readme_content=generated_markdown,
                    tone=tone,
                    files_analyzed=found_important_paths
                )
            except Exception as db_err:
                print(f"[DB SAVE ERROR] Failed to save generated README: {str(db_err)}")
        return Response({
            "readme": generated_markdown,
            "files_analyzed": found_important_paths,
            "owner": owner,
            "repo": repo,
            "branch": branch
        }, status=status.HTTP_200_OK)
    else:
        error_summary = "\n".join(error_details)
        print(f"[API ERROR] {error_summary}")
        return Response({
            "error": error_summary
        }, status=status.HTTP_502_BAD_GATEWAY)

from django.contrib.auth import authenticate, login as django_login, logout as django_logout
from django.contrib.auth.models import User
from .models import GeneratedReadme
from .serializers import GeneratedReadmeSerializer

@api_view(['POST'])
def auth_signup(request):
    username = request.data.get('username', '').strip()
    password = request.data.get('password', '').strip()
    if not username or not password:
        return Response({"error": "Username and password are required."}, status=status.HTTP_400_BAD_REQUEST)
    
    if User.objects.filter(username=username).exists():
        return Response({"error": "Username already exists."}, status=status.HTTP_400_BAD_REQUEST)
        
    user = User.objects.create_user(username=username, password=password)
    django_login(request, user)
    return Response({"status": "success", "username": user.username})

@api_view(['POST'])
def auth_login(request):
    username = request.data.get('username', '').strip()
    password = request.data.get('password', '').strip()
    user = authenticate(username=username, password=password)
    if user is not None:
        django_login(request, user)
        return Response({"status": "success", "username": user.username})
    return Response({"error": "Invalid username or password."}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
def auth_logout(request):
    django_logout(request)
    return Response({"status": "success"})

@api_view(['GET'])
def auth_status(request):
    if request.user.is_authenticated:
        return Response({"is_authenticated": True, "username": request.user.username})
    return Response({"is_authenticated": False})

@api_view(['GET'])
def user_readme_history(request):
    if not request.user.is_authenticated:
        return Response({"error": "Authentication required to view database history."}, status=status.HTTP_401_UNAUTHORIZED)
        
    readmes = GeneratedReadme.objects.filter(user=request.user).order_by('-created_at')
    serializer = GeneratedReadmeSerializer(readmes, many=True)
    return Response(serializer.data)

@api_view(['DELETE'])
def delete_user_readme(request, pk):
    if not request.user.is_authenticated:
        return Response({"error": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED)
    try:
        readme = GeneratedReadme.objects.get(pk=pk, user=request.user)
        readme.delete()
        return Response({"status": "success"})
    except GeneratedReadme.DoesNotExist:
        return Response({"error": "Record not found."}, status=status.HTTP_404_NOT_FOUND)

from django.views.decorators.csrf import ensure_csrf_cookie

@ensure_csrf_cookie
def home_page(request):
    # Refreshed to reload env v7
    return render(request, 'api/index.html')