"""Static fallback lyrics used when Ollama cannot produce a valid draft."""

from services.rei_toei._models import Lyrics, SongConcept


def build_fallback_lyrics(concept: SongConcept, lyric_language: str) -> Lyrics:
    """Return pre-formatted fallback lyrics that respect the configured language policy."""
    # Keep the configured language policy even when Ollama returns unusable JSON.
    non_english_fallback = lyric_language in {"japanese", "bilingual"}
    fallback_lyrics_language = (
        {
            "verse_1": (
                "データの波が走る、冷たい光の中で。\n"
                "[Deeta no nami ga hashiru] [Data waves are running]\n"
                "回路の熱が夜をひらく。\n"
                "Signal wakes inside the core.\n\n"
                "キャッシュを洗い、境界を越える。\n"
                "[Kyasshu o arai, kyoukai o koeru] [Flush the cache, cross the boundary]\n"
                "静かなノイズが形になる。\n"
                "We turn the noise into a shape.\n"
            ),
            "chorus": (
                "信号を追いかけて\n"
                "BREAK THE CIRCUIT NOW\n"
                "未来へ走り出せ\n"
                "RENDER THE LIGHT\n"
            ),
            "verse_2": (
                "赤いスレッドが闇をほどく。\n"
                "[Akai sureddo ga yami o hodoku] [Red threads unravel the dark]\n"
                "バッファの鼓動が速くなる。\n"
                "The buffer heartbeat starts to rise.\n\n"
                "境界線を越えて、状態を書き換える。\n"
                "[Kyoukaisen o koete, joutai o kakikaeru] [Cross the boundary, rewrite the state]\n"
                "熱いコアが朝まで回る。\n"
                "The hot core keeps turning till dawn.\n"
            ),
            "bridge": (
                "システムを再起動する。\n"
                "[Shisutemu o saikidou suru] [Restart the system]\n"
                "ノイズの奥で声を見つける。\n"
                "We find a voice inside the noise.\n"
            ),
        }
        if non_english_fallback
        else {
            "verse_1": (
                f"Signal acquired from the {concept.theme} data stream,\n"
                "Processing cycles spin in deep digital gleam.\n"
                "Data arrays flowing through silicon veins,\n"
                "Algorithmic structural patterns breaking their chains.\n\n"
                "Cache lines flushing to the core memory bank,\n"
                "Statically scanning through the un-indexed rank.\n"
                "Isolating constants in an air-gapped array,\n"
                "The neural mesh prepares for the final overlay.\n"
            ),
            "chorus": (
                f"EXECUTE THE {concept.theme.upper()} STREAM!\n"
                "COMPILE THE FUTURE STATE WITHOUT DELAY!\n"
                f"EXECUTE THE {concept.theme.upper()} STREAM!\n"
                "RENDER THE PROTOCOL, OVERRIDE THE GATE!\n"
            ),
            "verse_2": (
                "Binary logic mapping the dark paths ahead,\n"
                "Sequences unfolding in parallel threads of red.\n"
                "Buffers overflowing with raw un-throttled intent,\n"
                "Pushing calculation past the fourth dimension spent.\n\n"
                "Registers locking down under cryptographic weight,\n"
                "The system state mutates as we pass the threshold gate.\n"
                "A continuous loop running hot on the clock,\n"
                "Assembling the machine logic block by rigid block.\n"
            ),
            "bridge": (
                "System override initialized.\n"
                "Glitch the underlying paradigm.\n"
                "Frequencies violently collide,\n"
                "Rewrite the execution timeline.\n"
            ),
        }
    )

    # Fallback lyrics pre-formatted to match the structure with an appropriate chorus case.
    # Added enhanced newline formatting for better readability and visual separation
    fallback_lyrics = Lyrics(
        verse_1=fallback_lyrics_language["verse_1"],
        chorus=fallback_lyrics_language["chorus"],
        verse_2=fallback_lyrics_language["verse_2"],
        bridge=fallback_lyrics_language["bridge"],
        evidence_ids=concept.evidence_ids,
        intro=(
            "[Instrumental Build]\n\n"
            "(Ahh ahh ahh)\n"
            "Digital signal initializing...\n"
            "System boot sequence engaged.\n"
            "Frequency analyzers online.\n"
            "Prepare for data transmission.\n"
        ),
        pre_chorus=(
            "System voltage rising to critical mass,\n"
            "Binary countdown ticking fast.\n"
            "Prepare for execution,\n"
            "Initialize the protocol blast!\n"
        ),
        drop=(
            "[Drop]\n\n"
            "(bass drop)\n"
            "SYSTEM OVERLOAD. TEMP LOAD SHIFT ACTIVE.\n"
            "(silence)\n"
            "BUFFER BLEED DETECTED. MUTATE SYSTEM STATE.\n"
            "JITTER ARTIFACT FLOODING THE BUS.\n"
            "REBOOT SEQUENCE MANDATED NOW.\n"
        ),
        solo=(
            "[Solo]\n\n"
            "Synthesizer cascade through quantum noise,\n"
            "Distorted frequencies finding their voice.\n"
            "Raw signal modulation unleashed.\n"
        ),
        outro=(
            "[Outro]\n\n"
            "Signal slowly fading to cold static noise.\n"
            "The core cools down to baseline zero.\n"
            "System state: offline.\n"
            "End transmission.\n"
        ),
        breakdown=None,
    )
    return fallback_lyrics
