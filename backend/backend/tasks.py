from celery import shared_task
import requests
import os
from PIL import Image
from io import BytesIO
from api.models import ProductImage, ImageProcessingRequest
from django.conf import settings

@shared_task
def process_images_async(rows, request_id):
    try:
        image_processing_request = ImageProcessingRequest.objects.get(request_id=request_id)
    except ImageProcessingRequest.DoesNotExist:
        return  

    failed_images = []
    for row in rows:
        product_name = row['Product Name']
        urls = row['Input Image Urls'].split(',')
        
        product_image = ProductImage.objects.create(
            serial_number=row['S. No.'],
            product_name=product_name,
            input_image_urls=row['Input Image Urls'],  
            request=image_processing_request,
            status='IN_PROGRESS'  
        )

        product_dir = os.path.join(settings.BASE_DIR, 'media', 'output_images', product_name)
        if not os.path.exists(product_dir):
            os.makedirs(product_dir)

        for count,url in enumerate(urls):
            try:
                response = requests.get(url.strip())
                response.raise_for_status()  
                img = Image.open(BytesIO(response.content))
                img = img.convert('RGB')
                file_name = str(count)
                file_name += '.jpg'
                output_path = os.path.join(product_dir, file_name)
                
                img.save(output_path, quality=50)

            except Exception as e:
                failed_images.append(url.strip())  
                continue 

        if len(failed_images) == len(urls):
            product_image.status = 'FAILED'
        elif failed_images:
            product_image.status = 'PARTIALLY_FAILED'
        else:
            product_image.status = 'COMPLETED'

        product_image.save()  

    if all(product_image.status == 'COMPLETED' for product_image in image_processing_request.products.all()):
        image_processing_request.status = 'COMPLETED'
    else:
        image_processing_request.status = 'FAILED' if failed_images else 'PARTIALLY_FAILED'  # Update based on failures

    image_processing_request.save()
