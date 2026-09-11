from __future__ import annotations

from dataclasses import dataclass

from .models import WordTiming


@dataclass
class SubtitleStyle:
    font: str = "DejaVu Sans"
    size: int = 96
    primary: str = "&H00FFFFFF"  # белый (формат AABBGGRR)
    highlight: str = "&H0000E5FF"  # жёлтый для текущего слова
    outline_color: str = "&H00000000"
    outline: int = 6
    shadow: int = 2
    margin_v: int = 640  # отступ снизу: субтитры чуть ниже центра, где их не закрывает интерфейс
    width: int = 1080
    height: int = 1920


def ass_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    h = int(seconds // 3600)
    m = int(seconds % 3600 // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def escape_ass(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "(").replace("}", ")")


def chunk_words(words: list[WordTiming], per_line: int) -> list[list[WordTiming]]:
    per_line = max(1, per_line)
    chunks: list[list[WordTiming]] = []
    current: list[WordTiming] = []
    for w in words:
        current.append(w)
        ends_sentence = w.word.rstrip().endswith((".", "!", "?", ":"))
        if len(current) >= per_line or ends_sentence:
            chunks.append(current)
            current = []
    if current:
        chunks.append(current)
    return chunks


def build_ass(words: list[WordTiming], style: SubtitleStyle | None = None, per_line: int = 3) -> str:
    """Собирает файл субтитров ASS: показываем по несколько слов, текущее слово подсвечено."""
    st = style or SubtitleStyle()
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {st.width}
PlayResY: {st.height}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Word,{st.font},{st.size},{st.primary},{st.primary},{st.outline_color},&H80000000,-1,0,0,0,100,100,0,0,1,{st.outline},{st.shadow},2,60,60,{st.margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines: list[str] = []
    chunks = chunk_words(words, per_line)
    for ci, chunk in enumerate(chunks):
        chunk_end = chunks[ci + 1][0].start if ci + 1 < len(chunks) else chunk[-1].end
        for wi, w in enumerate(chunk):
            start = w.start
            end = chunk[wi + 1].start if wi + 1 < len(chunk) else chunk_end
            if end <= start:
                end = start + 0.05
            parts = []
            for k, other in enumerate(chunk):
                text = escape_ass(other.word.upper())
                if k == wi:
                    parts.append(f"{{\\c{st.highlight}}}{text}{{\\c{st.primary}}}")
                else:
                    parts.append(text)
            lines.append(f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Word,,0,0,0,,{' '.join(parts)}")
    return header + "\n".join(lines) + "\n"
