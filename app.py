import streamlit as st
from google import genai
from google.genai import types
import prompts
import smtplib
from email.mime.text import MIMEText

# 1. Page Configuration
st.set_page_config(page_title="Snap & Study", page_icon="🎓")

# 2. Get Secrets & Model Name
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
MODEL_NAME = "gemini-3.8-flash"

# 3. Cached Gemini Client Connection
@st.cache_resource
def get_gemini_client():
    return genai.Client(api_key=GEMINI_API_KEY)

gemini_client = get_gemini_client()

# Auto-clear stale session state from older model configurations
if "chat" in st.session_state and getattr(st.session_state.chat, "_model", None) != MODEL_NAME:
    del st.session_state["chat"]
    if "onboarded" in st.session_state:
        del st.session_state["onboarded"]
    st.rerun()

def send_email(to_address, subject, body):
    gmail_address = st.secrets["GMAIL_ADDRESS"]
    gmail_app_password = st.secrets["GMAIL_APP_PASSWORD"]

    message = MIMEText(body)
    message["Subject"] = subject
    message["From"] = gmail_address
    message["To"] = to_address

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(gmail_address, gmail_app_password)
        server.send_message(message)

# 4. Onboarding Screen Setup
if "onboarded" not in st.session_state:
    st.title("🎓 Snap & Study")
    st.caption("Upload homework or study notes. Get instant AI explanations!")

    with st.form("onboarding_form"):
        name = st.text_input("Your Name")
        recipient = st.text_input("Email / Delivery Address (for sending summaries)", placeholder="student@example.com")
        submitted = st.form_submit_button("Start Studying")

    if submitted:
        if not name.strip() or not recipient.strip():
            st.warning("Please fill in both fields before continuing.")
        else:
            st.session_state.name = name.strip()
            st.session_state.recipient = recipient.strip()
            
            st.session_state.chat = gemini_client.chats.create(
                model=MODEL_NAME,
                config=types.GenerateContentConfig(
                    system_instruction=prompts.SYSTEM_PROMPT
                )
            )
            
            st.session_state.onboarded = True
            st.rerun()

# 5. Main Chat Screen
else:
    st.title(f"Welcome, {st.session_state.name}!")
    
    if "messages" not in st.session_state:
        welcome_text = prompts.WELCOME_MESSAGE_TEMPLATE.format(name=st.session_state.name)
        st.session_state.messages = [{"role": "assistant", "content": welcome_text}]

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    uploaded_file = st.file_uploader("Upload a diagram, problem, or handwritten note", type=["jpg", "jpeg", "png"])
    user_prompt = st.chat_input("Ask a question about your study material...")

    if user_prompt:
        st.session_state.messages.append({"role": "user", "content": user_prompt})
        with st.chat_message("user"):
            st.markdown(user_prompt)

        contents = []
        if uploaded_file:
            image_bytes = uploaded_file.getvalue()
            contents.append(
                types.Part.from_bytes(
                    data=image_bytes,
                    mime_type=uploaded_file.type
                )
            )
            st.image(uploaded_file, caption="Uploaded Material", use_container_width=True)

        contents.append(user_prompt)

        with st.chat_message("assistant"):
            with st.spinner("Analyzing study material..."):
                try:
                    response = st.session_state.chat.send_message(contents)
                    st.markdown(response.text)
                    st.session_state.messages.append({"role": "assistant", "content": response.text})
                except Exception as e:
                    st.error(f"Error communicating with Gemini: {e}")

    st.divider()

    if st.button("Email Me Study Summary"):
        with st.spinner("Generating study summary..."):
            try:
                summary_response = st.session_state.chat.send_message(prompts.SUMMARY_REQUEST_PROMPT)
                summary_text = summary_response.text

                send_email(
                    to_address=st.session_state.recipient,
                    subject="Your Snap & Study Session Summary 🎓",
                    body=summary_text
                )
                st.success(f"Summary sent successfully to {st.session_state.recipient}!")
            except Exception as e:
                st.error(f"Failed to generate or send summary: {e}")