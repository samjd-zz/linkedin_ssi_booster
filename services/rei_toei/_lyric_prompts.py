"""Build system and user prompts for structured Rei lyric composition."""

import json
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from services.avatar_intelligence._models import PersonaGraph

from services.rei_toei._models import ReiDomainKnowledge, ReiPersonaGraph, SongConcept
from services.rei_toei._solo_options import build_solo_style_guidance
from services.rei_toei._stage_policy import load_stage_policy
from services.rei_toei._style_policy import apply_song_style

MAX_SUNO_PRACTICE_RULES = 8
_JAPANESE_RULE_WORDS = ("japanese", "romaji", "kana", "kanji")


def build_suno_practice_guidance(
    domain_knowledge: ReiDomainKnowledge, *, include_japanese: bool = True
) -> str:
    """Return the domain-knowledge Suno rules as a short prompt block, or ``""``."""
    rules = (domain_knowledge.suno_best_practices or {}).get("prompt_rules", [])
    lines = [str(rule).strip() for rule in rules if isinstance(rule, str) and rule.strip()]
    if not include_japanese:
        lines = [line for line in lines if not any(word in line.lower() for word in _JAPANESE_RULE_WORDS)]
    if not lines:
        return ""
    bullets = "\n".join(f"- {line}" for line in lines[:MAX_SUNO_PRACTICE_RULES])
    return f"Suno v6-mini lyric-formatting practices:\n{bullets}"


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
    policy = load_stage_policy(domain_knowledge.lyrical_structure)
    apply_song_style(concept, policy.style)
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
            "If adding a cue, place it immediately after the Japanese lyric: first the real pronunciation in brackets, then the English meaning as its own sung line. "
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
            "- Use parentheses () for sung vocalizations such as (Ahh ahh ahh), keeping them in Latin characters even in Japanese lyrics. "
            "Put instrumental cues such as [Guitar Solo] and [Chaos] in square brackets on their own lines.\n\n"
            "LEARNER CUES (OPTIONAL):\n"
            "- If adding a translation cue: Japanese Line, then [romaji] on the next line, then the English meaning as a sung line without brackets.\n"
            "- Never put Romaji or translations inside parentheses ().\n\n"
            f"Production context: {json.dumps(japanese_guidance, ensure_ascii=False)}"
        ),
        "english": english_only_instruction,
    }.get(lyric_language, english_only_instruction)
    if translate_mode:
        language_instruction = (
            f"{english_only_instruction} Selected lines will be translated into Japanese afterwards, so keep "
            "the chorus hook short, roughly three to seven words, concrete, and emotionally clear, and keep "
            "lines self-contained rather than splitting one sentence across lines."
        )

    chorus_case_rule = (
        "4. THE CHORUS MUST BE ENTIRELY UPPERCASE (ALL-CAPS) for dynamic velocity"
        if generation_language == "english" and policy.style.uppercase_chorus
        else "4. Preserve natural script/casing; do not force all-caps in chorus lines"
    )

    chorus_min = policy.style.min_chorus_lines
    chorus_body = (
        f"{max(4, chorus_min)}-{max(8, chorus_min)} sung lines built on the song's central metaphor. "
        "Line 1 is a short, memorable hook that states the emotional thesis. "
        f"Follow it with at least {max(3, chorus_min)} different lines that answer the hook with feeling, "
        "imagery, and a promise or consequence; each line must say something new. "
        "You may sing the hook once more as the final line, but never repeat it back-to-back "
        f"or let repeats make up the Chorus. At least {chorus_min} lines must be distinct. "
        "When the hook repeats, write the hook words again as a complete sung line. "
        "Do not output word counts or repetition instructions. Do not list tech nouns. "
    )
    chorus_json_instruction = (
        "[Chorus] Write every Chorus lyric in uppercase letters for dynamic velocity. "
        + chorus_body + "Max 400 characters."
        if generation_language == "english" and policy.style.uppercase_chorus
        else "[Chorus] " + chorus_body + "Preserve natural expressive script/casing. Max 400 characters."
    )

    final_rule = (
        "Remember: No '//' comments, no parenthetical labels. "
        + ("For English lyrics, the chorus must be entirely uppercase. "
           if policy.style.uppercase_chorus else "Preserve natural expressive casing. ")
        + "Do not include Japanese, Romaji, or other languages. "
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
               "If adding a cue, place it immediately after the Japanese lyric: first the real pronunciation in brackets, then the English meaning as its own sung line. "
               "Always place the Japanese lyric first; do not put Romaji in parentheses or mix the cue into the lyric line. "
               "Never output instructional placeholder labels; use real pronunciation and meaning values or omit the cue. "
               "Do not annotate every line. "
               "These annotations are instructional and not sung lyrics. "
               "Never put learning translations in parentheses. "
               "Use parentheses for sung vocalizations and brackets for sound cues. "
               "Do not force-uppercase Japanese lines. "
               "For bilingual lyrics, use complete Japanese phrases or lines that carry emotional, narrative, or hook meaning. "
               f"Aim for approximately {japanese_target_percent}% Japanese content; allow natural variation for musical phrasing and do not force rigid line alternation. "
               "A selected Japanese hook or emotional line may be followed by a concise natural English sung echo on the next line. "
               "Use echoes selectively; do not translate every Japanese line. "
               "When learner support helps, pronunciation annotations are optional and should be sparse. "
               "If used, place each cue immediately after the Japanese lyric: first the real pronunciation in brackets, then the English meaning as its own sung line. "
               "Always place the Japanese lyric first; do not put Romaji in parentheses or mix the cue into the lyric line. "
               "Do not annotate every Japanese line. "
               "These annotations are not sung lyrics. Never put learning translations in parentheses. "
               "Use parentheses for sung vocalizations, and brackets for instrumental directions. "
               "Do not force-uppercase bilingual or Japanese lines. "
               "Do not spell out numbers or invent quantities as a filler device \u2014 use imagery, not counting."
    )
    
    system_prompt = f"""You are {persona.identity['name']}, composing lyrics for {', '.join(concept.genre_tags)}.

Your lyrical style:
- Themes: {', '.join(lyrical_approach.get('themes', [])[:4])}
- Style: {', '.join(lyrical_approach.get('style', [])[:4])}
- Voice: {lyrical_approach.get('voice', 'First-person from AI perspective')}

Vocabulary pool: {', '.join(communication_vocab[:15])}
Communication style: {persona.communication_style['tone']}

Language policy: {language_instruction}

Suno Formatting Rules:
1. Follow the active stage-cue profile below for enabled fields, required sections, labels, and cues.
2. ABSOLUTELY NO code syntax, comments (do not use '//'), or markdown formatting inside the text fields
3. DO NOT use editorial parenthetical instructions like '(Stanza 1)', '(this is the hook)', or '(More chaos)'.
   Put sung vocalizations like '(Ahh ahh ahh)' and '(Oh oh oh)' in parentheses, keeping their spelling in Latin characters.
   Put instrumental or sound cues in square brackets, using the active profile, and never attach them to a sung line.
{chorus_case_rule}
5. Keep section labels and stage directions short and on their own lines. Never put stage directions in parentheses.
6. Use only the intro primer specified by the profile; do not force a primer when it is disabled.
7. Never sing, translate, or annotate instrumental directions as lyric lines.
8. Follow character caps per section for API parsing compliance
9. Make every section materially distinct. Do not copy Verse 1 into the Chorus, Drop, Bridge, Solo, or Outro.
10. Do not use spelled-out numbers or invented quantities (e.g. "fifteen", "nineteen", "seventeen", "a hundred signals") as a recurring lyrical device — this is a stale tic. Ground imagery in texture, motion, and sensation instead of counting things.
11. CREATIVE CRAFT: Write like a songwriter, not a keyword generator. Tell a concrete story with characters, a setting, and a turning point drawn from the theme. Every line must add a new image, action, or emotion; never restate the previous line with swapped synonyms.
12. Avoid stock cyberpop filler used as padding: 'signal flows', 'data streams', 'code descends', 'circuits sing', 'bits dance', 'neon', 'latency', 'packets', 'glitch', 'cyber realms', 'silicon dreams'. Use at most one such phrase in the whole song; invent fresh, specific imagery instead.
13. Do not recycle lines across sections. The Chorus hook is the only text allowed to repeat, and it must be a memorable, emotionally clear phrase tied to the theme, not a list of tech nouns. Write the hook words again as a complete sung line, not a word-count or repetition placeholder. Repeating the hook never replaces the Chorus's other distinct lines.
14. Use varied line lengths, concrete sensory detail, surprising metaphors, humor or wonder where the theme invites it, and a clear emotional arc from setup to climax to resolution.
15. Never gloss an English line with Japanese, Romaji, or pinyin in parentheses, e.g. 'Signal pulse (信号 shingou)'. If a line should be Japanese, write it on its own line.
16. Follow the profile's intro layout, including its sung-opening label when configured.
17. Prefer verbs and scenes over abstract noun lists. Show what happens (the ramp, the ignition, the landing) rather than describing 'data' and 'signals' abstractly.
18. Verse 2 must develop the story, never restate Verse 1: no shared lines and no reworded copies. Show what happens after the turning point and what the new state reveals.
19. Build the Chorus around one central metaphor from the narrative arc so the hook is memorable and emotionally clear.
20. If the profile includes a sung Bridge, give it a contrasting pivot and at least {policy.style.min_bridge_lines} sung lines, following the selected arrangement rather than forcing an electronic climax.
21. Keep rhymes natural. Never bend grammar or pick an odd word just to rhyme (not 'seek death' to rhyme with 'breath', not 'soft clutch' against 'growth'); a near rhyme is better than a forced one.
22. Keep meter steady: lines sung as a pair should be within about two syllables of each other, so Suno does not stretch or cram syllables."""
    system_prompt += f"\n\n{policy.prompt_guidance()}"
    system_prompt += "\n\n" + policy.style.guidance()
    
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
    
    solo_guidance = (
        build_solo_style_guidance(domain_knowledge.lyrical_structure)
        if policy.rule("solo") else ""
    )
    suno_guidance = build_suno_practice_guidance(
        domain_knowledge, include_japanese=generation_language in {"japanese", "bilingual"}
    )
    if suno_guidance:
        solo_guidance = f"{solo_guidance}\n\n{suno_guidance}" if solo_guidance else suno_guidance

    descriptions = {
        "intro": "2-4 opening lines. Max 400 characters.",
        "verse_1": "Two vivid, story-driven stanzas setting the scene. Max 600 characters.",
        "pre_chorus": "4-6 lines building tension. Max 300 characters.",
        "chorus": chorus_json_instruction.replace("[Chorus]", "").strip(),
        "verse_2": "Two new stanzas after the turning point. Do not reuse or reword any Verse 1 line. Max 600 characters.",
        "bridge": (
            f"At least {policy.style.min_bridge_lines} sung lines developing a contrasting pivot toward the emotional and thematic climax"
            + (", rising into the final drop" if policy.rule("drop") else "")
            + ". Max 450 characters."
        ),
        "drop": "4-5 high-energy lines after the configured cues. Max 400 characters.",
        "solo": "3-4 instrumental directions, never sung lyrics. Max 300 characters.",
        "breakdown": "A contrasting deconstructed passage. Max 300 characters.",
        "outro": "4 closing lines resolving the narrative. Max 400 characters.",
    }
    section_instructions = {
        rule.field: (
            f"{rule.guidance()}. "
            + (descriptions[rule.field] if rule.content == "sung"
               else "Use only bracketed instrumental directions; no lyrics, translations, or Romaji.")
        )
        for rule in policy.sections
    }
    user_prompt = f"""Generate an exceptionally long-form, progressive lyric architecture optimized for a 5-minute track runtime. 
Adhere to strict character caps per section to ensure compliance with Suno API parsing boundaries.

CREATIVE BRIEF: Treat the Theme as a story to dramatize, not a keyword list. For the sections enabled by the profile, use verses for scenes and consequences, a chorus for the emotional hook, a bridge for a climax, and an outro for resolution. Use fresh imagery rather than tech buzzword chains. Do not add sections disabled by the profile.

Title: {concept.title}
Theme: {concept.theme}
Mood: {concept.mood}
BPM: {concept.bpm}
Genre tags: {', '.join(concept.genre_tags)}
Narrative arc: {concept.narrative_arc}{metaphor_context}{sam_context}

Output a JSON object with these fields (output ONLY valid JSON, no markdown outside the JSON structure). 
{policy.prompt_guidance()}
Each field should contain the complete lyrics for that section, including any section markers.
LINE FORMAT: inside each JSON string, separate every lyric line and bracketed cue with a newline (\\n).
Never join lines with ';' or '/'. The values below describe what to write; never copy these
descriptions, character limits, or casing notes into the lyrics.

{json.dumps(section_instructions, ensure_ascii=False, indent=2)}

{solo_guidance}

{final_rule}"""
    return system_prompt, user_prompt
