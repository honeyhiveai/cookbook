import json

from honeyhive import evaluate

from langchain_chroma import Chroma
from langchain.chains import RetrievalQA
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings, ChatOpenAI


# Make sure you have the following environment variables set:
# OPENAI_API_KEY
# HH_API_KEY (create a project here: https://docs.honeyhive.ai/workspace/projects and get an API key here: https://docs.honeyhive.ai/sdk-reference/authentication)

DEBUG_MODE = True # only embed/benchmark a few documents and questions to debug quickly

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 100

NUM_DOCUMENTS = 100 if DEBUG_MODE else None
NUM_QUESTIONS = 20 if DEBUG_MODE else None

#######################
# Load the JSON files #
#######################

with open('rag-chromadb-cookbook-python/dataset.json', 'r', encoding='utf-8') as f:
    dataset = json.load(f)
# Load the corpus.json file
with open('rag-chromadb-cookbook-python/corpus.json', 'r', encoding='utf-8') as f:
    articles = json.load(f)
    
# Load the dataset.json file
with open('rag-chromadb-cookbook-python/dataset.json', 'r', encoding='utf-8') as f:
    dataset = json.load(f)

articles = articles[:NUM_DOCUMENTS] if NUM_DOCUMENTS else articles
dataset = dataset[:NUM_QUESTIONS] if NUM_QUESTIONS else dataset


##########################################
# Split the documents into small chunks  #
##########################################

# Prepare document texts and metadata
doc_texts = [article['body'] for article in articles]
doc_metadatas = [{key: article[key] or 'None' for key in article if key != 'body'} for article in articles]

# Initialize the text splitter
splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)

# Split the text into chunks
chunks = splitter.create_documents(doc_texts, doc_metadatas)
print(f'Created {len(chunks)} chunks')

##########################################
# Embed and upsert the chunks to Chroma  #
##########################################

# Initialize the embeddings model and Chroma DB
embeddings_model = OpenAIEmbeddings()
chroma_db = Chroma(embedding_function=embeddings_model)

# Embed and store the chunks in Chroma DB
chroma_db.add_documents(chunks)


##########################################
# Initialize the retriever and QA chain  #
##########################################

# Initialize the retriever
retriever = chroma_db.as_retriever(
    search_type="mmr", search_kwargs={"k": 1, "fetch_k": 5}
)

# Initialize the language model
llm = ChatOpenAI(model_name='gpt-4o', temperature=0)

# Initialize the QA chain
qa_chain = RetrievalQA.from_chain_type(llm=llm, retriever=retriever)

# Prepare the questions and ground truth answers
questions = [item['query'] for item in dataset]
ground_truth_answers = [item['answer'] for item in dataset]
query_list = [
    {
        'query': question,
        'ground_truth': ground_truth
    } for question, ground_truth in zip(questions, ground_truth_answers)
]

############################################
# Run the evaluation and print the results #
############################################

# To run HoneyHive evaluation
evaluate(
    function=qa_chain.invoke,
    hh_project='agi',
    name='QA Chain Evaluation',
    query_list=query_list
)

# For debugging, run the QA chain manually
# for question, ground_truth in zip(questions, ground_truth_answers):
#     answer = qa_chain.invoke(question)['result']
#     print("\nQuestion:", question)
#     print("Answer:", answer) 
#     print("Ground Truth:", ground_truth)
#     print("-" * 80)