from semanticscholar import SemanticScholar


def test_search():
    sch = SemanticScholar()

    # 1. 搜索论文 (Search for a paper)
    print("--- Testing Paper Search ---")
    query = 'Attention is all you need'
    results = sch.search_paper(query, limit=3)

    print(f"Total results found: {results.total}")
    for i, paper in enumerate(results):
        print(f"\nResult {i+1}:")
        print(f"  Title: {paper.title}")
        print(f"  Year: {paper.year}")
        print(f"  Citations: {paper.citationCount}")
        print(f"  Paper ID: {paper.paperId}")
        print(f"  URL: {paper.url}")

    # 2. 获取单篇论文详情 (Get details for a single paper)
    if results.total > 0:
        paper_id = results[0].paperId
        print(f"\n--- Fetching Details for Paper ID: {paper_id} ---")
        paper = sch.get_paper(paper_id)
        print(f"  Title: {paper.title}")
        print(f"  Abstract: {paper.abstract[:200]}..." if paper.
              abstract else "  Abstract: N/A")

        if paper.authors:
            authors = [author.name for author in paper.authors[:3]]
            print(f"  Authors (top 3): {', '.join(authors)}")


if __name__ == "__main__":
    try:
        test_search()
    except Exception as e:
        print(f"An error occurred: {e}")
