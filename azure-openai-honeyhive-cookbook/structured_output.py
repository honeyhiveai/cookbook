"""
This example demonstrates how to trace Azure OpenAI structured outputs with HoneyHive.
"""
import os
from pydantic import BaseModel, Field
from typing import List, Optional
from openai import AzureOpenAI
from honeyhive import HoneyHiveTracer, trace

# Initialize HoneyHive tracer at the beginning of your application
HoneyHiveTracer.init(
    api_key='your-honeyhive-api-key==',  # Replace with your actual HoneyHive API key
    project='Azure-OpenAI-traces'
)

# Initialize Azure OpenAI client
client = AzureOpenAI(
    api_version="2023-07-01-preview",
    azure_endpoint="https://your-endpoint.openai.azure.com",  # Replace with your Azure endpoint
)

# Define Pydantic models for structured outputs
class WeatherInfo(BaseModel):
    temperature: float = Field(description="Current temperature")
    unit: str = Field(description="Temperature unit (celsius or fahrenheit)")
    conditions: str = Field(description="Current weather conditions (e.g., sunny, cloudy, rainy)")
    humidity: int = Field(description="Humidity percentage")
    wind_speed: float = Field(description="Wind speed")
    forecast: List[str] = Field(description="Weather forecast for the next few days")

class Person(BaseModel):
    name: str = Field(description="Person's full name")
    age: int = Field(description="Person's age")
    occupation: str = Field(description="Person's occupation")
    email: Optional[str] = Field(None, description="Person's email address")
    skills: List[str] = Field(description="List of the person's skills")

# Simple JSON schema response format
@trace
def get_structured_json():
    """Get a structured JSON response using the response_format parameter."""
    try:
        response = client.chat.completions.create(
            model="deployment-name",  # Replace with your actual deployment name
            messages=[
                {"role": "system", "content": "You are a helpful assistant that provides weather information."},
                {"role": "user", "content": "What's the weather like in New York today?"}
            ],
            response_format={"type": "json_object"}
        )
        
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error: {e}")
        raise

# Using JSON schema for structured output
@trace
def get_json_schema_output():
    """Get a structured response using a JSON schema."""
    try:
        # Define a JSON schema
        json_schema = {
            "type": "object",
            "properties": {
                "location": {"type": "string"},
                "current_weather": {
                    "type": "object",
                    "properties": {
                        "temperature": {"type": "number"},
                        "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]},
                        "conditions": {"type": "string"},
                        "precipitation_chance": {"type": "number"}
                    },
                    "required": ["temperature", "unit", "conditions", "precipitation_chance"]
                },
                "forecast": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "day": {"type": "string"},
                            "temperature": {"type": "number"},
                            "conditions": {"type": "string"}
                        },
                        "required": ["day", "temperature", "conditions"]
                    }
                }
            },
            "required": ["location", "current_weather", "forecast"]
        }
        
        response = client.chat.completions.create(
            model="deployment-name",  # Replace with your actual deployment name
            messages=[
                {"role": "system", "content": "You are a helpful assistant that provides weather information."},
                {"role": "user", "content": "What's the weather like in London today and for the next 3 days?"}
            ],
            response_format={"type": "json_schema", "schema": json_schema}
        )
        
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error: {e}")
        raise

# Using Pydantic for structured output
@trace
def get_pydantic_structured_output():
    """Get a structured response using Pydantic models."""
    try:
        completion = client.beta.chat.completions.parse(
            model="deployment-name",  # Replace with your actual deployment name
            messages=[
                {"role": "system", "content": "You are a helpful assistant that extracts structured information."},
                {"role": "user", "content": "Extract information about this person: John Doe is a 32-year-old software engineer who specializes in Python, JavaScript, and cloud architecture. He can be reached at john.doe@example.com."}
            ],
            response_format=Person
        )
        
        # The parsed attribute contains the structured data
        person = completion.choices[0].message.parsed
        return person
    except Exception as e:
        print(f"Error: {e}")
        raise

# Using Pydantic for weather information
@trace
def get_weather_structured_output(location: str):
    """Get structured weather information for a location using Pydantic."""
    try:
        completion = client.beta.chat.completions.parse(
            model="deployment-name",  # Replace with your actual deployment name
            messages=[
                {"role": "system", "content": "You are a helpful assistant that provides weather information."},
                {"role": "user", "content": f"What's the weather like in {location} today?"}
            ],
            response_format=WeatherInfo
        )
        
        # The parsed attribute contains the structured data
        weather_info = completion.choices[0].message.parsed
        return weather_info
    except Exception as e:
        print(f"Error: {e}")
        raise

if __name__ == "__main__":
    # Get a simple JSON response
    json_response = get_structured_json()
    print("Simple JSON Response:")
    print(json_response)
    print("\n")
    
    # Get a JSON schema response
    json_schema_response = get_json_schema_output()
    print("JSON Schema Response:")
    print(json_schema_response)
    print("\n")
    
    # Get a Pydantic structured response
    try:
        person = get_pydantic_structured_output()
        print("Pydantic Person Response:")
        print(f"Name: {person.name}")
        print(f"Age: {person.age}")
        print(f"Occupation: {person.occupation}")
        print(f"Email: {person.email}")
        print(f"Skills: {', '.join(person.skills)}")
        print("\n")
    except Exception as e:
        print(f"Error with Pydantic Person: {e}")
    
    # Get weather information using Pydantic
    try:
        weather = get_weather_structured_output("Tokyo")
        print("Weather in Tokyo:")
        print(f"Temperature: {weather.temperature} {weather.unit}")
        print(f"Conditions: {weather.conditions}")
        print(f"Humidity: {weather.humidity}%")
        print(f"Wind Speed: {weather.wind_speed}")
        print(f"Forecast: {', '.join(weather.forecast)}")
    except Exception as e:
        print(f"Error with Weather Info: {e}")
    
    # You can view the traces in your HoneyHive dashboard
    print("\nView the traces in your HoneyHive dashboard!") 