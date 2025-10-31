# Visio Network Diagram Analyzer

A Streamlit application that uses Snowflake Cortex Complete with Claude 3.5 Sonnet to analyze network diagrams from Visio files.

## Features

- Upload network diagrams (PNG/JPG format)
- Automatic upload to Snowflake internal stage
- Ask questions about the diagram using natural language
- Powered by Snowflake Cortex Complete multimodal with Claude 3.5 Sonnet
- Secure key-pair authentication to Snowflake
- Vision AI analyzes actual diagram images (not just text descriptions)

## Prerequisites

1. **Snowflake Account** with Cortex Complete enabled
2. **Key-Pair Authentication** set up for your Snowflake account
3. **Python 3.8+**

## Setup Instructions

### 1. Generate Key-Pair for Snowflake Authentication

If you haven't already, generate a key pair:

```bash
# Generate private key
openssl genrsa 2048 | openssl pkcs8 -topk8 -inform PEM -out rsa_key.p8 -nocrypt

# Generate public key
openssl rsa -in rsa_key.p8 -pubout -out rsa_key.pub
```

### 2. Add Public Key to Snowflake User

```sql
ALTER USER YOUR_USERNAME SET RSA_PUBLIC_KEY='YOUR_PUBLIC_KEY_STRING';
```

(Remove the header/footer and newlines from the public key file)

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Secrets

Edit `.streamlit/secrets.toml` with your Snowflake credentials:

```toml
[snowflake]
user = "YOUR_USERNAME"
account = "YOUR_ACCOUNT_IDENTIFIER"
warehouse = "YOUR_WAREHOUSE"
database = "YOUR_DATABASE"
schema = "YOUR_SCHEMA"
role = "YOUR_ROLE"
private_key_path = "/path/to/your/rsa_key.p8"
private_key_passphrase = ""  # Leave empty if no passphrase
```

### 5. Prepare Your Diagram

Export your Visio diagram as PNG or JPG:
- In Visio: File → Export → Change File Type → PNG/JPG
- Save the exported image

## Running the App

```bash
streamlit run app.py
```

The app will open in your browser at `http://localhost:8501`

## Usage

1. Upload your network diagram (PNG/JPG format)
2. Once uploaded, type questions about the diagram in the chat input
3. The AI will analyze the diagram and answer your questions

## Example Questions

- "What devices are shown in this network diagram?"
- "Describe the network topology"
- "What are the connections between the routers?"
- "Identify any potential security concerns in this network layout"
- "List all the IP addresses visible in the diagram"

## Notes

- The app uses Claude 3.5 Sonnet via Snowflake Cortex Complete **multimodal** function
- Images are uploaded to a Snowflake internal stage (`@network_diagrams`) for processing
- Uses the `TO_FILE()` function as per [Snowflake's multimodal documentation](https://docs.snowflake.com/en/sql-reference/functions/complete-snowflake-cortex-multimodal)
- Native Visio (.vsdx) files are not directly supported - export as PNG/JPG first
- Maximum image size: 3.75 MB for Claude 3.5 Sonnet
- Maximum resolution: 8000x8000 pixels
- Make sure your Snowflake account has Cortex Complete enabled

## Troubleshooting

**Connection Error**: Verify your Snowflake credentials and key-pair setup
**Cortex Error**: Ensure Cortex Complete is enabled in your Snowflake account
**Image Upload Error**: Make sure you're uploading PNG or JPG files

