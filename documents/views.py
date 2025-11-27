import json
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings
from .models import Document
from .services import get_document_service
import traceback
import os


@csrf_exempt
@require_http_methods(["POST"])
def upload_document(request):
    """Handle document upload and process it for embeddings."""
    try:
        if 'file' not in request.FILES:
            return JsonResponse({'error': 'No file provided'}, status=400)
        
        uploaded_file = request.FILES['file']
        
        # Validate file type (only PDF for now)
        if not uploaded_file.name.lower().endswith('.pdf'):
            return JsonResponse({'error': 'Only PDF files are supported'}, status=400)
        
        # Save the file
        document = Document.objects.create(
            filename=uploaded_file.name,
            file=uploaded_file
        )
        
        # Process the document: create embeddings and store in FAISS
        try:
            service = get_document_service()
            vectorstore_path = service.process_document(
                document.file.path,
                document.id
            )
            document.vectorstore_path = vectorstore_path
            document.processed = True
            document.save()
            
            return JsonResponse({
                'success': True,
                'document_id': document.id,
                'filename': document.filename,
                'message': 'Document uploaded and processed successfully'
            })
        except ValueError as e:
            # Handle specific API errors with user-friendly messages
            traceback.print_exc()
            document.delete()  # Clean up if processing fails
            error_message = str(e)
            if "rate limit" in error_message.lower() or "quota" in error_message.lower():
                return JsonResponse({
                    'error': error_message,
                    'error_type': 'rate_limit',
                    'suggestion': 'Please check your OpenAI account billing and plan. You may need to add credits or wait for the rate limit to reset.'
                }, status=429)
            elif "authentication" in error_message.lower():
                return JsonResponse({
                    'error': error_message,
                    'error_type': 'authentication',
                    'suggestion': 'Please verify your OPENAI_API_KEY in the .env file is correct and valid.'
                }, status=401)
            else:
                return JsonResponse({
                    'error': error_message,
                    'error_type': 'api_error'
                }, status=500)
        except Exception as e:
            traceback.print_exc()
            document.delete()  # Clean up if processing fails
            return JsonResponse({
                'error': f'Error processing document: {str(e)}',
                'error_type': 'unknown'
            }, status=500)
            
    except Exception as e:
        traceback.print_exc()
        return JsonResponse({
            'error': f'Error uploading document: {str(e)}'
        }, status=500)


@require_http_methods(["GET"])
def list_documents(request):
    """List all uploaded documents."""
    documents = Document.objects.filter(processed=True)
    return JsonResponse({
        'documents': [
            {
                'id': doc.id,
                'filename': doc.filename,
                'uploaded_at': doc.uploaded_at.isoformat()
            }
            for doc in documents
        ]
    })


def chat_interface(request):
    """Serve the chat interface HTML file."""
    if settings.STATICFILES_DIRS:
        chat_html_path = os.path.join(settings.STATICFILES_DIRS[0], 'chat.html')
    else:
        chat_html_path = os.path.join(settings.BASE_DIR, 'static', 'chat.html')
    
    try:
        with open(chat_html_path, 'r') as f:
            return HttpResponse(f.read(), content_type='text/html')
    except FileNotFoundError:
        return HttpResponse('Chat interface not found. Please ensure chat.html exists in the static directory.', status=404)
