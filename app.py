import streamlit as st
import snowflake.connector
from snowflake.connector import DictCursor
import io
from PIL import Image
import json
import tempfile
import os
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization

# Page config
st.set_page_config(page_title="Visio Diagram Analyzer", layout="centered")

# Title
st.title("Network Diagram Analyzer")
st.caption("Upload a Visio diagram and ask questions using Snowflake Cortex")

# Session state initialization
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'diagram_uploaded' not in st.session_state:
    st.session_state.diagram_uploaded = False
if 'stage_filename' not in st.session_state:
    st.session_state.stage_filename = None
if 'connection' not in st.session_state:
    st.session_state.connection = None

@st.cache_resource
def get_snowflake_connection():
    """Create Snowflake connection with key-pair authentication"""
    try:
        # Read private key
        with open(st.secrets["snowflake"]["private_key_path"], "rb") as key_file:
            p_key = serialization.load_pem_private_key(
                key_file.read(),
                password=st.secrets["snowflake"].get("private_key_passphrase", "").encode() if st.secrets["snowflake"].get("private_key_passphrase") else None,
                backend=default_backend()
            )

        pkb = p_key.private_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )

        conn = snowflake.connector.connect(
            user=st.secrets["snowflake"]["user"],
            account=st.secrets["snowflake"]["account"],
            private_key=pkb,
            warehouse=st.secrets["snowflake"]["warehouse"],
            database=st.secrets["snowflake"]["database"],
            schema=st.secrets["snowflake"]["schema"],
            role=st.secrets["snowflake"].get("role", None)
        )
        return conn
    except Exception as e:
        st.error(f"Failed to connect to Snowflake: {str(e)}")
        return None

def convert_visio_to_image(uploaded_file):
    """
    Convert Visio file to image. 
    Note: Visio files (.vsdx) are complex. Best approach is to export as PNG/JPG from Visio first.
    For this demo, we'll accept image files (PNG, JPG) of Visio diagrams.
    """
    try:
        # Check file type
        if uploaded_file.type in ['image/png', 'image/jpeg', 'image/jpg']:
            # Directly use the image
            img = Image.open(uploaded_file)
            return img
        else:
            st.warning("Please upload an image file (PNG/JPG) of your Visio diagram. Export your .vsdx file as an image first.")
            return None
    except Exception as e:
        st.error(f"Error processing file: {str(e)}")
        return None

def upload_image_to_stage(connection, image, filename):
    """Upload image to Snowflake stage for Cortex Complete processing
    Returns: (success: bool, actual_filename: str)
    """
    try:
        # Save image to bytes
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        image_bytes = buffered.getvalue()
        
        # Create stage if it doesn't exist with server-side encryption (required for Cortex)
        cursor = connection.cursor()
        cursor.execute("CREATE STAGE IF NOT EXISTS network_diagrams ENCRYPTION = (TYPE = 'SNOWFLAKE_SSE')")
        
        # Create a directory table for the stage (needed for TO_FILE)
        try:
            cursor.execute("ALTER STAGE network_diagrams SET DIRECTORY = (ENABLE = TRUE)")
        except:
            pass  # Directory might already be enabled
        
        # Save to temp file with the desired filename
        temp_dir = tempfile.gettempdir()
        local_path = os.path.join(temp_dir, filename)
        
        # Remove existing file if present to avoid conflicts
        if os.path.exists(local_path):
            os.remove(local_path)
            
        with open(local_path, 'wb') as f:
            f.write(image_bytes)
        
        try:
            # Upload to stage root (not in a subdirectory)
            put_command = f"PUT 'file://{local_path}' @network_diagrams OVERWRITE=TRUE AUTO_COMPRESS=FALSE"
            result = cursor.execute(put_command)
            
            # List files to get the actual uploaded filename
            cursor.execute("LIST @network_diagrams")
            files = cursor.fetchall()
            
            # Extract just the filename from the stage path
            stage_files = [f[0] for f in files]
            
            # Verify our file is there
            uploaded_filename = filename
            for file_path in stage_files:
                base_name = file_path.split('/')[-1]
                if base_name == filename:
                    uploaded_filename = base_name
                    break
            
            cursor.close()
            return True, uploaded_filename
                
        finally:
            # Clean up temp file
            if os.path.exists(local_path):
                os.remove(local_path)
                
    except Exception as e:
        st.error(f"Error uploading image to stage: {str(e)}")
        return False, None

