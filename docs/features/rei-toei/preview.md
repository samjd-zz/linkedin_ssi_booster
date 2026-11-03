# Rei CLI Preview Runtime Behavior

See the [feature overview](idea.md) for Rei's role and music-generation architecture.

```bash
# Explicit theme: --rei-theme requires a quoted value
bash run.sh --profile core run --rm app \
  python main.py --rei-generate --rei-preview --rei-theme "async programming"

# Automatic theme selection from extracted knowledge
bash run.sh --profile core run --rm app python main.py --rei-generate --rei-preview

# Rebuild the app image before previewing local code changes
bash run.sh --profile core run --build --rm app python main.py --rei-generate --rei-preview
```

Preview generates the song concept, full lyrics, and formatted Suno prompt using local Ollama. It does not save artifacts, submit to Suno, download media, or render FLUX images. It is not a fast placeholder or a generation-free dry run.

## Preparation

Rei-only CLI runs skip GitHub profile enrichment because it is not used by the music prompts. Concept and lyric generation share the existing CLI Ollama client (including the configured model and host); the Rei default remains `gemma4:e4b` if `OLLAMA_MODEL` is unset. Recent titles are read once and reused for automatic theme selection and title uniqueness. Explicit themes skip unused avatar-state loading, except that `--rei-explain` still loads extracted evidence for DoT validation. Strudel's explicit-theme path likewise avoids avatar loading and reuses the CLI client.

## Timings and Retries

INFO timing records distinguish `rei.preparation`, `rei.concept`, `rei.lyrics`, `rei.suno_formatting`, and optional `rei.dot_validation`; Strudel generation uses `rei.strudel`. Existing `ollama.chat` wall times and server timing metrics identify each underlying model request.

After structured bilingual lyrics pass validation, each attempted translation
batch logs `🌐 Bilingual lyric translation: batch 1/3 (line count: 10)` before
its Ollama request. The message includes counts, not lyric text. It appears
within the CLI's `rei.lyrics` or console's `console.rei.lyrics` timing stage;
no batch message is emitted when no hooks are selected or for batches skipped
after a runner failure.

The lyric composer currently allows up to five attempts for Japanese/bilingual output and one for English, with up to 4,096 generated tokens per attempt. Structural, language-mix, script, and repetitiveness failures can trigger a complete regeneration. These checks and retry limits are unchanged by the startup optimization; warning logs give retry reasons. Formatting includes deterministic Japanese/Romaji normalization and does not make another LLM call. Use timings to distinguish retries from post-generation CPU work.

The launcher performs its GPU passthrough probe before Python's stage logs. One-off runs reuse the existing app image unless `run --build` is supplied.

### Intel JSON Grammar Compatibility

IPEX-LLM can abort during JSON-constrained decoding with
`Unexpected empty grammar stack after accepting piece: G`. Both Intel Compose
overrides set `OLLAMA_STRUCTURED_OUTPUT=false` on the app, disabling the native
JSON/schema sampler for all OllamaService format requests, including fallback
models. Prompts still request JSON and existing parsing and validation remain
in place. Other runtimes retain native structured output by default. For a
host Python process using IPEX-LLM, set `OLLAMA_STRUCTURED_OUTPUT=false` yourself.

If a hook-translation call raises an error, the remaining Ollama batches are
skipped instead of repeatedly hitting a failed runner. Valid results from
earlier batches are retained; missing lines use Argos when available, or stay
English with the failed count reported. Rebuild the app image after updating
and start a new preview run to pick up both the code and Compose environment.

## Required Sections and Instrumental Solo

Suno assembly and recognizable full-song console replies always include a sung
`[Intro Verse]` and `[Drop]` immediately followed by `[Heavy Bass Drop]`.
Existing sections are kept. A missing or empty intro reuses the first sung
chorus hook (or a verse line), retaining its adjacent pronunciation cues; an
omitted drop becomes an instrumental drop after the bridge or last verse/chorus.
Duplicate bass-drop markers are collapsed, and repairs are logged without
another model call. A song with no usable hook fails explicitly instead of
inventing an intro. Metadata reflects the repaired output.

