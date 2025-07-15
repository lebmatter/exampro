# Copyright (c) 2024, Labeeb Mattra and contributors
# For license information, please see license.txt

import frappe
import boto3
from botocore.exceptions import ClientError
from frappe.model.document import Document


class ExamSettings(Document):
	
	def get_storage_endpoint(self):
		"""
		Get the storage endpoint URL based on the selected provider
		"""
		if self.storage_provider == "AWS S3":
			return f"https://{self.s3_bucket}.s3.amazonaws.com"
		elif self.storage_provider == "Cloudflare R2":
			return f'https://{self.aws_account_id}.r2.cloudflarestorage.com'
		else:
			return None

def validate_video_settings():
	"""
	Validate AWS/Cloudflare account details are valid
	Returns True if credentials are valid, False otherwise
	"""
	settings = frappe.get_single("Exam Settings")
	aws_secret = settings.get_password("aws_secret")
	if not (settings.aws_account_id and settings.aws_key and aws_secret and settings.s3_bucket):
		frappe.msgprint("Video storage error: All AWS/Cloudflare credentials and bucket name are required")
		return False

	import pdb; pdb.set_trace()  # Debugging line to inspect the state before validation
	try:
		# Create S3 client with the appropriate endpoint based on provider
		client_kwargs = {
			'aws_access_key_id': settings.aws_key,
			'aws_secret_access_key': aws_secret
		}
		
		# Add endpoint_url for Cloudflare R2
		if settings.storage_provider == "Cloudflare R2":
			client_kwargs['endpoint_url'] = f'https://{settings.aws_account_id}.r2.cloudflarestorage.com'
		
		# Create an S3 client with the provided credentials
		s3_client = boto3.client('s3', **client_kwargs)
		
		# Try to access the bucket to verify credentials
		# Try to list objects in the bucket to verify access
		response = s3_client.list_objects_v2(
			Bucket=settings.s3_bucket,
			MaxKeys=1  # Just check for one object to minimize data transfer
		)
		# If we got here, the credentials and bucket access are valid
		return True
		
	except ClientError as e:
		error_code = e.response.get('Error', {}).get('Code', '')
		
		if error_code == '403':
			frappe.msgprint("Video storage error:  Access denied. Please check your AWS/Cloudflare credentials.")
		elif error_code == '404':
			frappe.msgprint(f"Bucket '{settings.s3_bucket}' not found.")
		else:
			frappe.msgprint(f"Video storage error: Error validating AWS/Cloudflare settings: {str(e)}")
			
		return False
		
	except Exception as e:
		frappe.msgprint(f"Video storage error: Unexpected error validating settings: {str(e)}")
		return False