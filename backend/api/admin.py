from django.contrib import admin
from .models import ProductImage, ImageProcessingRequest
# Register your models here.

admin.site.register(ProductImage)
admin.site.register(ImageProcessingRequest)