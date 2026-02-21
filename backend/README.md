git add .
git commit -m "feat: complete Ask Meno with wiki scraper and citation fixes

Citation System Fixes:
- Deduplicate chunks by URL before prompt building AND citation extraction
- Explicit source count in prompt (prevents phantom citations)
- Consistent numbering between what OpenAI sees and what user sees
- Bug was sequencing issue, not hallucination

Ask Meno Performance:
- Now answers with wiki + PubMed citations
- Covers fitness, treatments, symptoms, stages
- Proper inline citations with source list
- 151 total chunks (12 PubMed + 139 wiki)

Knowledge base went from 12 to 151 chunks. Ask Meno is now production-ready! 🎉"
git push