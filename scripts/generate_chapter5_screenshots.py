from __future__ import annotations

import io
import keyword
import math
import tokenize
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "docs" / "chapter5_tier1_screenshots"

CODE_FONT_PATH = Path(r"C:\Windows\Fonts\CascadiaMono.ttf")
UI_FONT_PATH = Path(r"C:\Windows\Fonts\segoeui.ttf")
UI_BOLD_FONT_PATH = Path(r"C:\Windows\Fonts\segoeuib.ttf")

BACKGROUND = "#10151d"
HEADER_BACKGROUND = "#171e29"
PANEL_BACKGROUND = "#0d1117"
PANEL_HEADER = "#202938"
GUTTER_BACKGROUND = "#121923"
TEXT = "#d8dee9"
MUTED = "#8b99ad"
ACCENT = "#62aef7"
KEYWORD = "#c792ea"
STRING = "#ecc48d"
COMMENT = "#7f9f7f"
NUMBER = "#f78c6c"
FUNCTION = "#82aaff"
OPERATOR = "#89ddff"
BORDER = "#334155"

CODE_SIZE = 23
LINE_HEIGHT = 34
IMAGE_WIDTH = 2380
SIDE_PADDING = 56
TOP_HEADER_HEIGHT = 178
PANEL_HEADER_HEIGHT = 54
PANEL_GAP = 30
PANEL_PADDING_Y = 20
LINE_NUMBER_WIDTH = 96


@dataclass(frozen=True)
class Segment:
    path: str
    start: int
    end: int
    label: str = ""


@dataclass(frozen=True)
class Screenshot:
    number: int
    title: str
    caption: str
    segments: tuple[Segment, ...]
    note: str = ""


