# Q&A Agent with Document Upload

A Django-based Q&A agent that answers questions from uploaded PDF documents using LangChain, OpenAI embeddings, FAISS vector store, and Anthropic Claude.

## Features

- 📄 Upload PDF documents
- 🔍 Semantic search using OpenAI embeddings
- 💬 Real-time chat interface via WebSockets
- 📚 Answer questions based on uploaded documents only
- 🔗 Source references for answers

## Setup

1. **Create and activate virtual environment:**
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. **Install dependencies:**
```bash
pip install -r requirements.txt
```

3. **Set up environment variables:**
Create a `.env` file in the project root with your API keys:
```bash
# Create .env file
cat > .env << EOF
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
EOF
```
Replace `your_openai_api_key_here` and `your_anthropic_api_key_here` with your actual API keys.

4. **Run migrations:**
```bash
python manage.py migrate
```

5. **Create superuser (optional):**
```bash
python manage.py createsuperuser
```

6. **Run the development server:**
   
   **Important:** For WebSocket support, you must run the server with daphne (ASGI server):
```bash
daphne -b 0.0.0.0 -p 8000 qa_agent.asgi:application
```
   
   Or use the provided script:
```bash
./run_server.sh
```
   
   **Note:** The regular `python manage.py runserver` may not properly handle WebSocket connections. Use daphne for reliable WebSocket support.

7. **Access the application:**
- Chat interface: http://localhost:8000
- Admin panel: http://localhost:8000/admin

## Docker Setup (Alternative)

You can also run the application using Docker and Docker Compose:

1. **Create `.env` file:**
   ```bash
   cat > .env << EOF
   OPENAI_API_KEY=your_openai_api_key_here
   ANTHROPIC_API_KEY=your_anthropic_api_key_here
   EOF
   ```
   Replace the placeholder values with your actual API keys.

2. **Build and run with Docker Compose:**
   ```bash
   docker-compose up --build
   ```
   
   This will:
   - Build the Docker image
   - Start the Django application
   - Start a Redis container (for Channels)
   - Run database migrations automatically

3. **Access the application:**
   - Chat interface: http://localhost:8000
   - Admin panel: http://localhost:8000/admin

4. **Stop the containers:**
   ```bash
   docker-compose down
   ```

5. **View logs:**
   ```bash
   docker-compose logs -f web
   ```

**Note:** The Docker setup includes Redis for Django Channels. If you want to use Redis in your local setup, update `CHANNEL_LAYERS` in `qa_agent/settings.py` to use Redis instead of InMemoryChannelLayer.

## Usage

1. Open the chat interface in your browser
2. Upload a PDF document using the upload button
3. Wait for the document to be processed (embeddings generated)
4. Ask questions about the document
5. The agent will answer based only on the uploaded documents and provide source references

## Technology Stack

- **Django**: Web framework
- **Django Channels**: WebSocket support
- **LangChain**: Document processing and retrieval
- **OpenAI Embeddings**: Text embeddings (text-embedding-3-small)
- **FAISS**: Vector store for embeddings
- **Anthropic Claude**: LLM for answer generation

## Project Structure

```
genai-project/
├── manage.py
├── requirements.txt
├── .env.example
├── qa_agent/          # Django project settings
├── documents/          # Main app
│   ├── models.py       # Document model
│   ├── views.py        # Upload endpoint
│   ├── consumers.py    # WebSocket consumer
│   ├── services.py     # LangChain service
│   └── routing.py      # WebSocket routing
├── static/
│   └── chat.html       # Chat interface
└── media/
    ├── uploads/        # Uploaded documents
    └── vectorstores/   # FAISS indices
```

## Configuration

Settings can be adjusted in `qa_agent/settings.py`:
- `CHUNK_SIZE`: Size of text chunks (default: 1000)
- `CHUNK_OVERLAP`: Overlap between chunks (default: 200)
- `SIMILARITY_SEARCH_K`: Number of results to retrieve (default: 5)

## Troubleshooting

### OpenAI Rate Limit / Quota Errors

If you encounter errors like:
- `RateLimitError: You exceeded your current quota`
- `insufficient_quota`

**Solutions:**
1. **Check your OpenAI account billing**: Visit https://platform.openai.com/account/billing
   - Ensure you have credits available
   - Check if you've hit your usage limits
   - Consider upgrading your plan if needed

2. **Verify your API key**: Make sure your `OPENAI_API_KEY` in the `.env` file is correct and active

3. **Wait for rate limit reset**: If you've hit a rate limit, wait a few minutes and try again

4. **Check usage limits**: Free tier accounts have lower limits. Consider upgrading if you need higher usage

The application will now display user-friendly error messages when these issues occur, including suggestions on how to resolve them.

### WebSocket Connection Issues

If you see errors like "WebSocket connection failed" or "/ws/chat/ not found":

1. **Ensure you're running the server with daphne:**
   ```bash
   daphne -b 0.0.0.0 -p 8000 qa_agent.asgi:application
   ```
   Do NOT use `python manage.py runserver` - it may not handle WebSockets correctly.

2. **Verify daphne is installed:**
   ```bash
   pip list | grep daphne
   ```
   If not installed, run: `pip install daphne`

3. **Check the server logs** - you should see ASGI application startup messages when using daphne.

4. **Verify the WebSocket URL** - The chat interface connects to `ws://localhost:8000/ws/chat/`. Make sure your server is running on port 8000.

