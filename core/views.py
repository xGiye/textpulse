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
@api_view(['GET', 'POST'])
def strings(request):
    """
    Create a new StringRecord with analyzed properties.
    Handles validation, duplicate checks, and detailed responses.
    """
    if request.method == 'POST':
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
        
    
    # ========== LIST + FILTER STRINGS ==========
    elif request.method == 'GET':
        
        records = StringRecord.objects.all()

        # --- Query Parameters ---
        params = request.query_params
        is_palindrome = params.get('is_palindrome')
        min_length = params.get('min_length')
        max_length = params.get('max_length')
        word_count = params.get('word_count')
        contains_character = params.get('contains_character')

        try:
            # --- Filter: is_palindrome ---
            if is_palindrome is not None:
                if is_palindrome.lower() not in ['true', 'false']:
                    return Response(
                        {"error": "Invalid value for is_palindrome (must be true or false)"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                is_palindrome_bool = is_palindrome.lower() == 'true'
                records = records.filter(properties__is_palindrome=is_palindrome_bool)

            # --- Filter: min_length / max_length ---
            if min_length is not None:
                records = records.filter(properties__length__gte=int(min_length))
            if max_length is not None:
                records = records.filter(properties__length__lte=int(max_length))

            # --- Filter: word_count ---
            if word_count is not None:
                records = records.filter(properties__word_count=int(word_count))

            # --- Filter: contains_character (case-sensitive) ---
            if contains_character is not None:
                records = records.filter(value__contains=contains_character)

        except ValueError:
            return Response(
                {"error": "Invalid query parameter type — must be numeric where expected"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # --- Response Data ---
        data = [{
            "id": record.id,
            "value": record.value,
            "properties": record.properties,
            "created_at": record.created_at.isoformat(),
        } for record in records]

        filters_applied = {
            k: v for k, v in {
                "is_palindrome": is_palindrome,
                "min_length": min_length,
                "max_length": max_length,
                "word_count": word_count,
                "contains_character": contains_character
            }.items() if v is not None
        }

        return Response({
            "data": data,
            "count": len(data),
            "filters_applied": filters_applied
        }, status=status.HTTP_200_OK)



# GET or DELETE /strings/{string_value}
@api_view(['GET', 'DELETE'])
def string_detail(request, string_value):
    """
    GET: Retrieve a string record by its value.
    DELETE: Delete a string record by its value.
    """
    string_value = string_value.lower()
    
    try:
        record = StringRecord.objects.get(value=string_value)
    except StringRecord.DoesNotExist:
        return Response({"error": "String not found"}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        serializer = StringRecordSerializer(record)
        return Response(serializer.data, status=status.HTTP_200_OK)

    elif request.method == 'DELETE':
        record.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

# GET /strings/filter-by-natural-language
@api_view(['GET'])
def filter_by_natural_language(request):
    """
    Natural Language Filtering for String Records.
    
    Supported Queries:
      - "all single word palindromic strings" → word_count=1, is_palindrome=true
      - "strings longer than 10 characters" → min_length=11
      - "strings containing the letter z" → contains_character='z'
      - "palindromic strings" → is_palindrome=true
    
    Response (200 OK):
    {
        "data": [...],
        "count": <int>,
        "interpreted_query": {
            "original": <query>,
            "parsed_filters": { ... }
        }
    }
    """
    query = request.query_params.get('query')

    if not query:
        return Response(
            {"error": "Missing query parameter"},
            status=status.HTTP_400_BAD_REQUEST
        )

    query_lower = query.lower().strip()
    filters = {}
    interpreted_query = {
        "original": query,
        "parsed_filters": {}
    }

    # --- Pattern recognition ---
    if "single word" in query_lower and "palindromic" in query_lower:
        filters["properties__word_count"] = 1
        filters["properties__is_palindrome"] = True
        interpreted_query["parsed_filters"] = {
            "word_count": 1,
            "is_palindrome": True
        }

    elif "longer than" in query_lower and "characters" in query_lower:
        try:
            words = query_lower.split()
            number = next(int(w) for w in words if w.isdigit())
            min_length = number + 1
            filters["properties__length__gte"] = min_length
            interpreted_query["parsed_filters"] = {
                "min_length": min_length
            }
        except StopIteration:
            return Response(
                {"error": "Unable to parse numeric value in query"},
                status=status.HTTP_400_BAD_REQUEST
            )

    elif "containing the letter" in query_lower:
        try:
            # Extract character after the word 'letter'
            parts = query_lower.split("letter")
            letter = parts[-1].strip().replace("'", "").replace('"', '')
            if not letter:
                raise ValueError("No letter provided")
            filters["value__contains"] = letter
            interpreted_query["parsed_filters"] = {
                "contains_character": letter
            }
        except Exception:
            return Response(
                {"error": "Unable to parse letter from query"},
                status=status.HTTP_400_BAD_REQUEST
            )

    elif "palindromic" in query_lower:
        filters["properties__is_palindrome"] = True
        interpreted_query["parsed_filters"] = {
            "is_palindrome": True
        }

    else:
        return Response(
            {"error": "Unable to interpret natural language query"},
            status=status.HTTP_400_BAD_REQUEST
        )

    # --- Apply filters ---
    records = StringRecord.objects.filter(**filters)

    # --- Serialize ---
    data = [{
        "id": record.id,
        "value": record.value,
        "properties": record.properties,
        "created_at": record.created_at.isoformat(),
    } for record in records]

    response = {
        "data": data,
        "count": len(data),
        "interpreted_query": interpreted_query
    }

    return Response(response, status=status.HTTP_200_OK)