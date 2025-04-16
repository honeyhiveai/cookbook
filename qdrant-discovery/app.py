import logging
import os
from dotenv import load_dotenv
from qdrant_client import models
import openai
import json
from typing import List, Tuple, Optional, Set, Dict

# Import retrieval functions
from retrieve import (
    get_embedding,
    query_by_context,
    get_random_quote,
    create_context_pairs
)
from honeyhive import HoneyHiveTracer, trace, enrich_session

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Load environment variables
load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    logger.warning("OPENAI_API_KEY environment variable not set. LLM calls will fail.")
else:
    openai.api_key = openai_api_key

@trace
def interpret_user_input_with_llm(
    user_input: str,
    current_quote: Optional[str] = None,
    num_examples: int = 3
) -> Dict[str, Optional[List[str]] | bool]:
    """
    Interprets user input, generates example quotes, and detects stop intent.
    
    Args:
        user_input: The user's input text
        current_quote: The current quote being discussed (if any)
        num_examples: Number of examples to generate for each category
        
    Returns:
        A dictionary containing:
        - positive_examples: List of example quotes matching preferences or None
        - negative_examples: List of example quotes to avoid or None
        - stop_requested: Boolean indicating if the user wants to stop
        
    Examples:
        "I like stoic quotes" -> {
            "positive_examples": [N stoic quotes],
            "negative_examples": None,
            "stop_requested": False
        }
        
        "Yes" (with current_quote) -> {
            "positive_examples": [current_quote + (N-1) similar quotes],
            "negative_examples": None,
            "stop_requested": False
        }
        
        "I like stoic quotes but not romantic ones" -> {
            "positive_examples": [N stoic quotes],
            "negative_examples": [N romantic quotes],
            "stop_requested": False
        }
        
        "ksajsoijehiuhs" -> {
            "positive_examples": None,
            "negative_examples": None,
            "stop_requested": False
        }

        "Ok, that's enough, let's stop" -> {
            "positive_examples": None,
            "negative_examples": None,
            "stop_requested": True
        }
    """
    system_prompt = (
        "You are an assistant helping to generate example motivational quotes based on user preferences "
        "and detecting if the user wants to end the conversation. "
        f"You should generate up to {num_examples} examples for each category when applicable.\n\n"
        "You must respond with valid JSON containing these keys:\n"
        "- positive_examples: list of example quotes or null\n"
        "- negative_examples: list of example quotes or null\n"
        "- stop_requested: boolean (true if the user wants to stop, false otherwise)\n\n"
        "Rules:\n"
        "1. If user expresses clear positive preferences, generate N matching examples for positive_examples\n"
        "2. If user shows approval of current quote, include it in positive examples and generate similar ones\n"
        "3. If user shows disapproval of current quote, include it in negative_examples. Then, generate N-1 *additional* examples *similar to the disliked quote* to bring the total negative examples to N. This step must be performed fully, even if the user also stated new positive preferences (Rule 1).\n"
        "4. If input is unclear/random, return null for examples and false for stop_requested\n"
        "5. Set stop_requested to true if the user expresses a clear desire to end the session (e.g., 'stop', 'I'm done', 'that's enough'). Otherwise, set it to false.\n"
        "6. Never generate more than the requested number of examples per category\n"
        "7. Keep quotes concise and impactful\n\n"
        "Example responses:\n\n"
        "For input 'I like stoic quotes':\n"
        "{\n"
        "  \"positive_examples\": [\n"
        "    \"The obstacle is the way.\",\n"
        "    \"What stands in the way becomes the way.\",\n"
        "    \"Focus on what you can control.\"\n"
        "  ],\n"
        "  \"negative_examples\": null,\n"
        "  \"stop_requested\": false\n"
        "}\n\n"
        "For input 'Yes!' with current_quote='Success is not final, failure is not fatal.':\n"
        "{\n"
        "  \"positive_examples\": [\n"
        "    \"Success is not final, failure is not fatal.\",\n"
        "    \"The only way to do great work is to love what you do.\",\n"
        "    \"Every setback is a setup for a comeback.\"\n"
        "  ],\n"
        "  \"negative_examples\": null,\n"
        "  \"stop_requested\": false\n"
        "}\n\n"
        "For input 'No, I don't like that one.' with current_quote='Love conquers all.' and num_examples=3:\n"
        "{\n"
        "  \"positive_examples\": null,\n"
        "  \"negative_examples\": [\n"
        "    \"Love conquers all.\",\n"
        "    \"All you need is love.\",\n"
        "    \"Love makes the world go round.\"\n"
        "  ],\n"
        "  \"stop_requested\": false\n"
        "}\n\n"
        "For input 'No, not that theme. I prefer quotes about perseverance.' with current_quote='Love conquers all.' and num_examples=3:\n"
        "{\n"
        "  \"positive_examples\": [\n"
        "    \"Perseverance is failing 19 times and succeeding the 20th.\",\n"
        "    \"It's not that I'm so smart, it's just that I stay with problems longer.\",\n"
        "    \"Success is the sum of small efforts, repeated day in and day out.\"\n"
        "  ],\n"
        "  \"negative_examples\": [\n"
        "    \"Love conquers all.\",\n"
        "    \"All you need is love.\",\n"
        "    \"Love makes the world go round.\"\n"
        "  ],\n"
        "  \"stop_requested\": false\n"
        "}\n\n"
        "For input 'gibberish text':\n"
        "{\n"
        "  \"positive_examples\": null,\n"
        "  \"negative_examples\": null,\n"
        "  \"stop_requested\": false\n"
        "}\n\n"
        "For input 'Okay, that's good for now, we can stop.':\n"
        "{\n"
        "  \"positive_examples\": null,\n"
        "  \"negative_examples\": null,\n"
        "  \"stop_requested\": true\n"
        "}"
    )
    
    # Default return value in case of errors
    default_response = {
        "positive_examples": None, 
        "negative_examples": None, 
        "stop_requested": False
    }

    try:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Current quote: {current_quote}\nUser input: {user_input}"}
        ]
        
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=messages,
            temperature=0.7,
            max_tokens=300
        )
        
        try:
            raw_response_content = response.choices[0].message.content
            logger.debug(f"Raw LLM response: {raw_response_content}")
            data = json.loads(raw_response_content)
            # Validate the response structure
            if not isinstance(data, dict):
                raise ValueError("Response is not a dictionary")
            if "positive_examples" not in data or "negative_examples" not in data or "stop_requested" not in data:
                raise ValueError("Response missing required keys")
            if not isinstance(data.get("stop_requested"), bool):
                 # Attempt to gracefully handle non-boolean but truthy/falsy values if needed, 
                 # or enforce strict boolean type. Let's enforce for now.
                 raise ValueError("stop_requested key must be a boolean")

            # Ensure we don't exceed the requested number of examples
            if data["positive_examples"] and isinstance(data["positive_examples"], list):
                data["positive_examples"] = data["positive_examples"][:num_examples]
            else:
                # Ensure key exists even if null or wrong type in response
                data["positive_examples"] = None 
                
            if data["negative_examples"] and isinstance(data["negative_examples"], list):
                data["negative_examples"] = data["negative_examples"][:num_examples]
            else:
                # Ensure key exists even if null or wrong type in response
                data["negative_examples"] = None
                
            logger.info(f"LLM interpretation: {data}")
            # Ensure all keys are present in the final return
            return {
                "positive_examples": data.get("positive_examples"),
                "negative_examples": data.get("negative_examples"),
                "stop_requested": data.get("stop_requested", False) # Default to False if missing after validation
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}. Response: {raw_response_content}")
            return default_response
        except ValueError as e:
            logger.error(f"Invalid response structure: {e}. Response: {raw_response_content}")
            return default_response

    except Exception as e:
        logger.error(f"Error in LLM interpretation: {e}")
        return default_response

