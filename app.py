import streamlit as st
from google import genai
import prompts

# 1. Page Configuration
st.set_page_config(page_title="Snap & Study", page_icon="🎓")

# 2. Get Secrets & Model Name
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
MODEL_NAME = "gemini-2.5-flash"

# 3. Cached Gemini Client Connection
@st.cache_resource
def get_gemini_client():
    return genai.Client(api_key=GEMINI_API_KEY)

gemini_client = get_gemini_client()
import smtplib
from email.mime.text import MIMEText

def send_email(to_address, subject, body):
    # Retrieve sender credentials from secrets
    gmail_address = st.secrets["GMAIL_ADDRESS"]
    gmail_app_password = st.secrets["GMAIL_APP_PASSWORD"]

    # Construct the email message
    message = MIMEText(body)
    message["Subject"] = subject
    message["From"] = gmail_address
    message["To"] = to_address

    # Connect to Gmail SMTP server securely on port 465
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
        submitted = st.form_submit_button("Start Studying ")

    if submitted:
        if not name.strip() or not recipient.strip():
            st.warning("Please fill in both fields before continuing.")
        else:
            # Store student details in session state
            st.session_state.name = name.strip()
            st.session_state.recipient = recipient.strip()
            
            # Start a new Gemini chat session with our system prompt
            st.session_state.chat = gemini_client.chats.create(
                model=MODEL_NAME,
                config=genai.types.GenerateContentConfig(
                    system_instruction=prompts.SYSTEM_PROMPT
                )
            )
            
            # Save onboarding completion status
            st.session_state.onboarded = True
            st.rerun()
    # 5. Main Chat Screen (only displays after onboarding)
else:
    st.title(f" Welcome, {st.session_state.name}!")
    
    # Initialize message history list in session state if it doesn't exist
    if "messages" not in st.session_state:
        welcome_text = prompts.WELCOME_MESSAGE_TEMPLATE.format(name=st.session_state.name)
        st.session_state.messages = [{"role": "assistant", "content": welcome_text}]

    # Display past chat history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # File uploader for study material / homework photos
    uploaded_file = st.file_uploader("Upload a diagram, problem, or handwritten note", type=["jpg", "jpeg", "png"])
    
    # Chat input box
    user_prompt = st.chat_input("Ask a question about your study material...")

    if user_prompt:
        # Display user message in UI
        st.session_state.messages.append({"role": "user", "content": user_prompt})
        with st.chat_message("user"):
            st.markdown(user_prompt)

        # Prepare payload for Gemini (supports text + optional image)
        contents = []
        if uploaded_file:
            from PIL import Image
            img = Image.open(uploaded_file)
            contents.append(img)
            st.image(img, caption="Uploaded Material", use_container_width=True)

        contents.append(user_prompt)

        # Send request to Gemini and display AI response
        with st.chat_message("assistant"):
            with st.spinner("Analyzing study material..."):
                response = st.session_state.chat.send_message(contents)
                st.markdown(response.text)
                st.session_state.messages.append({"role": "assistant", "content": response.text})# 5. Main Chat Screen (only displays after onboarding)

                # Separator line
    st.divider()

    # Action Tool: Trigger email delivery of session summary
    if st.button(" Email Me Study Summary"):
        with st.spinner("Generating study summary..."):
            # 1. Ask Gemini to summarize the session history
            summary_response = st.session_state.chat.send_message(prompts.SUMMARY_REQUEST_PROMPT)
            summary_text = summary_response.text

            # 2. Try sending the email via SMTP
            try:
                send_email(
                    to_address=st.session_state.recipient,
                    subject="Your Snap & Study Session Summary 🎓",
                    body=summary_text
                )
                st.success(f"Summary sent successfully to {st.session_state.recipient}!")
            except Exception as e:
                st.error(f"Failed to send email: {e}")
  