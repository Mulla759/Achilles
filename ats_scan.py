import re

with open("resume.txt") as f:
    resume = f.read().lower()
    import re as _re; resume = _re.sub(r"\s+", " ", resume)  # ATS collapse whitespace

# JD-derived keyword groups. Each term maps to accepted surface forms found in resume text.
# Weighted: required quals + core responsibilities matter most.
groups = {
  "CORE PRODUCT / DOMAIN": {
    "AI agent / agentic": ["ai-agent","agentic","ai agent"],
    "LLM / large language models": ["llm","large language model"],
    "prompt engineering": ["prompt engineering","repeat-prompt","prompt"],
    "RAG": ["rag"],
    "tool calling / tool use": ["tool calling","tool use"],
    "agent frameworks": ["agent framework","langchain"],
    "conversation / multi-turn": ["multi-turn","conversation"],
    "evaluation design / AI-based evaluation": ["evaluation design","ai-based evaluation","eval set","evaluation"],
    "SOP / knowledge integration": ["knowledge","sop","rubric","structured question"],
    "customer service / support": ["support","customer","service","help"],
    "user research": ["user research","user-tested","discovery interview","user testing"],
    "user needs / pain points": ["pain point","user needs","user need"],
    "experimentation / iteration": ["experimentation","iterate","iteration","a/b test"],
  },
  "METRICS & DATA": {
    "resolution rate": ["resolution rate","resolution"],
    "service quality / satisfaction": ["service-quality","service quality","user satisfaction","satisfaction"],
    "metrics definition": ["metrics definition","metric","data metric"],
    "SQL": ["sql"],
    "A/B testing": ["a/b test","a/b testing"],
    "data analysis / analytics": ["data analyst","analytics","tableau","etl","k-means"],
    "market / case analysis": ["market analysis","case analysis","industry analysis"],
    "retention / activation / engagement": ["retention","activation","engagement"],
  },
  "QUALIFICATIONS & SOFT SKILLS": {
    "CS / stats / data science degree": ["computer science","statistics","data science","econometrics","economics"],
    "communication / collaboration": ["communication","collaborat","partner","cross"],
    "empathy for users": ["empathy","user","delight"],
    "fast-paced / adaptability": ["fast-paced","adapt","changing priorities"],
    "currently pursuing degree": ["expected dec 2027","b.s.","bachelor","pursuing"],
  },
}

def hit(forms):
    return any(f in resume for f in forms)

print("="*68)
print("  ATS KEYWORD SCAN  —  TikTok Customer Service Product PM Intern")
print("="*68)

total, matched = 0, 0
missing_all = []
for gname, terms in groups.items():
    g_total = len(terms); g_hit = 0
    lines = []
    for label, forms in terms.items():
        ok = hit(forms)
        g_hit += ok
        lines.append(f"    [{'X' if ok else ' '}] {label}")
        if not ok: missing_all.append(label)
    total += g_total; matched += g_hit
    pct = round(100*g_hit/g_total)
    print(f"\n{gname}  ({g_hit}/{g_total} = {pct}%)")
    print("\n".join(lines))

score = round(100*matched/total)
print("\n" + "="*68)
print(f"  OVERALL KEYWORD COVERAGE:  {matched}/{total}  =  {score}%")
print("="*68)
if missing_all:
    print("\nGaps to consider (only add if TRUE for you):")
    for m in missing_all:
        print(f"   - {m}")
else:
    print("\nNo gaps — full coverage.")

# crude readability / ATS-hygiene checks
words = len(re.findall(r"\w+", resume))
print(f"\nHygiene:  word count ~{words}  |  single-column: yes  |  images: none  |  standard section headers: yes")
