# Standard library imports
import os
from time import time, sleep
from typing import List, Dict
from random import randint

# Third-party imports
import numpy as np
from dotenv import load_dotenv
from pymongo import MongoClient
from openai import OpenAI
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer
from honeyhive import evaluate, evaluator, trace, enrich_span, enrich_session
import pkg_resources
print(f"HoneyHive version: {pkg_resources.get_distribution('honeyhive').version}")

# Load environment variables and initialize clients
load_dotenv()
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# MongoDB setup
client = MongoClient(os.getenv('MONGODB_URI'))
db = client['medical_db']
collection = db['articles']

# Model initialization
model = SentenceTransformer('all-MiniLM-L6-v2')

# Database operations
def setup_mongodb():
    """Initialize MongoDB with sample medical articles if empty"""
    if collection.count_documents({}) == 0:
        sample_articles = [
            {
                "title": "Exercise and Diabetes",
                "content": "Regular exercise reduces diabetes risk by 30%. Studies show that engaging in moderate physical activity for at least 30 minutes daily can help regulate blood sugar levels. Daily walking is particularly recommended for diabetes prevention.",
                "embedding": None  # Will be computed before insertion
            },
            {
                "title": "Morning Exercise Benefits",
                "content": "Studies show morning exercises have better impact on blood sugar levels. Research indicates that working out before breakfast can improve insulin sensitivity and help with weight management.",
                "embedding": None
            },
            {
                "title": "Diet and Diabetes",
                "content": "A balanced diet rich in fiber and low in refined carbohydrates can help prevent diabetes. Whole grains, vegetables, and lean proteins are essential components of a diabetes-prevention diet.",
                "embedding": None
            }
        ]

        # Compute and store embeddings
        for article in sample_articles:
            article["embedding"] = model.encode(article["content"]).tolist()

        collection.insert_many(sample_articles)

# Evaluation functions
@evaluator()
def consistency_evaluator(outputs, inputs, ground_truths):
    """Evaluates consistency between outputs and ground truths"""
    if not outputs or not ground_truths:
        return 0.0

    # Convert outputs and ground truths to lists if they're not already
    if isinstance(outputs, str):
        outputs = [outputs]
    if isinstance(ground_truths, dict):
        ground_truths = [ground_truths]

    output_embeddings = model.encode([str(o) for o in outputs])
    truth_embeddings = model.encode([str(g['response']) for g in ground_truths])

    # Calculate cosine similarity between outputs and ground truths
    similarities = cosine_similarity(output_embeddings, truth_embeddings)

    # Return average similarity
    return float(np.mean(similarities))

def retrieval_relevance_evaluator(query_embedding: np.ndarray, retrieved_embeddings: List[np.ndarray]) -> float:
    """Evaluates the relevance of retrieved documents to the query"""
    try:
        similarities = cosine_similarity([query_embedding], retrieved_embeddings)[0]
    except Exception as e:
        print(f"Error: {e}")
        return 0.0

    # Return average similarity
    return float(np.mean(similarities))

# RAG Pipeline components
@trace
def get_relevant_docs(query: str, top_k: int = 2):
    """Retrieves relevant documents from MongoDB using semantic search"""
    # Compute query embedding
    query_embedding = model.encode(query).tolist()
    retrieved_docs = []
    retrieved_embeddings = []

    try:
        # Search for similar documents using vector similarity
        pipeline = [
            {
                "$vectorSearch": {
                    "index": "vector_index",
                    "path": "embedding",
                    "queryVector": query_embedding,
                    "numCandidates": top_k * 2,  # Search through more candidates for better results
                    "limit": top_k
                }
            }
        ]

        results = list(collection.aggregate(pipeline))
        retrieved_docs = [doc["content"] for doc in results]
        retrieved_embeddings = [doc["embedding"] for doc in results]

    except Exception as e:
        print(f"Vector search error: {e}")
        # Fallback to basic find if vector search fails
        results = list(collection.find().limit(top_k))
        retrieved_docs = [doc["content"] for doc in results]
        retrieved_embeddings = [doc["embedding"] for doc in results]

    # Calculate and record metrics regardless of which path was taken
    if retrieved_embeddings:
        retrieval_relevance = retrieval_relevance_evaluator(query_embedding, retrieved_embeddings)
    else:
        retrieval_relevance = 0.0
    
    enrich_span(metrics={
        "retrieval_relevance": retrieval_relevance,
        "num_docs_retrieved": len(retrieved_docs)
    })

    return retrieved_docs

