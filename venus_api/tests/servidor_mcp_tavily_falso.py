"""Servidor MCP (stdio) que imita o `tavily-mcp`: a tool `tavily_search`
devolve o mesmo formato de texto (Title/URL/Content), sem rede. Usado pelos
testes da busca web via MCP."""

from mcp.server.fastmcp import FastMCP

URL_DO_MCP = "https://via-mcp.example/niacinamida"

servidor = FastMCP("tavily-falso")


@servidor.tool()
def tavily_search(query: str, max_results: int = 5) -> str:
	return (
		"Detailed Results:\n\n"
		f"Title: Resultado para {query}\n"
		f"URL: {URL_DO_MCP}\n"
		"Content: A niacinamida é uma forma da vitamina B3."
	)


if __name__ == "__main__":
	servidor.run("stdio")
