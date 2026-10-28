# Curation Evidence Relevance

Curation selects evidence from the article title and first 600 summary characters,
not the SSI component label. Persona details/project names and domain/extracted/
external statements must share **at least two informative terms** with the article
(one for a one-term query). Stopwords and numeric-only tokens do not qualify.
Tags, source titles, skill labels, and graph connectivity cannot make unrelated
content eligible.

Matching uses batched, language-routed spaCy lemmas plus raw words to preserve
capitalized product names such as "Managed Agents." Japanese kanji/katakana terms
also support basic matching when the Japanese model is missing; install/configure
`ja_core_news_md` for full linguistic segmentation. This is content-overlap
matching, not cross-language translation or a guarantee of factual entailment.

Only eligible facts enter hybrid ranking. Without the hybrid retriever, lexical
overlap ranks eligible facts directly. `EVIDENCE_PROJECT_COUNT`,
`EVIDENCE_DOMAIN_COUNT`, and `EXTRACTED_EVIDENCE_COUNT` are maximums, not quotas
that must be filled: no match means no facts from that pool. The prompt builder
also checks extracted context and never restores rejected facts as a fallback.

Normal live curation learns before selecting evidence, so newly persisted facts
can ground the current article. `--learn` remains extraction-only, and dry runs
without learning do not write knowledge. Selection is shared across channels for
the same article; identical evidence across those channels is expected.

Avatar Explain lists the selected persona/domain facts rather than independently
retrieved candidates. DoT paths retain full extracted source IDs for auditing.
The article itself remains context when no stored knowledge matches; existing
truth-gate and confidence-routing checks still apply.

See [learning pipeline](../learning-pipeline.md) and
[test results and regressions](../testing-and-dev.md#article-evidence-relevance-regressions).
