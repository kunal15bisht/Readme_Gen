"""
URL configuration for readme_generator project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from api.views import (
    generate_readme_api,
    home_page,
    auth_signup,
    auth_login,
    auth_logout,
    auth_status,
    user_readme_history,
    delete_user_readme
)

urlpatterns = [
    # 1. The visible website frontend (Loads your index.html at the root URL)
    path('', home_page, name='home'),
    
    # 2. The invisible DRF API Endpoint (Listens for the frontend's data)
    path('api/generate-readme/', generate_readme_api, name='generate_readme'),
    
    # 3. Authentication Endpoints
    path('api/auth/signup/', auth_signup, name='auth_signup'),
    path('api/auth/login/', auth_login, name='auth_login'),
    path('api/auth/logout/', auth_logout, name='auth_logout'),
    path('api/auth/status/', auth_status, name='auth_status'),
    
    # 4. User History Endpoint
    path('api/history/', user_readme_history, name='user_readme_history'),
    path('api/history/<int:pk>/delete/', delete_user_readme, name='delete_user_readme'),
]