`[Solo]` is instrumental-only: every direction is wrapped in square brackets,
for example `[Synthesizer whispers in the mix]`. Existing bracketed cues stay
bracketed, and no Romaji is generated for instrumental instructions. Solo lines
are bracketed before bilingual hook selection so they are not counted as sung
lyrics. Unstructured console replies remain unchanged.

The optional solo palette includes `[Epic Guitar Solo]`, `[Melodic Synth Solo]`,
`[Arpeggiated Synth Solo]`, `[Glitch Synth Solo]`, `[Industrial Percussion Solo]`,
and `[Modulated Bass Solo]`. Both song-generation prompts ask the model to pick
what suits the song, honor a requested instrument, or invent another fitting
style; guitar is not required in every song. These are suggestions, not a
guaranteed rotation, and they do not add another model call.

Customize the `lyrical_structure.solo.instrumental_options` list in
[Rei's domain knowledge](../../../data/avatar/rei_toei_domain_knowledge.json)
with unbracketed, single-line names. An empty list disables the suggestions;
malformed lists or names raise a configuration error. Known instrument-solo
cues are also recognized as stage directions so they are not copied as Romaji
when an intro is repaired.

Parenthetical production directions in `[Drop]` and `[Outro]` are converted to
square-bracket tags when they mention instruments, sounds, or production
actions, for example `(Frequency sync, glitch surge)` becomes
`[Frequency sync, glitch surge]`. Vocal ad-libs such as `(Ahh ahh ahh)` and
ordinary parentheticals in other sections remain unchanged; known instrument
solo cues can be tagged in any section.

## Japanese Lyric Cues

Structured bilingual songs are written English-first by default
(`REI_BILINGUAL_STRATEGY=translate`), so structure and copied-line checks
apply before translation. The composer chooses eligible hooks (chorus first,
then verse stanza openers, alternating bridge lines, and other sections)
toward `REI_JAPANESE_LYRIC_PROBABILITY`, using
`REI_BILINGUAL_MAX_HOOK_LINES` (default 40) for selection. The final ratio can
be lower when hooks or translations are unavailable. Each valid Japanese line
is inserted above its English sung echo; with an English-only draft, the
translation step cannot exceed 50% Japanese sung lines.

Ollama translates hooks as numbered JSON in batches of up to 10, retaining
valid results from partial replies. Missing or rejected lines (including
Chinese grammar or leftover English) use the offline Argos en→ja model when
available; it runs with CTranslate2 and is downloaded by the `argos-init`
Docker service. Polite endings such as `します` or `消えます` become plain
`する` or `消える`; lines that still fail stay English. An Ollama runtime
error stops later batches without discarding earlier results.
Set `REI_BILINGUAL_STRATEGY=generate` for direct bilingual drafting and mix
validation. The console's direct-LLM fallback prompts for the mix instead of
running structured translation or ratio validation.

For Japanese and bilingual songs, Rei checks inline, bracketed, parenthesized, and recognizable bare Romaji against their Japanese lyric lines. Every uncued Japanese line receives a generated Romaji cue, with auxiliary verbs and conjunctive particles joined to their verb (`segumentoka sareru`, `hikatte`). Existing cues that differ only by such splits, like `[segumentoka sa reru]`, are re-joined while keeping their macrons and capitalization. Bare Romaji written directly under a Japanese line is wrapped in `[]` so Suno does not sing it, and an extra bare guess below an existing cue is kept but also bracketed, never deleted. English translation lines remain sung. Recognized inline pronunciations count toward cue coverage; when only an English translation is present, backfilling uses the Japanese phrase without incorporating the translation. Explicit pronunciation/meaning pairs retain their English meaning; ambiguous English lyrics and sound cues are handled conservatively. Formatting also removes leaked quoted stage instructions and keeps technical acronyms such as `SQL` attached to Japanese phrases. Common simplified-Chinese words (for example `和谐`, `数据`, `连接`, `重组`) are replaced with Japanese equivalents (`調和`, `データ`, `接続`, `再構成`) before Romaji is added; other Chinese characters still need review. If the model adds an English gloss inside the Japanese parentheses, such as `(データ (data))`, only the Japanese is romanized (`[deeta]`). Japanese glossed in parentheses after an English line, such as `Signal flux pulse (信號流脈 shingō ryūme)`, is moved to its own sung line, because Suno sings parenthetical text. That moved Japanese line is a translation of the English line, so it gets no Romaji cue: the model's inline Romaji/pinyin and any cue line directly below it (for example `[yori tsuyoi yóri tsuyoi.]`) are dropped. Other Japanese lyric lines keep their bracketed learner cue. Traditional-Chinese characters and syntax (`信號`, `由程式重塑`) become Japanese (`信号`, `プログラムで再構築`), Chinese grammar such as `電子火花在空中` becomes `電子火花が空に舞う` and the cue below it is regenerated (`[denshi hibana ga sora ni mau]`), and kana-free lines with Chinese grammar (`在`, `了`, `们`, `吗`) trigger a retry; and accented or doubled cues elsewhere are matched against the expected reading. Own-line instrument cues such as `(bass drop)` and `(guitar solo)` become Suno meta tags (`[Heavy Bass Drop]`, `[Guitar Solo]`); vocalizations like `(Ahh ahh ahh)` stay in parentheses. If the Chorus, Verse 2, or Bridge copies more than one line from an earlier section, the draft is retried with the copied lines named (Drop and Outro may still reprise the Chorus); the prompt also asks for natural rhymes and steady meter. Before translation and assembly, a tidy pass removes echo parentheticals that repeat their line (`PULSE CODE (Pulse Code)` becomes `PULSE CODE`), deletes drop cues outside `[Drop]` so the drop plays once, removes Bridge lines copied from the Chorus (unless nothing would remain), and strips a dangling `、` or `,` from Japanese lines. Leaked prompt notes such as `(34 chars)`, `(38 chars, UPPERCASE)`, or `(ALL-CAPS)` are removed whole, so no empty `()` is left for Suno to sing. Sung lines in the intro are moved under an `[Intro Verse]` tag after `[Instrumental Build]`. Romaji cleanup runs once, during Suno assembly after section normalization, so formatting already-formatted lyrics adds nothing (except that a line moved out of a gloss looks like an ordinary Japanese line on a second pass). The direct console fallback applies the same cleanup to recognizable section-marked songs; unstructured replies are unchanged.

Readings use SudachiPy's contextual tokenization and pykakasi's Hepburn conversion; both are already included by the core requirements. If Sudachi is unavailable, Rei warns and falls back to pykakasi alone. If a Japanese character cannot be read, Rei warns and leaves its existing cue unchanged rather than producing a partial reading. These checks do not guarantee correct Japanese, resolve every ambiguous reading, or verify English translations: review the preview before submitting. They do not add an LLM call.

## Song Development

Concept prompts ask for a central chorus metaphor, an opening situation, a turning point, and what happens after it. Lyric prompts require Verse 2 to continue after the turning point without reusing Verse 1 lines, a chorus hook built on the metaphor, and a 6-8 line climactic bridge that leads into the final Drop; assembled songs place `[Bridge]` before `[Drop]`. For Japanese and bilingual songs, a Verse 2 that mostly repeats Verse 1 triggers a retry with revision feedback; English songs make one attempt and only log a warning. Bridge length is guided by the prompt, not enforced.

See [regression coverage](../../testing-and-dev.md#rei-cli-preview-preparation-and-timing) for isolated CLI tests and current suite results.
