"""
This example demonstrates how to trace OpenAI structured outputs with HoneyHive.
"""
import os
from typing import List, Optional

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field

from honeyhive import HoneyHiveTracer, trace
from openinference.instrumentation.openai import OpenAIInstrumentor

load_dotenv(override=True)

# Initialize HoneyHive tracer and OpenAI auto-instrumentation
tracer = HoneyHiveTracer.init(
    api_key=os.getenv("HH_API_KEY"),
    project=os.getenv("HH_PROJECT", "OpenAI-traces"),
)
OpenAIInstrumentor().instrument(tracer_provider=tracer.provider)

# Initialize OpenAI client
client = OpenAI()


# Define Pydantic models for structured outputs
class WeatherInfo(BaseModel):
    temperature: float = Field(description="Current temperature")
    unit: str = Field(description="Temperature unit (celsius or fahrenheit)")
    conditions: str = Field(description="Current weather conditions")
    humidity: int = Field(description="Humidity percentage")
    forecast: List[str] = Field(description="Weather forecast for the next few days")


class Person(BaseModel):
    name: str = Field(description="Person's full name")
    age: int = Field(description="Person's age")
    occupation: str = Field(description="Person's occupation")
    email: Optional[str] = Field(None, description="Person's email address")
    skills: List[str] = Field(description="List of the person's skills")


@trace
def extract_person_info(text: str) -> Person:
    """Extract structured person information from text using Pydantic."""
    completion = client.beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that extracts structured information."},
            {"role": "user", "content": f"Extract information about this person: {text}"},
        ],
        response_format=Person,
    )
    return completion.choices[0].message.parsed


@trace
def get_weather_info(location: str) -> WeatherInfo:
    """Get structured weather information for a location using Pydantic."""
    completion = client.beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that provides weather information."},
            {"role": "user", "content": f"What's the weather like in {location} today?"},
        ],
        response_format=WeatherInfo,
    )
    return completion.choices[0].message.parsed


if __name__ == "__main__":
    person = extract_person_info(
        "John Doe is a 32-year-old software engineer who specializes in Python, "
        "JavaScript, and cloud architecture. He can be reached at john.doe@example.com."
    )
    print("Person Info:")
    print(f"  Name: {person.name}")
    print(f"  Age: {person.age}")
    print(f"  Occupation: {person.occupation}")
    print(f"  Email: {person.email}")
    print(f"  Skills: {', '.join(person.skills)}")

    print()

    weather = get_weather_info("Tokyo")
    print("Weather in Tokyo:")
    print(f"  Temperature: {weather.temperature} {weather.unit}")
    print(f"  Conditions: {weather.conditions}")
    print(f"  Humidity: {weather.humidity}%")
    print(f"  Forecast: {', '.join(weather.forecast)}")

    print("\nView the traces in your HoneyHive dashboard!")
