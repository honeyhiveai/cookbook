import openai
import os
from dotenv import load_dotenv
import logging
from qdrant_client import QdrantClient, models
from typing import List, Union, Optional
import random # Import random
from honeyhive import HoneyHiveTracer, trace, enrich_span

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Constants
COLLECTION_NAME = "quotes_collection"
EMBEDDING_MODEL = "text-embedding-3-small"

# Initialize OpenAI client
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    raise ValueError("OPENAI_API_KEY environment variable not set.")
openai.api_key = openai_api_key

client = QdrantClient(url="http://localhost:6333")

def get_embedding(text: str, model: str = EMBEDDING_MODEL) -> List[float]:
    """Generates embedding for a given text using the specified OpenAI model."""
    try:
        response = openai.embeddings.create(input=[text.replace("\n", " ")], model=model)
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"Failed to get embedding for text: {text[:50]}... Error: {e}")
        raise

def get_random_quote() -> List[models.ScoredPoint]:
    """
    Retrieves random quotes from the collection.

    Args:
        limit: Maximum number of quotes to return. Defaults to 1.

    Returns:
        List of ScoredPoint objects containing random quotes.
    """
    random_id = random.randint(0, 999)
    return client.query_points(
        collection_name=COLLECTION_NAME,
        query=random_id,
        with_payload=True
    ).points[0]

@trace
def query_by_context(
    context_pairs: List[models.ContextPair],
    limit: int = 10,
) -> List[models.ScoredPoint]:
    """
    Performs a Qdrant Context query using context pairs.

    Args:
        context_pairs: A list of positive/negative context pairs (models.ContextPair).
        limit: The maximum number of results to return.
        # exclude_ids: Optional list of point IDs to exclude from results. # Removed from docstring

    Returns:
        A list of ScoredPoint objects from the query results.
    """
    try:

        context_queries = [
            models.QueryRequest(
                query=models.ContextQuery(context=context_pairs),
                limit=limit,
                with_payload=True,
                with_vector=True,  # Include vectors in response
            ),
        ]

        logger.info(f"Performing Context query in collection '{COLLECTION_NAME}' with {len(context_pairs)} pairs...")
        results = client.query_batch_points(
            collection_name=COLLECTION_NAME,
            requests=context_queries
        )
        logger.info("Query finished.")
        
        # Return the points from the first (and only) query
        enrich_span(metadata={"number_pairs": len(context_pairs)})
        return results[0].points if results else []
        
    except Exception as e:
        logger.error(f"Error in query_by_context: {e}")
        raise

def create_context_pairs(
    positive_embeddings: List[List[float]],
    negative_embeddings: List[List[float]]
) -> List[models.ContextPair]:
    """
    Creates context pairs from positive and negative embedding lists.
    We are randomizing the pairings to avoid recommending the same quote when no additional context is given.
    
    Args:
        positive_embeddings: List of embeddings for positive examples
        negative_embeddings: List of embeddings for negative examples
        
    Returns:
        List of ContextPair objects matching positive and negative embeddings
    """
    len_pos = len(positive_embeddings)
    len_neg = len(negative_embeddings)
    min_len = min(len_pos, len_neg)

    if min_len == 0:
        return []

    # Take subsets of the embeddings up to the minimum length
    pos_subset = positive_embeddings[:min_len]
    neg_subset = negative_embeddings[:min_len]
    
    # If lists have different lengths, randomly sample from the longer list 
    # to match the length of the shorter list.
    if len_pos > min_len:
        pos_indices = random.sample(range(len_pos), min_len)
        pos_subset = [positive_embeddings[i] for i in pos_indices]
    elif len_neg > min_len:
        neg_indices = random.sample(range(len_neg), min_len)
        neg_subset = [negative_embeddings[i] for i in neg_indices]


    # Shuffle one of the lists (e.g., negative) to randomize pairing
    random.shuffle(neg_subset) 
    
    return [
        models.ContextPair(positive=pos, negative=neg)
        for pos, neg in zip(pos_subset, neg_subset)
    ]