SCREENSHOTS = (
    Screenshot(
        1,
        "Document Upload and Background Queueing",
        "The FastAPI endpoint receives a PDF, creates its document record, and queues the Tier 1 pipeline as a background task.",
        (
            Segment("app/api/endpoints.py", 684, 717, "Upload endpoint and PDF-type validation"),
            Segment("app/api/endpoints.py", 727, 763, "Save upload and create the PENDING record"),
            Segment("app/api/endpoints.py", 783, 801, "Queue run_full_ai_pipeline"),
        ),
    ),
    Screenshot(
        2,
        "Pipeline Input Validation",
        "Before processing, the pipeline verifies that required models are loaded and that the PDF exists and is within the configured size limit.",
        (Segment("app/core/pipeline.py", 116, 165),),
    ),
    Screenshot(
        3,
        "Runtime Configuration and Overrides",
        "The pipeline loads the current Control Panel configuration, applies request-specific overrides, and resolves the feature toggles used by later stages.",
        (
            Segment("app/core/pipeline.py", 167, 185, "Load, merge, and resolve pipeline toggles"),
            Segment("app/api/config_endpoints.py", 279, 296, "Runtime configuration access and update"),
        ),
    ),
    Screenshot(
        4,
        "Mark Document as Processing",
        "MongoDB is updated to PROCESSING before AI work starts, while prior results and errors are cleared.",
        (Segment("app/core/pipeline.py", 230, 252),),
    ),
    Screenshot(
        5,
        "PDF Rendering and PaddleOCR",
        "PDF pages are rendered as PIL images and passed to PaddleOCR, which returns ordered text and confidence measurements.",
        (
            Segment("app/core/classifier.py", 53, 83, "Convert PDF pages to images"),
            Segment("app/core/classifier.py", 286, 320, "Run PaddleOCR"),
            Segment("app/core/classifier.py", 354, 373, "Build ordered text and confidence output"),
        ),
    ),
    Screenshot(
        6,
        "Logical Document Splitting",
        "Each page is OCR-processed and embedded; cosine-similarity drops identify document boundaries, after which pages are grouped into logical documents.",
        (
            Segment("app/core/classifier.py", 381, 423, "Splitter contract and model selection"),
            Segment("app/core/classifier.py", 428, 476, "Page OCR, embeddings, and break detection"),
            Segment("app/core/classifier.py", 478, 520, "Assemble logical document groups"),
        ),
        "The source docstring names all-MiniLM-L6-v2, but the loaded implementation model is paraphrase-multilingual-MiniLM-L12-v2.",
    ),
    Screenshot(
        7,
        "Page Image Reuse and Conversion Fallback",
        "Rendered page images are reused from the splitter where possible; otherwise, the pipeline performs a controlled Poppler conversion.",
        (Segment("app/core/pipeline.py", 341, 386),),
    ),
    Screenshot(
        8,
        "Confidence-Based OCR Validation",
        "OCR confidence routes text through SKIP, LIGHT, FULL, or REVIEW handling. Very-low-confidence pages use regex and LLaMA correction and are flagged for review.",
        (
            Segment("app/core/pipeline.py", 461, 487, "Invoke OCR validation and apply corrected text"),
            Segment("app/services/ocr_validation.py", 95, 153, "Confidence thresholds and routing"),
            Segment("app/services/ocr_validation.py", 189, 220, "REVIEW and FULL outcomes"),
        ),
        "Full-page TrOCR is explicitly disabled; TrOCR is reserved for suitable text regions.",
    ),
    Screenshot(
        9,
        "Document Classification with Reasoning",
        "SentenceTransformer similarity provides the initial class, then LLaMA adds reasoning and can override a low-confidence result.",
        (
            Segment("app/core/pipeline.py", 493, 518, "Pipeline classification call"),
            Segment("app/core/classifier.py", 558, 590, "Embedding-based classification"),
            Segment("app/core/classifier.py", 669, 725, "LLaMA reasoning and low-confidence routing"),
        ),
    ),
    Screenshot(
        10,
        "Search Embedding Generation",
        "Page embeddings support break detection, and a combined logical-document embedding is stored for later semantic search.",
        (
            Segment("app/core/classifier.py", 428, 450, "Generate page embeddings"),
            Segment("app/core/classifier.py", 455, 487, "Use similarity and create the document embedding"),
            Segment("app/core/classifier.py", 508, 520, "Store the embedding in the logical document"),
        ),
        "The ENABLE_EMBEDDING_GENERATION toggle is loaded by the pipeline but is not currently checked before these embeddings are generated.",
    ),
    Screenshot(
        11,
        "GPU Memory Monitoring",
        "During document processing, allocated GPU memory is measured and the CUDA cache is cleared when usage exceeds the safety threshold.",
        (
            Segment("app/core/pipeline.py", 522, 529, "Pipeline monitoring and cache release"),
            Segment("app/models/loader.py", 236, 250, "GPU memory measurement"),
        ),
    ),
    Screenshot(
        12,
        "Signature Detection",
        "The current Tier 1 implementation searches OCR text for signature-related patterns and validates that the captured value resembles a personal name.",
        (Segment("app/core/pipeline.py", 531, 561),),
        "This is OCR-text pattern detection. It does not currently call a YOLO signature detector or produce image bounding boxes.",
    ),
    Screenshot(
        13,
        "Signature Text Validation",
        "When a signature name is detected, LLaMA cross-references it with names in the document and can return a corrected value and confidence.",
        (
            Segment("app/core/pipeline.py", 563, 573, "Pipeline validation call and timeout handling"),
            Segment("app/core/pipeline.py", 576, 583, "Apply corrected signature"),
            Segment("app/services/signature_validation.py", 13, 60, "Signature validation contract and name extraction"),
            Segment("app/services/signature_validation.py", 87, 123, "Configured LLaMA validation and score"),
        ),
    ),
    Screenshot(
        14,
        "Parallel AI Processing",
        "Structured extraction, entity extraction, table handling, and summarization are independent and therefore run concurrently with asyncio.gather.",
        (
            Segment("app/core/pipeline.py", 585, 588, "Independent task definition"),
            Segment("app/core/pipeline.py", 649, 656, "Concurrent execution"),
        ),
    ),
    Screenshot(
        15,
        "Structured Field Extraction",
        "The classified document type selects an extraction schema, after which LLaMA extracts the corresponding structured business fields.",
        (
            Segment("app/core/pipeline.py", 590, 602, "Pipeline task and timeout"),
            Segment("app/utils/extraction.py", 402, 450, "Schema selection and model preparation"),
        ),
    ),
    Screenshot(
        16,
        "Named Entity Extraction",
        "A separate LLaMA task extracts companies, people, dates, amounts, addresses, emails, and phone numbers into a fixed JSON structure.",
        (
            Segment("app/core/pipeline.py", 604, 615, "Pipeline task and timeout"),
            Segment("app/utils/extraction.py", 840, 864, "Entity extraction contract and fallback"),
            Segment("app/utils/extraction.py", 870, 895, "JSON output format and generation configuration"),
        ),
    ),
    Screenshot(
        17,
        "Table Handling",
        "PPStructure table extraction has been removed. The pipeline currently returns an empty table collection and records a table count of zero.",
        (
            Segment("app/core/pipeline.py", 617, 620, "Inactive table task"),
            Segment("app/core/pipeline.py", 830, 832, "Stored table result"),
        ),
    ),
    Screenshot(
        18,
        "Summary Generation",
        "The summary task calls LLaMA when healthy and falls back to document text when the model is unavailable, times out, or fails.",
        (
            Segment("app/core/pipeline.py", 622, 647, "Health check, timeout, and fallback"),
            Segment("app/core/pipeline.py", 932, 975, "Summary function and grounded prompt"),
            Segment("app/core/pipeline.py", 977, 1000, "Configured generation and final fallback"),
        ),
    ),
    Screenshot(
        19,
        "Final Result Assembly",
        "All outputs are assembled into one processed document containing OCR, classification, signature, structured-data, entity, table, and summary results.",
        (Segment("app/core/pipeline.py", 796, 839),),
    ),
    Screenshot(
        20,
        "MongoDB Result Storage",
        "Results are converted to BSON-compatible values and stored with COMPLETE status, completion time, and logical-document count.",
        (Segment("app/core/pipeline.py", 841, 873),),
    ),
    Screenshot(
        21,
        "Semantic Search Index Refresh",
        "After successful storage, the in-memory FAISS index is invalidated so that the next search rebuild includes the new document.",
        (
            Segment("app/core/pipeline.py", 875, 882, "Invalidate after pipeline completion"),
            Segment("app/utils/vector_index.py", 143, 148, "Thread-safe FAISS invalidation"),
        ),
    ),
    Screenshot(
        22,
        "Failure Handling and Resource Cleanup",
        "Unhandled failures mark the document as FAILED. The finally block closes images, clears GPU memory, and removes temporary files.",
        (
            Segment("app/core/pipeline.py", 884, 929, "Failure status and guaranteed cleanup"),
            Segment("app/core/pipeline.py", 1003, 1019, "Temporary-file cleanup helper"),
        ),
    ),
)


