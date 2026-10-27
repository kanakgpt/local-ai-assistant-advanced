import json
from mcp.server.fastmcp import FastMCP
from app.services.rag import search_docs
from app.services.web import search_web
from app.services.answer import answer_question

mcp = FastMCP("local-ai-knowledge-assistant")

@mcp.tool()
def search_local_documents(query: str, top_k: int = 4) -> str:
    """Search indexed local PDF passages and return source/page metadata."""
    if not 1 <= top_k <= 10:
        raise ValueError("top_k must be between 1 and 10.")
    return json.dumps(search_docs(query, top_k), ensure_ascii=False, indent=2)

@mcp.tool()
def search_web_tool(query: str, max_results: int = 5) -> str:
    """Search public web results and return titles, URLs, and snippets."""
    if not 1 <= max_results <= 10:
        raise ValueError("max_results must be between 1 and 10.")
    return json.dumps(search_web(query, max_results), ensure_ascii=False, indent=2)

@mcp.tool()
def ask_knowledge_assistant(question: str, allow_web: bool = True) -> str:
    """Answer from local documents with optional web fallback and estimated evidence score."""
    return json.dumps(answer_question(question, allow_web), ensure_ascii=False, indent=2)

if __name__ == "__main__":
    mcp.run()