def query_cortex_complete(connection, user_question, stage_filename):
    """Query Snowflake Cortex Complete with Claude model using multimodal support"""
    try:
        # Use the multimodal COMPLETE function with TO_FILE
        # Reference: https://docs.snowflake.com/en/sql-reference/functions/complete-snowflake-cortex-multimodal
        
        sql = """
        SELECT SNOWFLAKE.CORTEX.COMPLETE(
            'claude-3-5-sonnet',
            %s,
            TO_FILE('@network_diagrams', %s)
        ) as response
        """
        
        cursor = connection.cursor(DictCursor)
        cursor.execute(sql, (user_question, stage_filename))
        result = cursor.fetchone()
        cursor.close()
        
        if result and 'RESPONSE' in result:
            return result['RESPONSE']
        else:
            return "No response received from Cortex Complete"
            
    except Exception as e:
        st.error(f"Error querying Cortex: {str(e)}")
        return f"Error: {str(e)}"

# Main app layout
st.divider()

# File upload section
uploaded_file = st.file_uploader(
    "Upload Network Diagram (PNG/JPG)", 
    type=['png', 'jpg', 'jpeg'],
    help="Export your Visio diagram as PNG or JPG and upload it here"
)

if uploaded_file is not None:
    # Process the uploaded file
    image = convert_visio_to_image(uploaded_file)
    
    if image is not None:
        # Display the image
        st.image(image, caption="Uploaded Diagram", use_column_width=True)
        
        # Initialize connection if needed
        if st.session_state.connection is None:
            with st.spinner("Connecting to Snowflake..."):
                st.session_state.connection = get_snowflake_connection()
        
        if st.session_state.connection:
            # Upload image to Snowflake stage
            stage_filename = "diagram.png"
            with st.spinner("Uploading diagram to Snowflake..."):
                success, uploaded_filename = upload_image_to_stage(st.session_state.connection, image, stage_filename)
                if success and uploaded_filename:
                    st.session_state.stage_filename = uploaded_filename
                    st.session_state.diagram_uploaded = True
                    st.success("✓ Diagram uploaded successfully")
                else:
                    st.error("Failed to upload diagram to Snowflake stage")
        else:
            st.error("Unable to connect to Snowflake")

st.divider()

# Q&A Section
if st.session_state.diagram_uploaded:
    st.subheader("Ask Questions")
    
    # Initialize connection if not already done
    if st.session_state.connection is None:
        with st.spinner("Connecting to Snowflake..."):
            st.session_state.connection = get_snowflake_connection()
    
    if st.session_state.connection:
        # Display chat history
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.write(message["content"])
        
        # Chat input
        if prompt := st.chat_input("Ask a question about the diagram..."):
            # Add user message to chat
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.write(prompt)
            
            # Get AI response
            with st.chat_message("assistant"):
                with st.spinner("Analyzing..."):
                    response = query_cortex_complete(
                        st.session_state.connection,
                        prompt,
                        st.session_state.stage_filename
                    )
                    st.write(response)
            
            # Add assistant message to chat
            st.session_state.messages.append({"role": "assistant", "content": response})
    else:
        st.error("Unable to connect to Snowflake. Please check your configuration.")
else:
    st.info("👆 Upload a diagram to start asking questions")

# Clear chat button
if st.session_state.messages:
    if st.button("Clear Conversation"):
        st.session_state.messages = []
        st.rerun()

