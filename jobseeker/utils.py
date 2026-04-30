from rest_framework.response import Response
from rest_framework import status

def custom_response(success, message, data=None, errors=None, status_code=status.HTTP_200_OK):
    return Response({
        "success": success,
        "message": message,
        "data": data,
        "errors": errors
    }, status=status_code)