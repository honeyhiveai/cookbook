import openai
import streamlit as st
from honeyhive import HoneyHiveTracer, enrich_session
import os
from dotenv import load_dotenv

load_dotenv()

def init_honeyhive(update=False):
    if 'tracer' not in st.session_state or update:
        st.session_state.tracer = HoneyHiveTracer.init(
            api_key=os.getenv('HONEYHIVE_API_KEY'),
            project=os.getenv('HONEYHIVE_PROJECT'),
            session_name="Streamlit Session",
            server_url=os.getenv('HONEYHIVE_SERVER_URL')
        )
    return st.session_state.tracer

init_honeyhive()  # Initialize tracer in session state

def generate_response(query):
    client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "user", "content": query}
        ],
        temperature=0.7,
        max_tokens=500
    )
    if st.session_state.tracer.session_id:
        session_id = st.session_state.tracer.session_id
    else:
        session_id = None
    return {"response": response.choices[0].message.content, "session_id": session_id}

# Initialize session state variables
for key in ['current_query', 'current_feedback', 'current_response']:
    if key not in st.session_state:
        st.session_state[key] = None

def handle_feedback(feedback, session_id):
    enrich_session(feedback={"helpful": feedback}, session_id=session_id)
    st.session_state.current_feedback = feedback

# User input
new_query = st.text_input("Enter your query:")

# When user submits a new query
if new_query and new_query != st.session_state.current_query:
    init_honeyhive(update=True)  # Reinitialize if needed
    st.session_state.current_query = new_query
    st.session_state.current_feedback = None  # reset feedback
    st.session_state.current_response = generate_response(new_query)

# Display current response if available
if st.session_state.current_response:
    st.write(f"**Response:** {st.session_state.current_response['response']}")

    # Feedback buttons
    st.write("Was this response helpful?")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("👍"):
            handle_feedback(True, st.session_state.current_response['session_id'])
    with col2:
        if st.button("👎"):
            handle_feedback(False, st.session_state.current_response['session_id'])