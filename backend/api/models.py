from django.db import models
import uuid
from .constants import STATUS_CHOICES, STATUS_IN_PROGRESS


class ImageProcessingRequest(models.Model):
    request_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)  # Unique request ID
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_IN_PROGRESS)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return str(self.request_id)
    

class ProductImage(models.Model):
    serial_number = models.IntegerField()
    product_name = models.CharField(max_length=255)
    input_image_urls = models.TextField()
    request = models.ForeignKey(ImageProcessingRequest, on_delete=models.CASCADE, related_name='products', null=True)  # Associate with request
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_IN_PROGRESS)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.product_name


