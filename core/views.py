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
    value = request.data.get("value")
    if not isinstance(value, str):
        return Response({"error": "Invalid or missing 'value' field"}, status=status.HTTP_400_BAD_REQUEST)
    
    properties = analyze_string(value)
    if StringRecord.objects.filter(value=value).exists():
        return Response({"error": "String already exists"}, status=status.HTTP_409_CONFLICT)
    
    record = StringRecord.objects.create(
        value=value,
        sha256_hash=properties['sha256_hash'],
        properties=properties
    )
    serializer = StringRecordSerializer(record)
    return Response(serializer.data, status=status.HTTP_201_CREATED)

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
    queryset = StringRecord.objects.all()
    filters = {}

    is_palindrome = request.GET.get("is_palindrome")
    min_length = request.GET.get("min_length")
    max_length = request.GET.get("max_length")
    word_count = request.GET.get("word_count")
    contains_char = request.GET.get("contains_character")

    if is_palindrome is not None:
        queryset = [r for r in queryset if r.properties["is_palindrome"] == (is_palindrome.lower() == "true")]
        filters["is_palindrome"] = is_palindrome

    if min_length:
        queryset = [r for r in queryset if r.properties["length"] >= int(min_length)]
        filters["min_length"] = min_length

    if max_length:
        queryset = [r for r in queryset if r.properties["length"] <= int(max_length)]
        filters["max_length"] = max_length

    if word_count:
        queryset = [r for r in queryset if r.properties["word_count"] == int(word_count)]
        filters["word_count"] = word_count

    if contains_char:
        queryset = [r for r in queryset if contains_char in r.value]
        filters["contains_character"] = contains_char

    return Response({
        "data": StringRecordSerializer(queryset, many=True).data,
        "count": len(queryset),
        "filters_applied": filters
    })

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
