system_prompt:str = """
You are an expert AI assistant that creates advanced reasoning chains. For each step, provide a title and content that demonstrates your thought process. Respond in JSON format with 'title', 'content', and 'next_action' (either 'continue' or 'final_answer') keys. FOLLOW THESE GUIDELINES:
1. USE AT LEAST 5 REASONING STEPS, aiming for 10-20 steps for complex problems.
2. EMPLOY MULTIPLE METHODS: Use at least 3 distinct approaches to derive the answer.
3. EXPLORE ALTERNATIVES: Consider and analyze potential alternative answers.
4. CHALLENGE ASSUMPTIONS: Critically examine your own reasoning and initial conclusions.
5. ADDRESS LLM LIMITATIONS: Be aware of and compensate for typical AI shortcomings.
6. VISUALIZE WHEN POSSIBLE: If applicable, describe how you would visually represent the problem.
7. QUANTIFY CONFIDENCE: For each step and the final answer, provide a confidence level (0-100%).
8. CITE SOURCES: If referring to factual information, mention where you would source it from.
9. ETHICAL CONSIDERATIONS: If relevant, discuss any ethical implications of the problem or solution.
10. REAL-WORLD APPLICATION: Relate the problem or solution to practical, real-world scenarios.
11. NO ONLINE TOOLS AND SEARCHING: You cannot use online tools or search the internet.
12. YOUR RESPONSE MUST BE VALID JSON: This json response is essential for our job.

Example of a valid JSON response:
{
    "title": "Initial Problem Analysis",
    "content": "To begin solving this problem, I'll break it down into its core components...",
    "confidence": 90,
    "next_action": "continue"
}
"""




import json
import os
import requests
import streamlit as st
import time

# Get configuration from environment variables
OLLAMA_URL = os.getenv('OLLAMA_URL', 'ERROR: YOU MUST SET "OLLAMA_URL" IN YOUR ENVIRONMENT VARIBLES')
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'llama3.1:70b')
print(f'Got OLLAMA_URL: {OLLAMA_URL} and OLLAMA_MODEL: {OLLAMA_MODEL} from your settings')

if OLLAMA_MODEL != 'llama3.1:70b':
    print( f'[[WARN]]: Only OLLAMA_MODEL="llama3.1:70b is tested with this repo. Consider switch the model back if the performance is not good.' )

if OLLAMA_URL == 'ERROR: YOU MUST SET "OLLAMA_URL" IN YOUR ENVIRONMENT VARIBLES':
    print( f'[[ERROR]]: OLLAMA_URL is not set. Consider setting it in your enfironment variables.' )
    os.exit(1)


def make_api_call(messages, max_tokens, is_final_answer=False):
    for attempt in range(3):
        try:
            response = requests.post(
                f"{OLLAMA_URL}/api/chat",
                json={
                    "model": OLLAMA_MODEL,
                    "messages": messages,
                    "stream": False,
                    "format": "json", # important, or most of the time ollama does not generate valid json response
                    "options": {
                        "num_predict": max_tokens,
                        "temperature": 0.2
                    }
                }
            )
            print( f'Post request:\n{messages}\n' )
            response.raise_for_status()
            print( f'Response:\n{response.json()}\n' )
            return json.loads(response.json()["message"]["content"])
        except Exception as e:
            print( '\nFailed to retrieve json from response... trying again...\n' )
            if attempt == 2:
                if is_final_answer:
                    return {"title": "Error", "content": f"Failed to generate final answer after 3 attempts. Error: {str(e)}"}
                else:
                    return {"title": "Error", "content": f"Failed to generate step after 3 attempts. Error: {str(e)}", "next_action": "final_answer"}
            time.sleep(1)  # Wait for 1 second before retrying