def _initialize_agent() -> Optional[Tuple[models.PointStruct, Set[int]]]:
    """Initializes the agent state, prints welcome messages, and gets the first quote."""
    print("\n=== Motivational Quote Assistant ===")
    print("I'm here to help you discover motivational quotes that resonate with you!")
    print("You can tell me your preferences (e.g., 'I like stoic quotes, not romantic ones')")
    print("or give feedback on quotes I show you.")
    print("Type 'stop' when you've found quotes you like.")
    print("\nLet's start with a random quote to get your initial feedback...")
    
    try:
        initial_quote = get_random_quote()
        if not initial_quote:
            print("Sorry, I couldn't access the quote database. Please try again later.")
            return None
            
        seen_quote_ids: Set[int] = {initial_quote.id}
        logger.info(f"Initialized with quote ID: {initial_quote.id}")
        return initial_quote, seen_quote_ids
        
    except Exception as e:
        logger.error(f"Error getting initial quote: {e}")
        print("Sorry, I encountered an error during initialization. Please try again later.")
        return None

def _handle_user_interaction(current_quote_text: str) -> Tuple[str, Dict]:
    """Displays the current quote, gets user input, and returns the input and LLM interpretation."""
    print(f"\nQuote: \"{current_quote_text}\"")
    user_input = input("\nWhat do you think? (or type 'stop' to end): ").strip()
    interpretation = interpret_user_input_with_llm(user_input, current_quote_text, num_examples=3)
    return user_input, interpretation
    
def _update_embeddings_from_interpretation(
    interpretation: Dict,
    positive_embeddings: List[List[float]],
    negative_embeddings: List[List[float]]
):
    """Updates positive and negative embedding lists based on LLM interpretation."""
    if interpretation.get("positive_examples"):
        print("\nProcessing positive feedback...")
        for example in interpretation["positive_examples"]:
            try:
                embedding = get_embedding(example)
                positive_embeddings.append(embedding)
            except Exception as e:
                logger.error(f"Error getting embedding for positive example: {e}")
                continue
    
    if interpretation.get("negative_examples"):
        print("\nProcessing negative feedback...")
        for example in interpretation["negative_examples"]:
            try:
                embedding = get_embedding(example)
                negative_embeddings.append(embedding)
            except Exception as e:
                logger.error(f"Error getting embedding for negative example: {e}")
                continue

