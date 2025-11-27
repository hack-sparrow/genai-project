from django.db import models
from django.utils import timezone
import os


class Document(models.Model):
    """Model to store document metadata and file information."""
    
    filename = models.CharField(max_length=255)
    file = models.FileField(upload_to='uploads/')
    uploaded_at = models.DateTimeField(default=timezone.now)
    processed = models.BooleanField(default=False)
    vectorstore_path = models.CharField(max_length=500, blank=True, null=True)
    
    class Meta:
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return self.filename
    
    @property
    def file_path(self):
        """Return the absolute file path."""
        return self.file.path if self.file else None