def load_font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size=size)


CODE_FONT = load_font(CODE_FONT_PATH, CODE_SIZE)
TITLE_FONT = load_font(UI_BOLD_FONT_PATH, 39)
CAPTION_FONT = load_font(UI_FONT_PATH, 24)
PANEL_FONT = load_font(UI_BOLD_FONT_PATH, 21)
NOTE_FONT = load_font(UI_FONT_PATH, 21)


def read_segment(segment: Segment) -> list[tuple[int, str]]:
    path = ROOT / segment.path
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return [(number, lines[number - 1].expandtabs(4)) for number in range(segment.start, segment.end + 1)]


def token_color(token_type: int, token_text: str) -> str:
    if token_type == tokenize.COMMENT:
        return COMMENT
    if token_type == tokenize.STRING:
        return STRING
    if token_type == tokenize.NUMBER:
        return NUMBER
    if token_type == tokenize.OP:
        return OPERATOR
    if token_type == tokenize.NAME and keyword.iskeyword(token_text):
        return KEYWORD
    return TEXT


def highlighted_spans(code_lines: list[str]) -> list[list[tuple[str, str]]]:
    colors: list[list[str]] = [[TEXT] * len(line) for line in code_lines]
    source = "\n".join(code_lines) + "\n"

    try:
        tokens = tokenize.generate_tokens(io.StringIO(source).readline)
        previous_name = ""
        for token_info in tokens:
            token_type, token_text, start, end, _ = token_info
            start_row, start_col = start
            end_row, end_col = end
            color = token_color(token_type, token_text)
            if token_type == tokenize.NAME and previous_name in {"def", "class"}:
                color = FUNCTION

            if start_row == end_row and 1 <= start_row <= len(colors):
                line_colors = colors[start_row - 1]
                for col in range(start_col, min(end_col, len(line_colors))):
                    line_colors[col] = color
            else:
                for row in range(start_row, end_row + 1):
                    if not 1 <= row <= len(colors):
                        continue
                    line_colors = colors[row - 1]
                    row_start = start_col if row == start_row else 0
                    row_end = end_col if row == end_row else len(line_colors)
                    for col in range(row_start, min(row_end, len(line_colors))):
                        line_colors[col] = color

            if token_type == tokenize.NAME:
                previous_name = token_text
            elif token_type not in {tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT}:
                previous_name = ""
    except (tokenize.TokenError, IndentationError):
        pass

    result: list[list[tuple[str, str]]] = []
    for text, line_colors in zip(code_lines, colors):
        if not text:
            result.append([])
            continue
        spans: list[tuple[str, str]] = []
        start = 0
        current = line_colors[0]
        for index in range(1, len(text)):
            if line_colors[index] != current:
                spans.append((text[start:index], current))
                start = index
                current = line_colors[index]
        spans.append((text[start:], current))
        result.append(spans)
    return result


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if draw.textlength(candidate, font=font) <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def panel_height(line_count: int) -> int:
    return PANEL_HEADER_HEIGHT + PANEL_PADDING_Y * 2 + max(1, line_count) * LINE_HEIGHT