def _get_next_quote(
    positive_embeddings: List[List[float]],
    negative_embeddings: List[List[float]],
    seen_quote_ids: Set[int]
) -> Optional[models.PointStruct]:
    """Gets the next quote, either via context query or randomly, excluding seen quotes."""
    try:
        next_quote = None
        if positive_embeddings or negative_embeddings: # Check if *any* embeddings exist
            if positive_embeddings and negative_embeddings:
                 # We have context pairs to use
                print("\nSearching for quotes based on your feedback...")
                context_pairs = create_context_pairs(positive_embeddings, negative_embeddings)
                results = query_by_context(
                    context_pairs=context_pairs,
                    limit=5,
                    exclude_ids=list(seen_quote_ids)
                )
            elif positive_embeddings:
                # Only positive feedback available, use simple query
                print("\nSearching for similar quotes...")
                results = query_by_context(
                    context_pairs=[models.ContextExamplePair(positive=pos, negative=None) for pos in positive_embeddings],
                    limit=5,
                    exclude_ids=list(seen_quote_ids)
                )
            else: # Only negative feedback available
                print("\nTrying to find something different...")
                # Use negative examples to find dissimilar items (less direct with context pairs)
                # Could implement a negative-only query or fallback to random here.
                # For simplicity, falling back to random if only negative exists.
                results = [] # Force fallback to random if only negative

            # Pick first unseen quote from results
            for result in results:
                if result.id not in seen_quote_ids:
                    next_quote = result
                    break
                    
            if not next_quote and results:
                 print("\nFound similar quotes, but you've seen them all. Getting a random one.")
            elif not next_quote:
                print("\nCouldn't find a match based on feedback, getting a random quote.")

        if not next_quote:
            # If no context, not enough context, or context query failed/returned seen quotes
            print("\nLet me find another quote for you...")
            next_quote = get_random_quote(exclude_ids=list(seen_quote_ids))
            if not next_quote: # Handle case where random retrieval also fails
                print("Couldn't find any more quotes.")
                return None
                
        return next_quote
            
    except Exception as e:
        logger.error(f"Error getting next quote: {e}")
        print("\nSorry, I encountered an error getting the next quote. Let's try again.")
        return None # Indicate an error occurred


@trace
def run_agent():
    """Runs the conversational quote recommendation agent."""
    # --- Initialization ---
    initialization_result = _initialize_agent()
    if initialization_result is None:
        return 0 # Indicate initialization failure

    current_quote, seen_quote_ids = initialization_result
    current_quote_text = current_quote.payload.get("quote", "Quote text not available.")
    
    # --- State Variables ---
    positive_embeddings: List[List[float]] = []
    negative_embeddings: List[List[float]] = []
    round_count = 0

    # --- Main Conversation Loop ---
    while True:
        round_count += 1
        logger.info(f"Round {round_count}. Displaying quote ID: {current_quote.id}")

        # --- User Interaction & Interpretation ---
        try:
            user_input, interpretation = _handle_user_interaction(current_quote_text)
        except EOFError: # Handle Ctrl+D or unexpected end of input
            print("\nInput stream closed. Ending session.")
            break
        except Exception as e:
            logger.error(f"Error during user interaction: {e}")
            print("\nAn unexpected error occurred during interaction. Trying to continue...")
            continue # Attempt to recover by getting a new quote in the next iteration

        # --- Stop Condition ---
        if interpretation.get("stop_requested", False):
            print("\nOkay, stopping the session. Hope you found some inspiration!")
            break
            
        # --- Update Embeddings ---
        _update_embeddings_from_interpretation(
            interpretation, positive_embeddings, negative_embeddings
        )
        
        # --- Get Next Quote ---
        next_quote = _get_next_quote(positive_embeddings, negative_embeddings, seen_quote_ids)

        if next_quote is None:
            # Error occurred in _get_next_quote (already logged) or no more quotes available
            print("\nEnding session due to error or lack of suitable quotes.")
            break

        # --- Update State for Next Round ---
        current_quote = next_quote
        current_quote_text = current_quote.payload.get("quote", "Quote text not available.")
        seen_quote_ids.add(current_quote.id)


    print("\n=== Session Ended ===")
    return round_count

if __name__ == "__main__":
    # --- Run Agent ---
    HoneyHiveTracer.init(
        session_name="motivational_quote_assistant",
    )
    round_count = run_agent()
    print(f"Total rounds: {round_count}")
    enrich_session(
        metadata={"round_count": round_count}
    )
    HoneyHiveTracer.flush()