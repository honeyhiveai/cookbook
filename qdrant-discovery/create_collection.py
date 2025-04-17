from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
from qdrant_client.models import PointStruct
import pandas as pd
import openai
import os
from dotenv import load_dotenv
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Constants
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "quotes_collection")
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536  # Dimension for text-embedding-3-small
MAX_DATAPOINTS = 1000 # Limit the number of points to process for upsert testing
EMBEDDINGS_FILE = "quotes_with_embeddings.parquet"

# Initialize OpenAI client
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    raise ValueError("OPENAI_API_KEY environment variable not set.")
openai.api_key = openai_api_key

client = QdrantClient(url="http://localhost:6333")

# Function to get embeddings
def get_embedding(text: str, model: str = EMBEDDING_MODEL) -> list[float]:
    """Generates embedding for a given text using the specified OpenAI model."""
    try:
        response = openai.embeddings.create(input=[text.replace("\n", " ")], model=model)
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"Failed to get embedding for text: {text[:50]}... Error: {e}")
        raise



df = pd.read_csv("inspiration.csv") # Renamed file, assuming this is correct

# print(df.head())
# print(df['Category'].unique())

df = df[["Quote", "Category"]]
logger.info("\nChecking for missing values in the DataFrame:")
logger.info(df.isnull().sum())
logger.info("\nChecking for duplicate quotes:")
duplicates = df['Quote'].duplicated().sum()
logger.info(f"{duplicates} duplicate quotes found")
logger.info(f"\nLength before dropping duplicates: {len(df)}")
df = df.drop_duplicates(subset=['Quote'])
df = df.reset_index(drop=True) # Reset index to get sequential IDs
logger.info(f"Length after dropping duplicates: {len(df)}")

logger.info(df.head())

# --- Embedding Generation or Loading ---

if os.path.exists(EMBEDDINGS_FILE):
    logger.info(f"Loading existing embeddings from {EMBEDDINGS_FILE}...")
    df_embeddings = pd.read_parquet(EMBEDDINGS_FILE)
    logger.info(f"Loaded {len(df_embeddings)} embeddings.")
else:
    logger.info("Generating embeddings as no pre-computed file found...")
    # Prepare data for the new DataFrame
    quotes_data = []
    # Process the entire DataFrame now
    total_rows = len(df)
    logger.info(f"Starting embedding generation for {total_rows} quotes...")
    for index, row in df.iterrows():
        try:
            embedding = get_embedding(row['Quote'])
            quotes_data.append({
                'id': index, # Use the sequential index after reset
                'quote': row['Quote'],
                'category': row['Category'],
                'embedding': embedding
            })
            if (index + 1) % 100 == 0: # Log progress every 100 points
                logger.info(f"Generated embeddings for {index + 1}/{total_rows} quotes...")
        except Exception as e:
            logger.error(f"Error processing row {index}: {e}. Skipping row.")

    if not quotes_data:
        raise SystemExit("No quotes were successfully embedded. Exiting.")

    # Create DataFrame with embeddings
    df_embeddings = pd.DataFrame(quotes_data)
    logger.info(f"Generated embeddings for {len(df_embeddings)} quotes. Saving to {EMBEDDINGS_FILE}...")
    try:
        df_embeddings.to_parquet(EMBEDDINGS_FILE, index=False)
        logger.info(f"Embeddings saved successfully to {EMBEDDINGS_FILE}.")
    except Exception as e:
        logger.error(f"Failed to save embeddings to Parquet file: {e}")
        # Decide if you want to proceed without saving or stop
        logger.warning("Proceeding with upsert without saving embeddings.")

# --- Collection Creation and Upsert --- 

# Recreate the collection (or create if it doesn't exist)
logger.info(f"Attempting to create or recreate collection: {COLLECTION_NAME}")
client.recreate_collection(
    collection_name=COLLECTION_NAME,
    vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
    timeout=300  # Optional: Increase timeout further for potentially larger upsert
)
logger.info(f"Collection '{COLLECTION_NAME}' created/recreated successfully.")

# Prepare points for upsert from the df_embeddings DataFrame
points_to_upsert = []

num_points_to_prepare = min(MAX_DATAPOINTS, len(df_embeddings))

logger.info(f"Preparing {num_points_to_prepare} points for upsert from DataFrame (limited by MAX_DATAPOINTS={MAX_DATAPOINTS})...")

for index, row in df_embeddings.head(num_points_to_prepare).iterrows(): # Limit points for upsert
    # Use the index from df_embeddings which should be sequential 0..N-1
    point_id = index
    point = PointStruct(
        id=point_id,
        vector=row['embedding'], # Get embedding from the DataFrame
        payload={"category": row['category'], "quote": row['quote']} # Get payload data
    )
    points_to_upsert.append(point)
    if (index + 1) % 500 == 0: # Log progress every 500 points during prep
         logger.info(f"Prepared {index + 1}/{len(df_embeddings)} points for upsert...")

logger.info(f"Generated {len(points_to_upsert)} points. Upserting to collection '{COLLECTION_NAME}'...")

# Upsert points
# Qdrant client handles batching internally, but monitor memory for very large datasets
try:
    operation_info = client.upsert(
        collection_name=COLLECTION_NAME,
        wait=True, # Wait for operation to complete
        points=points_to_upsert
    )
    logger.info("Upsert operation finished.")
    logger.info(operation_info)
except Exception as e:
    logger.error(f"Failed to upsert points: {e}")

logger.info("Script finished.")

