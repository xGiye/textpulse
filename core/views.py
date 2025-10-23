from django.shortcuts import render

# Create your views here.
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from .models import StringRecord
from .serializers import StringRecordSerializer
from .utils import analyze_string

# POST /strings
@api_view(['POST'])
def create_string(request):
    """
    Create a new StringRecord with analyzed properties.
    Handles validation, duplicate checks, and detailed responses.
    """
    try:
        value = request.data.get("value")
        print(request.data)
        print(value)
        # Check for missing or empty value
        if value is None or value == "":
            return Response(
                {"error": "Missing 'value' field"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate that value is a string
        if not isinstance(value, str):
            return Response(
                {"error": "Invalid data type for 'value' (must be a string)"},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY
            )

        # Check if string already exists
        if StringRecord.objects.filter(value=value).exists():
            return Response(
                {"error": "String already exists"},
                status=status.HTTP_409_CONFLICT
            )

        # Analyze string properties
        properties = analyze_string(value)

        # Create and save record
        record = StringRecord.objects.create(
            value=value,
            sha256_hash=properties.get("sha256_hash"),
            properties=properties
        )

        # Serialize and return response
        serializer = StringRecordSerializer(record)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    except Exception as e:
        # Catch any unexpected errors
        return Response(
            {"error": f"Internal Server Error: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    

# GET /strings/{string_value}
@api_view(['GET'])
def get_string(request, string_value):
    try:
        record = StringRecord.objects.get(value=string_value)
    except StringRecord.DoesNotExist:
        return Response({"error": "String not found"}, status=status.HTTP_404_NOT_FOUND)
    
    return Response(StringRecordSerializer(record).data, status=status.HTTP_200_OK)

# GET /strings (filters)
@api_view(['GET'])
def list_strings(request):
    """
    Retrieve all stored strings with optional filters:
    - is_palindrome (true/false)
    - min_length (int)
    - max_length (int)
    - word_count (int)
    - contains_character (str)
    """
    try:
        queryset = StringRecord.objects.all()
        filters_applied = {}

        # Extract query params
        is_palindrome = request.GET.get("is_palindrome")
        min_length = request.GET.get("min_length")
        max_length = request.GET.get("max_length")
        word_count = request.GET.get("word_count")
        contains_char = request.GET.get("contains_character")

        # Apply filters (in memory, since properties is a JSONField)
        filtered_records = []
        for record in queryset:
            props = record.properties
            keep = True  # flag to keep the record

            # Filter: palindrome
            if is_palindrome is not None:
                target = is_palindrome.lower() == "true"
                if props.get("is_palindrome") != target:
                    keep = False
                else:
                    filters_applied["is_palindrome"] = target

            # Filter: min_length
            if keep and min_length:
                if props.get("length", 0) < int(min_length):
                    keep = False
                else:
                    filters_applied["min_length"] = int(min_length)

            # Filter: max_length
            if keep and max_length:
                if props.get("length", 0) > int(max_length):
                    keep = False
                else:
                    filters_applied["max_length"] = int(max_length)

            # Filter: word_count
            if keep and word_count:
                if props.get("word_count", 0) != int(word_count):
                    keep = False
                else:
                    filters_applied["word_count"] = int(word_count)

            # Filter: contains_character
            if keep and contains_char:
                if contains_char not in record.value:
                    keep = False
                else:
                    filters_applied["contains_character"] = contains_char

            if keep:
                filtered_records.append(record)

        serializer = StringRecordSerializer(filtered_records, many=True)

        return Response({
            "status": "success",
            "count": len(filtered_records),
            "filters_applied": filters_applied,
            "data": serializer.data
        }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({
            "status": "error",
            "message": f"Internal Server Error: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



# GET /strings/filter-by-natural-language
@api_view(['GET'])
def natural_filter(request):
    query = request.GET.get("query", "").lower()
    parsed_filters = {}
    
    if "palindromic" in query:
        parsed_filters["is_palindrome"] = True
    if "single word" in query:
        parsed_filters["word_count"] = 1
    if "longer than" in query:
        num = ''.join(filter(str.isdigit, query))
        if num: parsed_filters["min_length"] = int(num) + 1
    if "containing the letter" in query:
        letter = query.split("letter")[-1].strip().split()[0]
        parsed_filters["contains_character"] = letter

    # reuse list_strings filters
    req = request._request
    req.GET = parsed_filters
    return list_strings(request)

# DELETE /strings/{string_value}
@api_view(['DELETE'])
def delete_string(request, string_value):
    try:
        record = StringRecord.objects.get(value=string_value)
        record.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    except StringRecord.DoesNotExist:
        return Response({"error": "String not found"}, status=status.HTTP_404_NOT_FOUND)
