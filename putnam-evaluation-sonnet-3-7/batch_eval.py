import os
import json
import time
import argparse
from concurrent.futures import ThreadPoolExecutor
from anthropic import Anthropic

# Replace with your actual Anthropic API key
ANTHROPIC_API_KEY = 'your anthropic api key'
os.environ["ANTHROPIC_API_KEY"] = ANTHROPIC_API_KEY

# Initialize the Anthropic client
anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY)

def load_problems(file_path, problem_ids=None):
    """
    Load problems from the JSONL file.
    If problem_ids is provided, only load those specific problems.
    """
    problems = []
    with open(file_path, 'r') as f:
        for line in f:
            problem = json.loads(line)
            if problem_ids is None or problem.get('question_id') in problem_ids:
                problems.append(problem)
    return problems

def solve_problem(problem, thinking_budget=16000):
    """Solve a single Putnam problem using Claude 3.7 Sonnet with thinking enabled."""
    print(f"Processing problem {problem['question_id']}: {problem['question_category']}")
    
    try:
        # Create the completion with thinking enabled
        completion = anthropic_client.messages.create(
            model="claude-3-7-sonnet-20250219",
            max_tokens=20000,
            thinking={
                "type": "enabled",
                "budget_tokens": thinking_budget
            },
            messages=[
                {"role": "user", "content": problem['question']}
            ]
        )
        
        # Extract the thinking content and final response
        thinking_content = ""
        final_response = ""
        
        for content_block in completion.content:
            if content_block.type == "thinking":
                thinking_content += content_block.thinking
            elif content_block.type == "text":
                final_response += content_block.text
        
        # Return the results
        return {
            "problem_id": problem['question_id'],
            "category": problem['question_category'],
            "question": problem['question'],
            "thinking": thinking_content,
            "solution": final_response,
            "ground_truth": problem['solution'],
            "status": "success"
        }
    
    except Exception as e:
        print(f"Error processing problem {problem['question_id']}: {str(e)}")
        return {
            "problem_id": problem['question_id'],
            "category": problem['question_category'],
            "question": problem['question'],
            "thinking": "",
            "solution": "",
            "ground_truth": problem['solution'],
            "status": "error",
            "error": str(e)
        }

def batch_evaluate(problems, output_dir="results", max_workers=3, thinking_budget=16000):
    """
    Evaluate multiple problems in parallel using a thread pool.
    
    Args:
        problems: List of problem dictionaries to evaluate
        output_dir: Directory to save results
        max_workers: Maximum number of concurrent workers
        thinking_budget: Number of tokens to allocate for thinking
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    results = []
    start_time = time.time()
    
    # Process problems in parallel
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all problems to the executor
        future_to_problem = {
            executor.submit(solve_problem, problem, thinking_budget): problem 
            for problem in problems
        }
        
        # Process results as they complete
        for i, future in enumerate(future_to_problem):
            problem = future_to_problem[future]
            try:
                result = future.result()
                results.append(result)
                
                # Save individual result
                with open(f"{output_dir}/result_{result['problem_id']}.json", 'w') as f:
                    json.dump(result, f, indent=2)
                
                print(f"Completed {i+1}/{len(problems)}: Problem {result['problem_id']}")
            
            except Exception as e:
                print(f"Error processing problem {problem['question_id']}: {str(e)}")
                results.append({
                    "problem_id": problem['question_id'],
                    "status": "error",
                    "error": str(e)
                })
    
    # Calculate total time
    total_time = time.time() - start_time
    
    # Save all results to a single file
    with open(f"{output_dir}/all_results.json", 'w') as f:
        json.dump({
            "results": results,
            "total_time": total_time,
            "problems_count": len(problems),
            "success_count": sum(1 for r in results if r.get("status") == "success"),
            "error_count": sum(1 for r in results if r.get("status") == "error"),
        }, f, indent=2)
    
    print(f"\nEvaluation completed in {total_time:.2f} seconds")
    print(f"Results saved to {output_dir}/all_results.json")
    
    return results

def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(description="Batch evaluate Putnam problems using Claude 3.7 Sonnet with thinking")
    parser.add_argument("--input", default="putnam_2023.jsonl", help="Input JSONL file with problems")
    parser.add_argument("--output", default="results", help="Output directory for results")
    parser.add_argument("--problems", nargs="+", help="Specific problem IDs to evaluate (e.g., A1 B2)")
    parser.add_argument("--workers", type=int, default=3, help="Maximum number of concurrent workers")
    parser.add_argument("--thinking-budget", type=int, default=16000, help="Token budget for thinking")
    
    args = parser.parse_args()
    
    # Load problems
    problems = load_problems(args.input, args.problems)
    
    if not problems:
        print("No problems found!")
        return
    
    print(f"Loaded {len(problems)} problems for evaluation")
    
    # Run batch evaluation
    batch_evaluate(
        problems, 
        output_dir=args.output,
        max_workers=args.workers,
        thinking_budget=args.thinking_budget
    )

if __name__ == "__main__":
    main() 