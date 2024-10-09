from celery import shared_task
import requests
import os
import csv
import datetime
from PIL import Image
from io import BytesIO
from api.models import ProductImage, ImageProcessingRequest
from django.conf import settings

@shared_task
def process_images_async(rows, request_id):
    try:
        image_processing_request = ImageProcessingRequest.objects.get(request_id=request_id)
    except ImageProcessingRequest.DoesNotExist:
        print(f"Failed to process images")
        return  

    output_rows = []
    failed_images = []
    try:
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
            output_urls = []
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
                    output_urls.append(output_path)
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

            output_rows.append({
                    "S. No.": row['S. No.'],
                    "Product Name": product_name,
                    "Input Image Urls": row['Input Image Urls'],
                    "Output Image Urls": ", ".join(output_urls)  # Store comma-separated output URLs
                })

        if all(product_image.status == 'COMPLETED' for product_image in image_processing_request.products.all()):
            image_processing_request.status = 'COMPLETED'
        else:
            image_processing_request.status = 'FAILED' if failed_images else 'PARTIALLY_FAILED'  # Update based on failures


        image_processing_request.save()
        output_file_name = 'output_file-{date:%Y-%m-%d_%H:%M:%S}.txt'.format( date=datetime.datetime.now()) + '.csv'
        output_csv_dir = os.path.join(settings.BASE_DIR, 'media', 'output_files')
        if not os.path.exists(output_csv_dir):
            os.makedirs(output_csv_dir)
        output_csv_path = os.path.join(output_csv_dir, output_file_name)

        with open(output_csv_path, 'w', newline='') as csvfile:
            fieldnames = ['S. No.', 'Product Name', 'Input Image Urls', 'Output Image Urls']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for output_row in output_rows:
                writer.writerow(output_row)

        # webhook_payload = {
        #     "request_id": str(request_id),
        #     "status": image_processing_request.status,
        #     "failed_images": failed_images,
        #     "output_rows": output_rows,
        #     "message": "Image processing completed"
        # }
        # try:
        #     requests.post("http://0.0.0.0:8000/api/output-webhook/", json=webhook_payload)
        # except requests.exceptions.RequestException as e:
        #     print(f"Failed to trigger webhook: {e}")
    except Exception as e:
        ImageProcessingRequest.objects.filter(request_id=request_id).update(status='FAILED')
        print(f"Failed to process images: {str(e)}")
