from django.urls import path
from . import views

urlpatterns = [
    path("", views.chat_interface, name="chat_interface"),
    path("api/upload/", views.upload_document, name="upload_document"),
    path("api/documents/", views.list_documents, name="list_documents"),
]
