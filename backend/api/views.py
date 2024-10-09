from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import ProductImage, ImageProcessingRequest
from .constants import STATUS_IN_PROGRESS, STATUS_FAILED
from backend.tasks import process_images_async
import csv
import datetime
import os
from django.conf import settings
from io import StringIO
from urllib.parse import urlparse


class UploadCSV(APIView):
    def post(self, request):
        file = request.FILES.get('file')
        if not file:
            return Response({"error": "No file provided"}, status=status.HTTP_400_BAD_REQUEST)

        image_processing_request = ImageProcessingRequest.objects.create()
        
        # Parse and validate CSV
        try:
            csv_file = StringIO(file.read().decode())
            csv_reader = csv.DictReader(csv_file)
            try:
                rows = [row for row in csv_reader]
                self.validate_csv(rows)
            except ValueError as e:
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)  

            # Trigger async image processing
            process_images_async.delay(rows, image_processing_request.request_id)

            return Response({"request_id": str(image_processing_request.request_id)}, status=status.HTTP_201_CREATED)
        except Exception as e:
            image_processing_request.status = STATUS_FAILED
            image_processing_request.save()
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


    def validate_csv(self, rows):
        required_columns = ['S. No.', 'Product Name', 'Input Image Urls']
        for row in rows:
            for col in required_columns:
                if col not in row or not row[col]:
                    raise ValueError(f"Missing or empty column: {col}")

            # Validate URLs
            urls = row['Input Image Urls'].split(',')
            for url in urls:
                parsed = urlparse(url.strip())
                if not parsed.scheme or not parsed.netloc:
                    raise ValueError(f"Invalid URL: {url}")
                

class StatusAPI(APIView):
    def get(self, request, request_id):
        try:
            image_processing_request = ImageProcessingRequest.objects.get(request_id=request_id)
            products = image_processing_request.products.all()  
            
            product_statuses = [{
                "serial_number": product.serial_number,
                "product_name": product.product_name,
                "status": product.status
            } for product in products]
            
            response_data = {
                "request_id": str(image_processing_request.request_id),
                "status": image_processing_request.status,
                "products": product_statuses
            }
            
            return Response(response_data, status=status.HTTP_200_OK)
        
        except ImageProcessingRequest.DoesNotExist:
            return Response({"error": "Request ID not found."}, status=status.HTTP_404_NOT_FOUND)


class OutputWebhook(APIView):
    def post(self, request):
        output_rows = request.data['output_rows']
        output_file_name = 'output_file' + str(datetime.datetime.now) + '.csv'
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
        return Response({"status": "success"}, status=200)