@trace
def generate_response(docs: List[str], query: str):
    """Generates response using OpenAI model"""
    prompt = f"Question: {query}\nContext: {docs}\nAnswer:"
    completion = openai_client.chat.completions.create(
        model="o3-mini",
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    return completion.choices[0].message.content

@trace
def rag_pipeline(inputs: Dict, ground_truths: Dict) -> str:
    """Complete RAG pipeline that retrieves docs and generates response"""
    query = inputs["query"]
    docs = get_relevant_docs(query)
    response = generate_response(docs, query)

    enrich_session(metrics={
        "rag_pipeline": {
            "num_retrieved_docs": len(docs),
            "query_length": len(query.split())   
        }
    })
    return response

# Test dataset
dataset = [
    {
        "inputs": {
            "query": "How does exercise affect diabetes?",
        },
        "ground_truths": {
            "response": "Regular exercise reduces diabetes risk by 30%. Daily walking is recommended.",
        }
    },
    {
        "inputs": {
            "query": "What are the benefits of morning exercise?",
        },
        "ground_truths": {
            "response": "Morning exercise has better impact on blood sugar levels.",
        }
    },
    {
        "inputs": {
            "query": "What is the best diet for diabetes?",
        },
        "ground_truths": {
            "response": "A balanced diet rich in fiber and low in refined carbohydrates is recommended.",
        }
    },
    {
        "inputs": {
            "query": "What is the best way to manage stress?",
        },
        "ground_truths": {
            "response": "Regular exercise, a balanced diet, and adequate sleep are effective ways to manage stress.",
        }
    },
    {
        "inputs": {
            "query": "How do sleep patterns affect mental health?",
        },
        "ground_truths": {
            "response": "Sleep patterns significantly impact mental well-being. Poor sleep can lead to increased anxiety and depression risks.",
        }
    },
    {
        "inputs": {
            "query": "How can stress management improve overall health?",
        },
        "ground_truths": {
            "response": "Effective stress management can improve overall health by reducing the risk of chronic diseases and improving mental well-being.",
        }
    },
    {
        "inputs": {
            "query": "What are common sleep disorders and their effects?",
        },
        "ground_truths": {
            "response": "Common sleep disorders include insomnia, sleep apnea, and restless legs syndrome, which can lead to fatigue, mood disturbances, and decreased cognitive function.",
        }
    },
    {
        "inputs": {
            "query": "How does morning exercise influence productivity?",
        },
        "ground_truths": {
            "response": "Morning exercise can boost productivity by enhancing mood, increasing energy levels, and improving focus throughout the day.",
        }
    },
    {
        "inputs": {
            "query": "What role does diet play in managing diabetes?",
        },
        "ground_truths": {
            "response": "A healthy diet is crucial in managing diabetes, as it helps control blood sugar levels and prevent complications.",
        }
    },
    {
        "inputs": {
            "query": "Can regular exercise reverse type 2 diabetes?",
        },
        "ground_truths": {
            "response": "Regular exercise, along with a healthy diet, can help reverse type 2 diabetes by improving insulin sensitivity and aiding weight loss.",
        }
    },
]

# Main execution
if __name__ == "__main__":
    # Setup MongoDB with sample data
    setup_mongodb()

    # Run experiment
    evaluate(
        function=rag_pipeline,
        api_key=os.getenv('HH_API_KEY'),
        project=os.getenv('HH_PROJECT'),
        name='MongoDB RAG Pipeline Evaluation',
        dataset=dataset,
        evaluators=[consistency_evaluator],
    )
