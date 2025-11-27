import json
import traceback
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.conf import settings
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from .models import Document
from .services import get_document_service


class ChatConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for handling chat messages."""

    async def connect(self):
        """Handle WebSocket connection."""
        await self.accept()
        await self.send(
            text_data=json.dumps(
                {"type": "connection", "message": "Connected to Q&A Agent"}
            )
        )

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        pass

    async def receive(self, text_data):
        """Handle incoming WebSocket messages."""
        try:
            data = json.loads(text_data)
            message_type = data.get("type", "message")

            if message_type == "message":
                question = data.get("question", "")
                document_ids = data.get("document_ids", [])

                if not question:
                    await self.send(
                        text_data=json.dumps(
                            {"type": "error", "message": "Question is required"}
                        )
                    )
                    return

                # Process the question
                response = await self.process_question(question, document_ids)

                await self.send(
                    text_data=json.dumps(
                        {
                            "type": "response",
                            "answer": response["answer"],
                            "sources": response["sources"],
                        }
                    )
                )
            else:
                await self.send(
                    text_data=json.dumps(
                        {
                            "type": "error",
                            "message": f"Unknown message type: {message_type}",
                        }
                    )
                )

        except json.JSONDecodeError:
            await self.send(
                text_data=json.dumps(
                    {"type": "error", "message": "Invalid JSON format"}
                )
            )
        except Exception as e:
            traceback.print_exc()
            await self.send(
                text_data=json.dumps(
                    {"type": "error", "message": f"Error processing request: {str(e)}"}
                )
            )

    @database_sync_to_async
    def get_documents(self, document_ids):
        """Get documents from database (async wrapper)."""
        if document_ids:
            queryset = Document.objects.filter(id__in=document_ids, processed=True)
        else:
            queryset = Document.objects.filter(processed=True)
        return list(queryset)

    async def process_question(self, question: str, document_ids: list) -> dict:
        """
        Process a question and return an answer with sources.

        Args:
            question: User's question
            document_ids: List of document IDs to search (empty list means search all)

        Returns:
            Dictionary with 'answer' and 'sources'
        """
        # Get processed documents
        documents = await self.get_documents(document_ids)

        if not documents:
            return {
                "answer": "No documents have been uploaded and processed yet. Please upload a document first.",
                "sources": [],
            }

        # Search for relevant chunks
        doc_ids = [doc.id for doc in documents]

        try:
            service = get_document_service()
            # Search across all documents
            try:
                relevant_chunks = service.search_all_documents(
                    question, doc_ids, k=settings.SIMILARITY_SEARCH_K
                )
            except ValueError as e:
                # Handle API errors during search
                error_msg = str(e)
                if "rate limit" in error_msg.lower() or "quota" in error_msg.lower():
                    return {
                        "answer": "⚠️ OpenAI API rate limit exceeded or insufficient quota. Please check your OpenAI account billing and plan. You may need to add credits or wait for the rate limit to reset.",
                        "sources": [],
                    }
                elif "authentication" in error_msg.lower():
                    return {
                        "answer": "⚠️ OpenAI API authentication failed. Please check that your OPENAI_API_KEY is correct and valid.",
                        "sources": [],
                    }
                else:
                    return {
                        "answer": f"⚠️ Error searching documents: {error_msg}",
                        "sources": [],
                    }

            if not relevant_chunks:
                return {
                    "answer": "I couldn't find enough relevant information in the uploaded documents to answer your question. Please try rephrasing your question or upload more relevant documents.",
                    "sources": [],
                }

            # Create a combined vectorstore from the chunks for the QA chain
            # For simplicity, we'll use the first document's vectorstore
            # In a production system, you might want to combine vectorstores
            first_doc = documents[0]
            vectorstore = service.load_vectorstore(first_doc.vectorstore_path)

            # If we have multiple documents, we need to search each and combine results
            # For now, we'll use a simple approach: search the first document's vectorstore
            # and include results from other documents if available

            # Create QA chain with Anthropic Claude
            if not settings.ANTHROPIC_API_KEY:
                return {
                    "answer": "ANTHROPIC_API_KEY not configured. Please set it in your environment variables.",
                    "sources": [],
                }

            llm = ChatAnthropic(
                model="claude-sonnet-4-5",
                anthropic_api_key=settings.ANTHROPIC_API_KEY,
                temperature=0,
            )

            # Create retriever
            retriever = vectorstore.as_retriever(
                search_kwargs={"k": settings.SIMILARITY_SEARCH_K}
            )

            # Retrieve relevant documents
            retrieved_docs = retriever.invoke(question)

            # Format context from retrieved documents
            context = "\n\n".join([doc.page_content for doc in retrieved_docs])

            # Create a prompt that only uses the provided context
            prompt = ChatPromptTemplate.from_messages(
                [
                    (
                        "system",
                        """You are a helpful assistant that answers questions based only on the provided context from uploaded documents. 
If you don't know the answer based on the provided context, say "I don't have enough information in the uploaded documents to answer this question."
For greeting messages just give a simple response like "Hello! How can I help you today?".
Do not use any knowledge outside of the provided context.""",
                    ),
                    (
                        "human",
                        """Context from documents:
{context}

Question: {question}

Answer: Provide a clear answer based only on the context provided. Include references to the source documents when possible.""",
                    ),
                ]
            )

            # Create chain
            chain = prompt | llm | StrOutputParser()

            # Get answer
            answer = chain.invoke({"context": context, "question": question})

            # Extract sources from retrieved documents
            sources = []
            for doc in retrieved_docs:
                source_info = {
                    "content": (
                        doc.page_content[:200] + "..."
                        if len(doc.page_content) > 200
                        else doc.page_content
                    ),
                    "metadata": doc.metadata,
                }
                sources.append(source_info)

            # Check if answer indicates insufficient information
            if (
                "don't have enough information" in answer.lower()
                or "don't know" in answer.lower()
            ):
                return {
                    "answer": "I don't have enough information in the uploaded documents to answer this question. Please try rephrasing your question or upload more relevant documents.",
                    "sources": sources,
                }

            return {"answer": answer, "sources": sources}

        except Exception as e:
            traceback.print_exc()
            return {"answer": f"Error processing question: {str(e)}", "sources": []}
