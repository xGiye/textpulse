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
        value = request.data.get("value").lower()
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
        record = StringRecord.objects.get(value=string_value.lower())
    except StringRecord.DoesNotExist:
        return Response({"error": "String not found"}, status=status.HTTP_404_NOT_FOUND)
    
    return Response(StringRecordSerializer(record).data, status=status.HTTP_200_OK)

# GET /strings (filters)
@api_view(['GET'])
def list_strings(request):
    """
    GET /strings
    Supports filters:
    - is_palindrome (true/false)
    - min_length
    - max_length
    - word_count
    - contains_character
    """

    # Start with all records
    records = StringRecord.objects.all()

    # --- Retrieve Query Parameters ---
    is_palindrome = request.query_params.get('is_palindrome')
    min_length = request.query_params.get('min_length')
    max_length = request.query_params.get('max_length')
    word_count = request.query_params.get('word_count')
    contains_character = request.query_params.get('contains_character')

    # --- Apply Filters ---
    try:
        # Filter by palindrome
        if is_palindrome is not None:
            if is_palindrome.lower() not in ['true', 'false']:
                return Response(
                    {"error": "Invalid value for is_palindrome (must be true or false)"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            is_palindrome_bool = is_palindrome.lower() == 'true'
            records = records.filter(properties__is_palindrome=is_palindrome_bool)

        # Filter by length
        if min_length is not None:
            records = records.filter(properties__length__gte=int(min_length))
        if max_length is not None:
            records = records.filter(properties__length__lte=int(max_length))

        # Filter by word_count
        if word_count is not None:
            records = records.filter(properties__word_count=int(word_count))

        # Filter by character presence (case-sensitive)
        if contains_character is not None:
            records = records.filter(value__contains=contains_character)

    except ValueError:
        return Response(
            {"error": "Invalid query parameter type"},
            status=status.HTTP_400_BAD_REQUEST
        )

    # --- Prepare Response ---
    data = []
    for record in records:
        data.append({
            "id": record.id,
            "value": record.value,
            "properties": record.properties,
            "created_at": record.created_at.isoformat(),
        })

    filters_applied = {
        "is_palindrome": is_palindrome,
        "min_length": min_length,
        "max_length": max_length,
        "word_count": word_count,
        "contains_character": contains_character
    }
    # Remove None filters from response
    filters_applied = {k: v for k, v in filters_applied.items() if v is not None}

    return Response({
        "data": data,
        "count": len(data),
        "filters_applied": filters_applied
    }, status=status.HTTP_200_OK)

# GET /strings/filter-by-natural-language
@api_view(['GET'])
def filter_by_natural_language(request):
    """
    GET /strings/filter-by-natural-language?query=<string>
    Supports:
      - "all single word palindromic strings"
      - "strings longer than 10 characters"
      - "strings containing the letter z"
      - "palindromic strings"
    """
    query = request.query_params.get('query')

    if not query:
        return Response(
            {"error": "Missing query parameter"},
            status=status.HTTP_400_BAD_REQUEST
        )

    query_lower = query.lower().strip()
    filters = {}
    interpreted_query = {"original": query, "parsed_filters": {}}

    # --- Basic NLP pattern recognition ---
    if "single word" in query_lower and "palindromic" in query_lower:
        filters["properties__word_count"] = 1
        filters["properties__is_palindrome"] = True
        interpreted_query["parsed_filters"] = {"word_count": 1, "is_palindrome": True}

    elif "longer than" in query_lower and "characters" in query_lower:
        try:
            words = query_lower.split()
            number = next(int(w) for w in words if w.isdigit())
            min_length = number + 1
            filters["properties__length__gte"] = min_length
            interpreted_query["parsed_filters"] = {"min_length": min_length}
        except StopIteration:
            return Response(
                {"error": "Unable to parse numeric value in query"},
                status=status.HTTP_400_BAD_REQUEST
            )

    elif "containing the letter" in query_lower:
        try:
            letter = query_lower.split("letter")[-1].strip().replace("'", "").replace('"', '')
            letter = letter.strip()
            if len(letter) == 0:
                raise ValueError
            filters["value__contains"] = letter
            interpreted_query["parsed_filters"] = {"contains_character": letter}
        except Exception:
            return Response(
                {"error": "Unable to parse letter from query"},
                status=status.HTTP_400_BAD_REQUEST
            )

    elif "palindromic" in query_lower:
        filters["properties__is_palindrome"] = True
        interpreted_query["parsed_filters"] = {"is_palindrome": True}

    else:
        return Response(
            {"error": "Unable to parse natural language query"},
            status=status.HTTP_400_BAD_REQUEST
        )

    # --- Apply filters ---
    records = StringRecord.objects.filter(**filters)

    data = []
    for record in records:
        data.append({
            "id": record.id,
            "value": record.value,
            "properties": record.properties,
            "created_at": record.created_at.isoformat(),
        })

    return Response({
        "data": data,
        "count": len(data),
        "interpreted_query": interpreted_query
    }, status=status.HTTP_200_OK)

# DELETE /strings/{string_value}
@api_view(['DELETE'])
def delete_string(request, string_value):
    try:
        # Case-insensitive match
        record = StringRecord.objects.get(value=string_value.lower())
        record.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    except StringRecord.DoesNotExist:
        return Response(
            {"error": "String not found"},
            status=status.HTTP_404_NOT_FOUND
        )