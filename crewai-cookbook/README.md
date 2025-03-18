# CrewAI with HoneyHive Tracing

This repository demonstrates how to use HoneyHive to trace, monitor, and evaluate CrewAI agent operations. The sample scripts set up simple crews with tracing and evaluation enabled via HoneyHive's SDK.

## Overview

[CrewAI](https://github.com/crewAI/crewAI) is a framework for orchestrating role-playing autonomous AI agents. It allows developers to create agents with specific roles, goals, and backstories, and organize them into crews to collaborate on tasks.

[HoneyHive](https://www.honeyhive.ai/) is an observability platform for AI applications. It allows developers to trace, monitor, evaluate, and debug their AI applications, including LLM calls, tool usage, and more.

This example shows how to integrate CrewAI with HoneyHive to gain visibility into agent operations, task execution, and overall crew performance, as well as to evaluate the quality of results.

## Features

- Tracing of CrewAI agent creation, task creation, and crew execution
- Visualization of agent operations in HoneyHive's dashboard
- Performance monitoring and debugging capabilities
- Automatic instrumentation of LLM calls made by CrewAI agents
- Tracing of custom tools used by agents
- Evaluation of crew outputs using HoneyHive's evaluation capabilities

## Prerequisites

- Python 3.9+
- A HoneyHive account and API key
- An OpenAI API key (or other LLM provider key supported by CrewAI)

## Installation

1. Clone this repository:
   ```bash
   git clone <repository-url>
   cd crewai-cookbook
   ```

2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Copy the example environment file and add your API keys:
   ```bash
   cp env.example .env
   ```
   Then edit the `.env` file to add your API keys and configuration.

## Usage

### Basic Example

Run the basic example script:

```bash
python trace_crewai.py
```

This will:
1. Initialize the HoneyHive tracer
2. Create two CrewAI agents: a researcher and a writer
3. Define tasks for each agent
4. Run the crew with sequential task execution
5. Trace all operations and send the data to HoneyHive

### Advanced Example

The repository also includes a more advanced example with custom tools:

```bash
python advanced_trace_example.py
```

This advanced example:
1. Sets up a more complex crew with three agents: market analyst, financial analyst, and strategic advisor
2. Defines and traces custom tools for company research, market trend analysis, and financial data retrieval
3. Creates interdependent tasks that build on each other's outputs
4. Adds custom attributes to traces for better filtering and analysis
5. Demonstrates a more realistic business use case

### Evaluation Example

For evaluating the quality of your CrewAI outputs:

```bash
python evaluate_crew_results.py
```

This evaluation example:
1. Sets up a simple research and writing crew
2. Runs the crew to generate content on a specified topic
3. Evaluates the generated content using HoneyHive's evaluation capabilities
4. Scores the output on multiple criteria such as relevance, accuracy, completeness, readability, and actionability
5. Records evaluation results in the HoneyHive trace for further analysis

## Viewing Traces and Evaluations in HoneyHive

After running any of the scripts:

1. Log in to your [HoneyHive dashboard](https://app.honeyhive.ai/)
2. Navigate to your project (default: "crewai-demo", "crewai-advanced-demo", or "crewai-eval-demo")
3. Go to the "Traces" tab to see the details of your CrewAI execution and evaluation
4. Click on any trace to see detailed information about the execution, including:
   - Agent creation and configuration
   - Task definition and parameters
   - Task execution flow
   - LLM calls made by agents
   - Tool usage and inputs/outputs
   - Execution time and performance metrics
   - Evaluation scores and explanations (if using the evaluation script)

## Customization

You can customize these examples in several ways:

- Change the research topic or company to analyze
- Add more agents with different roles
- Create new custom tools and integrate them with the tracing
- Modify the task descriptions and expected outputs
- Change the crew process (sequential, hierarchical, etc.)
- Add more tracing decorators to other functions
- Add custom attributes to spans for better filtering
- Modify the evaluation criteria and prompts

## Best Practices for Tracing with HoneyHive

When tracing CrewAI applications with HoneyHive:

1. Trace all key functions with the `@trace` decorator
2. Use descriptive session names for better organization
3. Add custom attributes to important spans
4. Trace custom tools to understand their usage and performance
5. Use HoneyHive's dashboard to identify bottlenecks and optimization opportunities
6. Compare different runs to measure improvements
7. Evaluate outputs to measure quality and track improvements over time

## Troubleshooting

If you encounter issues:

1. Ensure your API keys are correctly set in the `.env` file
2. Check that you have the latest versions of the required packages
3. Verify that your HoneyHive project is correctly configured
4. Look for error messages in the console output
5. Check the HoneyHive dashboard for any errors or warnings

## Further Resources

- [CrewAI Documentation](https://docs.crewai.com/)
- [HoneyHive Documentation](https://docs.honeyhive.ai/)
- [OpenTelemetry Documentation](https://opentelemetry.io/docs/)
