"""
Example of evaluating CrewAI results with HoneyHive evaluators.
"""

import os
import json
from typing import Dict, Any
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process
from honeyhive import HoneyHiveTracer, trace, evaluate, enrich_span, enrich_session

# Load environment variables
load_dotenv()

# Initialize HoneyHive Tracer
HoneyHiveTracer.init(
    api_key=os.getenv("HONEYHIVE_API_KEY"),
    project=os.getenv("HONEYHIVE_PROJECT_NAME", "crewai-eval-demo"),
    source=os.getenv("HONEYHIVE_SOURCE", "dev"),
    session_name="crewai-evaluation-example"
)

# Define evaluation criteria
EVALUATION_CRITERIA = {
    "relevance": "How relevant is the output to the requested topic?",
    "accuracy": "How accurate and factual is the information provided?",
    "completeness": "How complete is the analysis, covering all important aspects?",
    "readability": "How readable and well-structured is the output?",
    "actionability": "How actionable are the insights or recommendations?"
}

@trace
def create_agents() -> Dict[str, Agent]:
    """Create and return a dictionary of agents with specific roles."""
    
    researcher = Agent(
        role="Research Analyst",
        goal="Conduct comprehensive research on the given topic",
        backstory="You're a senior research analyst with expertise in gathering and analyzing information from various sources.",
        verbose=True,
        allow_delegation=False,  # Disable delegation for simpler sequential processing
    )
    
    writer = Agent(
        role="Content Writer",
        goal="Create well-structured, informative content based on research findings",
        backstory="You're an experienced content writer known for your ability to transform complex information into clear, engaging content.",
        verbose=True,
        allow_delegation=False,  # Disable delegation for simpler sequential processing
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
def evaluate_result(result: str, topic: str) -> Dict[str, Any]:
    """Evaluate the result using HoneyHive evaluators with an LLM as judge."""
    
    # Set up evaluation context
    evaluation_context = {
        "topic": topic,
        "output": result
    }
    
    # Evaluate each criterion
    evaluation_results = {}
    
    # Create a comprehensive prompt for the LLM judge
    judge_prompt = f"""
    # LLM Judge Evaluation Task
    
    You are an expert judge tasked with evaluating the quality of an AI-generated article on "{topic}".
    
    ## Article to Evaluate:
    {result}
    
    ## Evaluation Criteria:
    Please evaluate the article on the following criteria, scoring each on a scale of 1-10 (where 10 is excellent):
    
    1. Relevance: How relevant is the content to the topic? (1-10)
    2. Accuracy: How accurate and factual is the information provided? (1-10)
    3. Completeness: How comprehensive is the coverage of important aspects? (1-10)
    4. Readability: How well-structured and easy to understand is the writing? (1-10)
    5. Actionability: How useful and actionable are the insights provided? (1-10)
    
    ## Instructions:
    For each criterion:
    - Provide a numerical score (1-10)
    - Include a brief explanation of your reasoning
    - Highlight specific examples from the text to support your assessment
    
    ## Output Format:
    {{"relevance": {{"score": X, "explanation": "Your explanation"}},
     "accuracy": {{"score": X, "explanation": "Your explanation"}},
     "completeness": {{"score": X, "explanation": "Your explanation"}},
     "readability": {{"score": X, "explanation": "Your explanation"}},
     "actionability": {{"score": X, "explanation": "Your explanation"}}}}
    
    Important: Provide your response in valid JSON format only.
    """
    
    # Use evaluate to get the LLM judge's assessment
    judge_result = evaluate(
        evaluator_name="openai/gpt-4o",  # Using GPT-4o as the evaluator
        prompt=judge_prompt,
        output=result,
        metadata={
            "evaluation_type": "llm_judge",
            "topic": topic
        }
    )
    
    # Parse the evaluation result
    try:
        evaluation_results = json.loads(judge_result)
    except json.JSONDecodeError:
        # Fallback if the LLM doesn't return valid JSON
        evaluation_results = {}
        for criterion in EVALUATION_CRITERIA.keys():
            evaluation_results[criterion] = {
                "score": 5,  # Default middle score
                "explanation": f"Failed to parse LLM judge's evaluation for {criterion}"
            }
    
    # Add the scores to the span metrics
    for criterion, result_data in evaluation_results.items():
        enrich_span(metrics={f"evaluation_{criterion}_score": result_data["score"]})
    
    # Calculate the average score
    scores = [result_data["score"] for result_data in evaluation_results.values()]
    average_score = sum(scores) / len(scores) if scores else 0
    
    # Add all evaluation results to the session
    enrich_session(metrics={
        "evaluation_average_score": average_score,
        "evaluation_details": evaluation_results,
        "evaluation_method": "llm_judge"
    })
    
    # Return the evaluation results
    return {
        "results": evaluation_results,
        "average_score": average_score
    }

@trace
def main() -> None:
    """Main function to run the CrewAI demonstration with HoneyHive evaluation."""
    
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
    
    # Evaluate the result
    print("\n=== EVALUATING RESULT ===\n")
    evaluation = evaluate_result(result, research_topic)
    
    # Print the evaluation results
    print("\n=== EVALUATION RESULTS ===\n")
    for criterion, data in evaluation["results"].items():
        print(f"{criterion.capitalize()}: {data['score']}/10")
        print(f"Explanation: {data['explanation']}")
        print()
    
    print(f"Average Score: {evaluation['average_score']:.2f}/10")

if __name__ == "__main__":
    main() 