def draw_code_line(
    draw: ImageDraw.ImageDraw,
    y: int,
    line_number: int,
    spans: Iterable[tuple[str, str]],
) -> None:
    draw.text(
        (SIDE_PADDING + LINE_NUMBER_WIDTH - 18, y),
        str(line_number),
        font=CODE_FONT,
        fill=MUTED,
        anchor="ra",
    )
    x = SIDE_PADDING + LINE_NUMBER_WIDTH + 24
    for text, color in spans:
        draw.text((x, y), text, font=CODE_FONT, fill=color)
        x += draw.textlength(text, font=CODE_FONT)


def make_screenshot(spec: Screenshot) -> Path:
    segment_data = [(segment, read_segment(segment)) for segment in spec.segments]
    note_height = 0
    if spec.note:
        note_height = 88
    total_height = (
        TOP_HEADER_HEIGHT
        + sum(panel_height(len(lines)) for _, lines in segment_data)
        + PANEL_GAP * (len(segment_data) + 1)
        + note_height
    )

    image = Image.new("RGB", (IMAGE_WIDTH, total_height), BACKGROUND)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, IMAGE_WIDTH, TOP_HEADER_HEIGHT), fill=HEADER_BACKGROUND)

    step_text = f"STEP {spec.number:02d}"
    draw.rounded_rectangle((SIDE_PADDING, 31, SIDE_PADDING + 142, 76), radius=12, fill=ACCENT)
    draw.text((SIDE_PADDING + 71, 53), step_text, font=PANEL_FONT, fill="#07111d", anchor="mm")
    draw.text((SIDE_PADDING + 166, 25), spec.title, font=TITLE_FONT, fill="#f3f6fb")

    caption_lines = wrap_text(
        draw,
        spec.caption,
        CAPTION_FONT,
        IMAGE_WIDTH - SIDE_PADDING * 2,
    )
    caption_y = 91
    for line in caption_lines[:2]:
        draw.text((SIDE_PADDING, caption_y), line, font=CAPTION_FONT, fill=MUTED)
        caption_y += 32

    y = TOP_HEADER_HEIGHT + PANEL_GAP
    for segment, numbered_lines in segment_data:
        height = panel_height(len(numbered_lines))
        panel_bottom = y + height
        draw.rounded_rectangle(
            (SIDE_PADDING, y, IMAGE_WIDTH - SIDE_PADDING, panel_bottom),
            radius=15,
            fill=PANEL_BACKGROUND,
            outline=BORDER,
            width=2,
        )
        draw.rounded_rectangle(
            (SIDE_PADDING, y, IMAGE_WIDTH - SIDE_PADDING, y + PANEL_HEADER_HEIGHT),
            radius=15,
            fill=PANEL_HEADER,
        )
        draw.rectangle(
            (SIDE_PADDING, y + PANEL_HEADER_HEIGHT - 15, IMAGE_WIDTH - SIDE_PADDING, y + PANEL_HEADER_HEIGHT),
            fill=PANEL_HEADER,
        )
        header_text = f"{segment.path}  |  lines {segment.start}-{segment.end}"
        if segment.label:
            header_text += f"  |  {segment.label}"
        draw.text(
            (SIDE_PADDING + 22, y + PANEL_HEADER_HEIGHT / 2),
            header_text,
            font=PANEL_FONT,
            fill="#dce8f5",
            anchor="lm",
        )

        code_top = y + PANEL_HEADER_HEIGHT
        draw.rectangle(
            (
                SIDE_PADDING,
                code_top,
                SIDE_PADDING + LINE_NUMBER_WIDTH,
                panel_bottom,
            ),
            fill=GUTTER_BACKGROUND,
        )
        draw.line(
            (
                SIDE_PADDING + LINE_NUMBER_WIDTH,
                code_top,
                SIDE_PADDING + LINE_NUMBER_WIDTH,
                panel_bottom,
            ),
            fill=BORDER,
            width=1,
        )

        code_lines = [text for _, text in numbered_lines]
        spans_by_line = highlighted_spans(code_lines)
        line_y = code_top + PANEL_PADDING_Y
        for (line_number, _), spans in zip(numbered_lines, spans_by_line):
            draw_code_line(draw, line_y, line_number, spans)
            line_y += LINE_HEIGHT

        y = panel_bottom + PANEL_GAP

    if spec.note:
        note_lines = wrap_text(
            draw,
            f"Implementation note: {spec.note}",
            NOTE_FONT,
            IMAGE_WIDTH - SIDE_PADDING * 2 - 36,
        )
        note_top = y
        note_bottom = total_height - PANEL_GAP
        draw.rounded_rectangle(
            (SIDE_PADDING, note_top, IMAGE_WIDTH - SIDE_PADDING, note_bottom),
            radius=13,
            fill="#2a2318",
            outline="#806b3b",
            width=2,
        )
        note_y = note_top + 16
        for line in note_lines[:2]:
            draw.text((SIDE_PADDING + 18, note_y), line, font=NOTE_FONT, fill="#f1d79a")
            note_y += 28

    filename = f"{spec.number:02d}_{spec.title.lower().replace(' ', '_')}.png"
    filename = "".join(character for character in filename if character.isalnum() or character in "._-")
    output_path = OUTPUT_DIR / filename
    image.save(output_path, "PNG", optimize=True)
    return output_path


