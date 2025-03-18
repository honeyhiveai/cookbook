"""
A simple script to demonstrate tracing CrewAI operations with HoneyHive.
"""

import os
from typing import Dict, Any
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process
from honeyhive import HoneyHiveTracer, trace

# Load environment variables
load_dotenv()

# Initialize HoneyHive Tracer
HoneyHiveTracer.init(
    api_key=os.getenv("HONEYHIVE_API_KEY"),
    project=os.getenv("HONEYHIVE_PROJECT_NAME", "crewai-demo"),
    source=os.getenv("HONEYHIVE_SOURCE", "dev"),
    session_name="crewai-research-crew"
)

@trace
def create_agents() -> Dict[str, Agent]:
    """Create and return a dictionary of agents with specific roles."""
    
    researcher = Agent(
        role="Research Analyst",
        goal="Conduct comprehensive research on the given topic",
        backstory="You're a senior research analyst with expertise in gathering and analyzing information from various sources.",
        verbose=True,
        allow_delegation=False,
    )
    
    writer = Agent(
        role="Content Writer",
        goal="Create well-structured, informative content based on research findings",
        backstory="You're an experienced content writer known for your ability to transform complex information into clear, engaging content.",
        verbose=True,
        allow_delegation=False,
    )
    
    return {"researcher": researcher, "writer": writer}

@trace
def create_tasks(agents: Dict[str, Agent], research_topic: str) -> Dict[str, Task]:
    """Create and return a dictionary of tasks for the agents."""
    
    research_task = Task(
        description=f"Research the following topic thoroughly: {research_topic}. Find key information, statistics, and expert opinions.",
        expected_output="A comprehensive research document with key findings, statistics, and expert opinions.",
        agent=agents["researcher"]
    )
    
    writing_task = Task(
        description=f"Using the research provided, create a well-structured article about {research_topic}.",
        expected_output="A well-structured, comprehensive article ready for publication.",
        agent=agents["writer"],
        context=[research_task]
    )
    
    return {"research_task": research_task, "writing_task": writing_task}

@trace
def run_crew(agents: Dict[str, Agent], tasks: Dict[str, Task]) -> str:
    """Create and run a crew with the given agents and tasks."""
    
    crew = Crew(
        agents=list(agents.values()),
        tasks=[tasks["research_task"], tasks["writing_task"]],
        process=Process.sequential,
        verbose=True
    )
    
    return crew.kickoff()

@trace
def main() -> None:
    """Main function to run the CrewAI demonstration with HoneyHive tracing."""
    
    # Define the research topic
    research_topic = "The impact of artificial intelligence on healthcare"
    
    # Create agents and tasks
    agents = create_agents()
    tasks = create_tasks(agents, research_topic)
    
    # Run the crew and get the result
    result = run_crew(agents, tasks)
    
    # Print the final result
    print("\n=== FINAL RESULT ===\n")
    print(result)

if __name__ == "__main__":
    main() 