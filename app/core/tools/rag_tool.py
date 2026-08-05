from langchain_core.tools import tool

from app.core.rag import retrieve_documents


@tool
async def rag_tool(
    query: str
) -> str:
    """
    Search user's uploaded knowledge base
    using Pinecone retrieval.
    """

    try:

        documents = await retrieve_documents(
            query=query
        )


        if not documents:
            return "No relevant documents found."


        context = "\n\n".join(
            [
                doc.page_content
                for doc in documents
            ]
        )


        return context


    except Exception as e:

        return f"RAG error: {str(e)}"