import os
import requests
import pandas as pd
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

HH_API_KEY = os.environ["HH_API_KEY"]
PROJECT = os.environ["HH_PROJECT"] # For example, "Lazard Sandbox"
SOURCE = "evaluation" 
HEADERS = {"Content-Type": "application/json", "Authorization": f"Bearer {HH_API_KEY}"} 

def get_data():
    financebench = pd.read_csv("Financebench.csv")
    datapoints = []
    for index, row in financebench.iterrows():
        datapoints.append({
            "input": row["question"],
            "context": row["evidence_text"],
            "answer": row["answer"]
        })
    return datapoints

def requests_retry_session(
    retries=10,
    backoff_factor=0.3,
    status_forcelist=(400, 500, 502, 503, 504),
    session=None,
    jitter_base=0.1,
):
    """
    Creates a requests session with retry logic including exponential backoff with jitter.

    Args:
        retries (int): Number of retries.
        backoff_factor (float): A base factor to apply for exponential backoff.
        status_forcelist (tuple): A set of HTTP status codes that we should force a retry on.
        session (requests.Session, optional): Use an existing session if provided, otherwise create a new one.
    
    Returns:
        requests.Session: A requests session configured with retry logic including jitter.
    """
    session = session or requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
        allowed_methods=["GET", "PUT", "POST"],
        raise_on_status=False, 
    )   
    
    def backoff_with_jitter(retry, *args, **kwargs):
        # Calculate the normal backoff
        backoff_value = retry.get_backoff_time()
        # Apply jitter by randomizing the backoff time
        jittered_backoff = backoff_value + random.uniform(0, jitter_base)
        return jittered_backoff
                
    # Override the backoff method
    retry.get_backoff_time = backoff_with_jitter
        
    adapter = HTTPAdapter(max_retries=retry) 
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session
        
def start_new_session():
    body = {
        "project": PROJECT,
        "source": SOURCE,
        "session_name": "LLM Session",
    }
    
    res = requests_retry_session().post(
        url="https://api.honeyhive.ai/session/start",
        headers=HEADERS,
        json=body,
    )
    return res.json()["session_id"]

def insert_event(input_test, context, answer):
    session_id = start_new_session()
    event = {
        "event_name": "LLM Event",
        "event_type": "model",
        "project": PROJECT,
        "source": SOURCE,
        "duration": 0,
        "config": {'type': 'generic'},
        "inputs": {'question': input_test, 'context': context},
        "outputs": {'answer': answer},
        "parent_id": session_id,
        "session_id": session_id,
    }
    
    requests_retry_session().post(
        url="https://api.honeyhive.ai/events",
        json={"event": event},
        headers=HEADERS,
    )

# Example usage:
if __name__ == "__main__":
    datapoints = get_data()
    counter = 0
    for datapoint in datapoints:
        insert_event(datapoint["input"], datapoint["context"], datapoint["answer"])
        counter += 1
        if counter > 10:
            break