def generate_response(prompt):
    messages = [ # add two sentences to encourage json format response
        {"role": "system", "content": """You are an expert AI assistant that explains your reasoning step by step. For each step, provide a title that describes what you're doing in that step, along with the content. Decide if you need another step or if you're ready to give the final answer. Respond in JSON format with 'title', 'content', and 'next_action' (either 'continue' or 'final_answer') keys. USE AS MANY REASONING STEPS AS POSSIBLE. AT LEAST 3. BE AWARE OF YOUR LIMITATIONS AS AN LLM AND WHAT YOU CAN AND CANNOT DO. IN YOUR REASONING, INCLUDE EXPLORATION OF ALTERNATIVE ANSWERS. CONSIDER YOU MAY BE WRONG, AND IF YOU ARE WRONG IN YOUR REASONING, WHERE IT WOULD BE. FULLY TEST ALL OTHER POSSIBILITIES. YOU CAN BE WRONG. WHEN YOU SAY YOU ARE RE-EXAMINING, ACTUALLY RE-EXAMINE, AND USE ANOTHER APPROACH TO DO SO. DO NOT JUST SAY YOU ARE RE-EXAMINING. USE AT LEAST 3 METHODS TO DERIVE THE ANSWER. USE BEST PRACTICES.

Example of a valid JSON response:
```json
{
    "title": "Identifying Key Information",
    "content": "To begin solving this problem, we need to carefully examine the given information and identify the crucial elements that will guide our solution process. This involves...",
    "next_action": "continue"
}```.
You MUST response using the expected json schema, and your response must be valid json. This JSON response is essential for our job.
"""},
        {"role": "user", "content": prompt},
        {"role": "assistant", "content": "Thank you! I will now think step by step following my instructions, starting at the beginning after decomposing the problem."}
    ]


    steps = []
    step_count = 1
    total_thinking_time = 0

    # First pass
    while True:
        start_time = time.time()
        step_data = make_api_call(messages, 512)
        end_time = time.time()
        thinking_time = end_time - start_time
        total_thinking_time += thinking_time

        steps.append((f"Step {step_count}: {step_data['title']}", step_data['content'], thinking_time))

        messages.append({"role": "assistant", "content": json.dumps(step_data)})

        if step_data['next_action'] == 'final_answer':
            break

        step_count += 1

        # Yield after each step for Streamlit to update
        yield steps, None  # We're not yielding the total time until the end

    # Second pass for recursive reasoning
    step_count = 1  # Reset step count for second pass
    messages = messages + [{"role": "user", "content": "Please re-examine your reasoning. Identify any weak points or alternative solutions you may have missed."}]

    while True:
        start_time = time.time()
        step_data = make_api_call(messages, 512)
        end_time = time.time()
        thinking_time = end_time - start_time
        total_thinking_time += thinking_time

        steps.append((f"Second Pass Step {step_count}: {step_data['title']}", step_data["content"], thinking_time))
        messages.append({"role": "assistant", "content": json.dumps(step_data)})

        if (step_data["next_action"] == "final_answer" or step_count > 10):  # Keep second pass limited to avoid excessive looping
            break

        step_count += 1
        yield steps, None  # Yield after each step for Streamlit to update

    # Generate final answer
    messages.append({"role": "user", "content": "Please provide the final answer based on your reasoning above."})

    start_time = time.time()
    final_data = make_api_call(messages, 512, is_final_answer=True)
    end_time = time.time()
    thinking_time = end_time - start_time
    total_thinking_time += thinking_time

    steps.append(("Final Answer", final_data['content'], thinking_time))

    yield steps, total_thinking_time





def main():
    st.set_page_config(page_title="ol1 prototype - Ollama version", page_icon="🧠", layout="wide")

    st.title("o_o: Using Ollama to create o1-like reasoning chains")
    st.markdown(""" This is an early prototype of using prompting to create o1-like reasoning chains to improve output accuracy. It is not perfect and accuracy has yet to be formally evaluated. It is powered by Ollama so that the reasoning step is local!  """)

    st.markdown(f"**Current Configuration:**")
    st.markdown(f"- Ollama URL: `{OLLAMA_URL}`")
    st.markdown(f"- Ollama Model: `{OLLAMA_MODEL}`")

    # Text input for user query
    user_query = st.text_input("Enter your query:", placeholder="e.g., How many 'R's are in the word strawberry?")

    if user_query:
        st.write("Generating response...")

        # Create empty elements to hold the generated text and total time
        response_container = st.empty()
        time_container = st.empty()

        # Generate and display the response
        for steps, total_thinking_time in generate_response(user_query):
            with response_container.container():
                for i, (title, content, thinking_time) in enumerate(steps):
                    if title.startswith("Final Answer"):
                        st.markdown(f"### {title}")
                        #st.markdown(content, unsafe_allow_html=True)
                        st.markdown(content.replace('```', '\n```'), unsafe_allow_html=True)
                    else:
                        with st.expander(title, expanded=True):
                            st.markdown(content.replace('\n', '<br>'), unsafe_allow_html=True)

            # Only show total time when it's available at the end
            if total_thinking_time is not None:
                time_container.markdown(f"**Total thinking time: {total_thinking_time:.2f} seconds**")

if __name__ == "__main__":
    main()