def make_contact_sheet(paths: list[Path]) -> None:
    thumb_width = 720
    columns = 3
    gap = 24
    margin = 32
    thumbs: list[Image.Image] = []
    for path in paths:
        image = Image.open(path).convert("RGB")
        ratio = thumb_width / image.width
        height = max(220, int(image.height * ratio))
        thumbs.append(image.resize((thumb_width, height), Image.Resampling.LANCZOS))

    rows = math.ceil(len(thumbs) / columns)
    row_heights = []
    for row in range(rows):
        row_items = thumbs[row * columns : (row + 1) * columns]
        row_heights.append(max(item.height for item in row_items))

    sheet_width = margin * 2 + columns * thumb_width + (columns - 1) * gap
    sheet_height = margin * 2 + sum(row_heights) + (rows - 1) * gap
    sheet = Image.new("RGB", (sheet_width, sheet_height), "#e7ebf0")

    y = margin
    for row in range(rows):
        x = margin
        row_items = thumbs[row * columns : (row + 1) * columns]
        for item in row_items:
            sheet.paste(item, (x, y))
            x += thumb_width + gap
        y += row_heights[row] + gap

    sheet.save(OUTPUT_DIR / "00_contact_sheet.png", "PNG", optimize=True)


def make_index(paths: list[Path]) -> None:
    lines = [
        "# Chapter 5 - Tier 1 Pipeline Screenshot Index",
        "",
        "These screenshots were generated from the current Tier 1 source code. "
        "No application source files were modified.",
        "",
        "Use the screenshots in this order:",
        "",
    ]
    for spec, path in zip(SCREENSHOTS, paths):
        lines.extend(
            [
                f"## {spec.number}. {spec.title}",
                "",
                spec.caption,
                "",
                f"- Image: `{path.name}`",
                "- Source: "
                + "; ".join(
                    f"`{segment.path}:{segment.start}-{segment.end}`"
                    for segment in spec.segments
                ),
            ]
        )
        if spec.note:
            lines.append(f"- Implementation note: {spec.note}")
        lines.append("")

    (OUTPUT_DIR / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    paths = [make_screenshot(spec) for spec in SCREENSHOTS]
    make_contact_sheet(paths)
    make_index(paths)
    print(f"Generated {len(paths)} screenshots in {OUTPUT_DIR}")
    for path in paths:
        print(path.name)


if __name__ == "__main__":
    main()
