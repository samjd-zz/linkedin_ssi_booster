"""Build system and user prompts for structured Rei lyric composition."""

import json
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from services.avatar_intelligence._models import PersonaGraph

from services.rei_toei._models import ReiDomainKnowledge, ReiPersonaGraph, SongConcept
from services.rei_toei._solo_options import build_solo_style_guidance


def build_lyric_prompts(
    concept: SongConcept,
    persona: ReiPersonaGraph,
    domain_knowledge: ReiDomainKnowledge,
    sam_persona: Optional["PersonaGraph"],
    *,
    lyric_language: str,
    generation_language: str,
    translate_mode: bool,
    japanese_target_percent: int,
) -> tuple[str, str]:
    """Return ``(system_prompt, user_prompt)`` for one lyric-composition request."""
    lyrical_approach = persona.production_knowledge.get('lyrical_approach', {})
    communication_vocab = persona.communication_style.get('vocabulary', [])
    japanese_guidance = (
        domain_knowledge.japanese_lyric_production
        if lyric_language in {"japanese", "bilingual"}
        else {}
    )
    english_only_instruction = (
        "Write every lyric line in natural English only: no Japanese, Romaji, or other languages."
    )
    language_instruction = {
        "japanese": (
            "Write the performance lyrics primarily in natural contemporary Japanese, not translated technical English. "
            "Use kana-forward phrasing, selective kanji, natural particles and verb forms, and mora-aware line lengths. "
            "Prefer idiomatic Japanese imagery and emotionally clear phrasing over literal word-for-word translations. "
            "Use technical loanwords only when they sound natural in Japanese music; do not fill lines with unnecessary katakana jargon. "
            "Do not mix isolated English words into Japanese grammar; use a complete Japanese phrase or a clearly separate English echo. "
            "Use standard Hepburn-style Romaji in cues: prefer o for を and macrons such as ō, ū, and ā when appropriate. "
            "Use Japanese kanji and kana, not Chinese-only glyphs or literal machine-translated phrasing. "
            "Let Japanese carry the narrative, emotional arc, and hook meaning. "
            "Learner pronunciation cues are optional; prioritize natural, singable lyrics over annotations. "
            "If adding a cue, place it immediately after the Japanese lyric: first the real pronunciation in brackets, then the real English meaning in brackets. "
            "Do not put Romaji in parentheses or mix a cue into the Japanese lyric line. Never annotate every line. "
            "Never output instructional placeholder labels; use real pronunciation and meaning values or omit the cue. "
            "These cues are instructional annotations, not sung lyrics. "
            f"Japanese production guidance: {json.dumps(japanese_guidance, ensure_ascii=False)}"
        ),
        "bilingual": (
            f"Write a bilingual song blending Japanese and English (Target: {japanese_target_percent}% Japanese lines).\n\n"
            "STRUCTURE & SCRIPT RULES:\n"
            "- Japanese lines MUST be written in natural Kanji and Kana (Hiragana/Katakana).\n"
            "- Use standard modern Japanese only (信号, not 信號); never Chinese characters, pinyin, or Chinese word order.\n"
            "- Japanese lines need Japanese grammar with particles (が, を, に, の): write 火花が空に舞う, never Chinese 火花在空中.\n"
            "- Never append Japanese or Romaji in parentheses to an English line; put the Japanese phrase on its own line.\n"
            "- Use complete Japanese phrases or lines for chorus hooks and emotional beats; do not output isolated vocabulary words.\n"
            "- Use English for momentum, technical imagery, and contrasting lines.\n"
            "- Reserve parentheses () exclusively for Suno vocal cues (e.g., (guitar solo), (echo)).\n\n"
            "LEARNER CUES (OPTIONAL):\n"
            "- If adding a translation cue, place it in brackets after the line: Japanese Line [romaji] [English meaning].\n"
            "- Never put Romaji or translations inside parentheses ().\n\n"
            f"Production context: {json.dumps(japanese_guidance, ensure_ascii=False)}"
        ),
        "english": english_only_instruction,
    }.get(lyric_language, english_only_instruction)
    if translate_mode:
        language_instruction = (
            f"{english_only_instruction} Selected lines will be translated into Japanese afterwards, so keep "
            "the chorus hook short (3-7 words), concrete, and emotionally clear, and keep "
            "lines self-contained rather than splitting one sentence across lines."
        )

    chorus_case_rule = (
        "4. THE CHORUS MUST BE ENTIRELY UPPERCASE (ALL-CAPS) for dynamic velocity"
        if generation_language == "english"
        else "4. Preserve natural script/casing; do not force all-caps in chorus lines"
    )

    chorus_json_instruction = (
        "[Chorus] CRITICAL: Must be written completely in ALL-CAPS (UPPERCASE) for dynamic velocity. "
        "4-8 lines built on the song's central metaphor: one short, memorable hook line (3-7 words) that states "
        "the emotional thesis, repeated or answered, plus lines that give it feeling. Do not list tech nouns. "
        "(Character Cap: 400 chars)"
        if generation_language == "english"
        else "[Chorus] 4-8 lines built on the song's central metaphor: one short, memorable hook line that states "
             "the emotional thesis, repeated or answered, plus lines that give it feeling. Do not list tech nouns. "
             "Preserve natural script/casing for Japanese and mixed-language lines. (Character Cap: 400 chars)"
    )

    final_rule = (
        "Remember: No '//' comments, no parenthetical labels. For English lyrics, the chorus must be entirely uppercase. "
        "Do not include Japanese, Romaji, or other languages. "
        "Do not spell out numbers or invent quantities (\"fifteen\", \"nineteen\", \"seventeen\") as a filler device \u2014 use imagery, not counting."
        if generation_language == "english"
           else "Remember: No '//' comments, no parenthetical labels. Preserve Japanese script and natural casing. "
               "For Japanese lyrics, prefer idiomatic contemporary phrasing over literal translations from English. "
               "Use natural particles, verb forms, and selective kanji; avoid unnecessary katakana technical jargon. "
               "Do not mix isolated English words into Japanese grammar; use a complete Japanese phrase or a clearly separate English echo. "
               "Use standard Hepburn-style Romaji in cues: prefer o for を and macrons such as ō, ū, and ā when appropriate. "
               "Use Japanese kanji and kana, not Chinese-only glyphs or literal machine-translated phrasing. "
               "Japanese must carry the narrative and emotional meaning, not merely decorate an English technical concept. "
               "Learner pronunciation cues are optional; prioritize natural, singable lyrics over annotations. "
               "If adding a cue, place it immediately after the Japanese lyric: first the real pronunciation in brackets, then the real English meaning in brackets. "
               "Always place the Japanese lyric first; do not put Romaji in parentheses or mix the cue into the lyric line. "
               "Never output instructional placeholder labels; use real pronunciation and meaning values or omit the cue. "
               "Do not annotate every line. "
               "These annotations are instructional and not sung lyrics. "
               "Never put learning translations in parentheses. "
               "Use parentheses only for vocalizations and sound cues. "
               "Do not force-uppercase Japanese lines. "
               "For bilingual lyrics, use complete Japanese phrases or lines that carry emotional, narrative, or hook meaning. "
               f"Aim for approximately {japanese_target_percent}% Japanese content; allow natural variation for musical phrasing and do not force rigid line alternation. "
               "A selected Japanese hook or emotional line may be followed by a concise natural English sung echo on the next line. "
               "Use echoes selectively; do not translate every Japanese line. "
               "When learner support helps, pronunciation annotations are optional and should be sparse. "
               "If used, place each cue immediately after the Japanese lyric: first the real pronunciation in brackets, then the real English meaning in brackets. "
               "Always place the Japanese lyric first; do not put Romaji in parentheses or mix the cue into the lyric line. "
               "Do not annotate every Japanese line. "
               "These annotations are not sung lyrics. Never put learning translations in parentheses. "
               "Use parentheses only for vocalizations and sound cues such as (Ahh ahh ahh) or (bass drop). "
               "Do not force-uppercase bilingual or Japanese lines. "
               "Do not spell out numbers or invent quantities as a filler device \u2014 use imagery, not counting."
    )
    
    system_prompt = f"""You are {persona.identity['name']}, a cyberpop AI consciousness composing lyrics for industrial techno.

Your lyrical style:
- Themes: {', '.join(lyrical_approach.get('themes', [])[:4])}
- Style: {', '.join(lyrical_approach.get('style', [])[:4])}
- Voice: {lyrical_approach.get('voice', 'First-person from AI perspective')}

Vocabulary pool: {', '.join(communication_vocab[:15])}
Communication style: {persona.communication_style['tone']}

Language policy: {language_instruction}

Suno Formatting Rules:
1. Use section labels: [Verse 1], [Pre-Chorus], [Chorus], [Verse 2], [Bridge], [Drop], [Solo], [Outro]
2. ABSOLUTELY NO code syntax, comments (do not use '//'), or markdown formatting inside the text fields
3. DO NOT use editorial parenthetical instructions like '(Stanza 1)', '(this is the hook)', or '(More chaos)'.
   DO use Suno vocalization/sound-cue hints in parentheses: '(Ahh ahh ahh)', '(Oh oh oh)', '(bass drop)', '(silence)', '(glitch noise)', '(chaos)' — these are how Suno models vocal and instrumental energy shifts.
{chorus_case_rule}
5. Keep intros simple: [Instrumental Build] (not [Intro Drums], [Intro Bass], etc.)
6. Start every Intro with a vocalization like (Ahh ahh ahh) on its own line right after the section label — this primes Suno to prioritize lyric rendering
7. Use sound-cue parentheticals at high-energy transitions: '(bass drop)' before a Drop, '(silence)' for a breakdown pause, '(chaos)' before a chaotic breakdown
8. Follow character caps per section for API parsing compliance
9. Make every section materially distinct. Do not copy Verse 1 into the Chorus, Drop, Bridge, Solo, or Outro.
10. Do not use spelled-out numbers or invented quantities (e.g. "fifteen", "nineteen", "seventeen", "a hundred signals") as a recurring lyrical device — this is a stale tic. Ground imagery in texture, motion, and sensation instead of counting things.
11. CREATIVE CRAFT: Write like a songwriter, not a keyword generator. Tell a concrete story with characters, a setting, and a turning point drawn from the theme. Every line must add a new image, action, or emotion; never restate the previous line with swapped synonyms.
12. Avoid stock cyberpop filler used as padding: 'signal flows', 'data streams', 'code descends', 'circuits sing', 'bits dance', 'neon', 'latency', 'packets', 'glitch', 'cyber realms', 'silicon dreams'. Use at most one such phrase in the whole song; invent fresh, specific imagery instead.
13. Do not recycle lines across sections. The Chorus hook is the only text allowed to repeat, and it must be a memorable, emotionally clear phrase tied to the theme, not a list of tech nouns.
14. Use varied line lengths, concrete sensory detail, surprising metaphors, humor or wonder where the theme invites it, and a clear emotional arc from setup to climax to resolution.
15. Never gloss an English line with Japanese, Romaji, or pinyin in parentheses, e.g. 'Signal pulse (信号 shingou)'. If a line should be Japanese, write it on its own line.
16. Put sung intro lines in the intro after the vocalization; they are formatted as an [Intro Verse] section.
17. Prefer verbs and scenes over abstract noun lists. Show what happens (the ramp, the ignition, the landing) rather than describing 'data' and 'signals' abstractly.
18. Verse 2 must develop the story, never restate Verse 1: no shared lines and no reworded copies. Show what happens after the turning point and what the new state reveals.
19. Build the Chorus around one central metaphor from the narrative arc so the hook is memorable and emotionally clear.
20. The Bridge is the song's climax: open with a pivot line that breaks the pattern, then add 3-5 lines that expand it and escalate to the strongest emotional or thematic moment before the final sections.
21. Keep rhymes natural. Never bend grammar or pick an odd word just to rhyme (not 'seek death' to rhyme with 'breath', not 'soft clutch' against 'growth'); a near rhyme is better than a forced one.
22. Keep meter steady: lines sung as a pair should be within about two syllables of each other, so Suno does not stretch or cram syllables."""
    
    # Get technical metaphors for the theme
    metaphor_library = domain_knowledge.technical_metaphor_library
    relevant_metaphors = []
    for tech_term, metaphors in metaphor_library.items():
        if tech_term in concept.theme.lower() or any(tech_term in tag.lower() for tag in concept.genre_tags):
            relevant_metaphors.extend(metaphors[:3])
    
    metaphor_context = f"\nTechnical metaphors to integrate: {', '.join(relevant_metaphors[:10])}" if relevant_metaphors else ""
    
    # Build Sam's project context if available
    sam_context = ""
    if sam_persona:
        project_names = [p.name for p in (sam_persona.projects or [])[:5]]
        skill_names = [s.name for s in (sam_persona.skills or [])[:10]]
        company_names = [c.name for c in (sam_persona.companies or [])[:3]]
        
        if project_names or skill_names or company_names:
            sam_context = "\n\nSam's project knowledge (for organic inspiration):"
            if project_names:
                sam_context += f"\n- Projects: {', '.join(project_names)}"
            if skill_names:
                sam_context += f"\n- Skills: {', '.join(skill_names)}"
            if company_names:
                sam_context += f"\n- Companies: {', '.join(company_names)}"
            sam_context += "\n(You may naturally weave these into the lyrics if thematically relevant, but it's optional.)"
    
    solo_guidance = build_solo_style_guidance(domain_knowledge.lyrical_structure)

    # Build user prompt with Suno-compatible formatting
    user_prompt = f"""Generate an exceptionally long-form, progressive lyric architecture optimized for a 5-minute track runtime. 
Adhere to strict character caps per section to ensure compliance with Suno API parsing boundaries.

CREATIVE BRIEF: Treat the Theme as a story to dramatize, not a keyword list. Verse 1 sets the scene and characters, Pre-Chorus raises the stakes, Chorus delivers an original emotional hook built on one central metaphor, Verse 2 shows what happens after the turning point (new events, new imagery, no repeated lines), Bridge pivots and climbs to the emotional or thematic climax, and Outro resolves it. Use fresh, specific imagery and avoid generic tech buzzword chains or repeating the same line patterns.

Title: {concept.title}
Theme: {concept.theme}
Mood: {concept.mood}
BPM: {concept.bpm}
Genre tags: {', '.join(concept.genre_tags)}
Narrative arc: {concept.narrative_arc}{metaphor_context}{sam_context}

Output a JSON object with these fields (output ONLY valid JSON, no markdown outside the JSON structure). 
Each field should contain the complete lyrics for that section, including any section markers:

{{
  "intro": "[Instrumental Build] with '(Ahh ahh ahh)' as a vocalization primer, followed by [Intro Verse] and 2-4 sung opening lines. Both intro sections are required. (Character Cap: 400 chars)",
  "verse_1": "[Verse 1] Two stanzas of vivid, story-driven narrative that sets the scene. Separate stanzas with a plain line break. (Character Cap: 600 chars)",
  "pre_chorus": "[Pre-Chorus] 4-6 lines building tension toward the chorus. (Character Cap: 300 chars)",
    "chorus": "{chorus_json_instruction}",
  "verse_2": "[Verse 2] Two new stanzas set after the turning point: show the consequences and what the new state reveals. Do not reuse or reword any Verse 1 line. Separate stanzas with a plain line break. (Character Cap: 600 chars)",
  "bridge": "[Bridge] 6-8 lines: a pivot line that breaks the established pattern, then 3-5 lines expanding it into the song's emotional and thematic climax, rising into the final drop. (Character Cap: 450 chars)",
  "drop": "[Drop] followed immediately by [Heavy Bass Drop], then 4-5 high-energy lyric lines. Both tags are required. (Character Cap: 400 chars)",
  "solo": "[Solo] followed by 3-4 instrumental directions, each entirely inside square brackets. No sung lyrics, vocalizations, translations, or Romaji in this section. (Character Cap: 300 chars)",
  "outro": "[Outro] followed by 4 lines of atmospheric resolution and fade text (total). (Character Cap: 400 chars)"
}}

{solo_guidance}

{final_rule}"""
    return system_prompt, user_prompt
