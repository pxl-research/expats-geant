"""
Text processing utilities: chunking, conversion, and string sanitization.
"""

import re
from typing import Callable, Optional

from markitdown import MarkItDown


def document_to_markdown(doc_filename: str) -> str:
    """
    Convert a document (DOCX, PPTX, XLSX, PDF, images, etc.) to Markdown text.

    Args:
        doc_filename: Path to the document file

    Returns:
        Markdown representation of the document
    """
    mid = MarkItDown(enable_plugins=False)
    conversion = mid.convert(doc_filename)
    return conversion.text_content


def image_description(img_filename: str, llm_client, model_name: str, language: str = "English") -> str:
    """
    Generate a Markdown image description using an LLM.

    Args:
        img_filename: Path to the image file
        llm_client: Initialized LLM client (e.g., LLMClient instance)
        model_name: Model name to use for description
        language: Language for the description (default: English)

    Returns:
        Markdown description of the image
    """
    md = MarkItDown(
        llm_client=llm_client,
        llm_model=model_name,
        llm_prompt=f"Describe the following image in detail, in {language}, using Markdown format",
    )
    result = md.convert(img_filename)
    return result.text_content


def clean_up_string(string: str) -> str:
    """
    Normalize and sanitize a string for use as identifiers/collection names.
    Converts to lowercase, replaces underscores with dashes, removes special characters,
    and collapses spaces to dashes.

    Args:
        string: Input string to sanitize

    Returns:
        Sanitized string (lowercase, dashes, alphanumeric + dashes only)
    """
    string = string.lower()
    string = string.replace("_", "-")
    string = re.sub(r"[^a-z0-9 -]+", " ", string)  # keep only a-z 0-9 space and dash
    string = string.lstrip(" ")  # remove leading spaces
    return string.replace(" ", "-")


def sanitize_filename(full_file_path: str, max_length: int = 60) -> str:
    """
    Create a safe, sanitized filename from a file path.
    Removes path and extension, sanitizes, and crops to max length.

    Args:
        full_file_path: Full path to the file
        max_length: Maximum length of output filename (default: 60)

    Returns:
        Sanitized filename
    """
    import os

    base_name = os.path.basename(full_file_path)  # remove path
    name_only = os.path.splitext(base_name)[0]  # remove extension
    sanitized = clean_up_string(name_only)
    return sanitized[:max_length]


def split_by_header(md_text: str, header_level: int = 1) -> list[str]:
    """
    Split Markdown text into sections based on header level.

    Args:
        md_text: Markdown text to split
        header_level: Header level to split on (1 = #, 2 = ##, etc.)

    Returns:
        List of text sections
    """
    header_pattern = r"(?=^" + r"#" * header_level + r" )"
    sections = re.split(header_pattern, md_text, flags=re.MULTILINE)
    return [sec for sec in sections if sec.strip()]


def split_by_newlines(text: str, newline_count: int = 2) -> list[str]:
    """
    Split text into sections based on consecutive newlines.

    Args:
        text: Text to split
        newline_count: Number of consecutive newlines to split on

    Returns:
        List of text sections
    """
    pattern = r"\n{" + str(newline_count) + r",}\s*"
    sections = re.split(pattern, text)
    return [sec.strip() for sec in sections if sec.strip()]


def split_on_sentences(text: str) -> list[str]:
    """
    Split text into sentences, preserving punctuation.

    Args:
        text: Text to split

    Returns:
        List of sentences
    """
    pattern = r"(?<=[.!?])\s+"
    sentences = re.split(pattern, text)
    return [s.strip() for s in sentences if s.strip()]


def split_on_threshold(text: str, max_chars: int = 1024, overlap_pct: float = 0.05) -> list[str]:
    """
    Split text into chunks not exceeding max_chars, respecting word boundaries.
    Optional overlap between chunks.

    Args:
        text: Text to split
        max_chars: Maximum characters per chunk
        overlap_pct: Overlap as percentage of max_chars (default: 5%)

    Returns:
        List of text chunks
    """
    chunks = []
    start = 0
    txt_len = len(text)
    overlap = int(max_chars * overlap_pct)

    while start < txt_len:
        end = min(start + max_chars, txt_len)

        if end == txt_len:
            chunk = text[start:end]
            if chunk.strip():
                chunks.append(chunk.strip())
            break

        # Find last whitespace to avoid breaking words
        last_whitespace = text.rfind(" ", start, end)
        chunk_end = last_whitespace if last_whitespace != -1 else end

        chunk = text[start:chunk_end].strip()
        if chunk:
            chunks.append(chunk)

        # Set next start with optional overlap
        if overlap > 0 and chunk_end - overlap > start:
            # Try to set overlap position at a word boundary
            overlap_start = chunk_end - overlap
            last_whitespace = text.rfind(" ", start, overlap_start)
            if last_whitespace > start:
                start = last_whitespace
            else:
                start = chunk_end
        else:
            start = chunk_end

    return chunks


def merge_small_chunks(small_chunks: list[str], max_size: int = 1024) -> list[str]:
    """
    Merge consecutive small chunks if their combined size is <= max_size.
    Reduces fragmentation from aggressive chunking strategies.

    Args:
        small_chunks: List of chunks to merge
        max_size: Maximum size per merged chunk

    Returns:
        List of merged chunks, optimized for size
    """
    if not small_chunks:
        return []

    merged = []
    current = ""

    for chunk in small_chunks:
        # If adding chunk keeps total size under max_size, merge
        if len(current) + len(chunk) <= max_size:
            current = (current + " " + chunk).strip() if current else chunk
        else:
            if current:
                merged.append(current)
            current = chunk

    if current:
        merged.append(current)

    return merged


def iterative_chunking(md_text: str, max_size: int = 1024) -> list[str]:
    """
    Iteratively chunk Markdown text using multiple strategies until all chunks are under max_size.
    Applies strategies progressively from coarse (headers) to fine (threshold-based).
    Merges small chunks to avoid fragmentation.

    Args:
        md_text: Markdown text to chunk
        max_size: Target maximum chunk size in characters

    Returns:
        List of chunks, all under max_size
    """
    chunks = [md_text]

    # Chunking strategies, from coarse to fine
    strategies: list[Callable[[str], list[str]]] = [
        lambda text: split_by_header(text, header_level=1),
        lambda text: split_by_header(text, header_level=2),
        lambda text: split_by_header(text, header_level=3),
        lambda text: split_by_header(text, header_level=4),
        lambda text: split_by_header(text, header_level=5),
        lambda text: split_by_header(text, header_level=6),
        lambda text: split_by_newlines(text, newline_count=4),
        lambda text: split_by_newlines(text, newline_count=3),
        lambda text: split_by_newlines(text, newline_count=2),
        lambda text: split_by_newlines(text, newline_count=1),
        split_on_sentences,
        lambda text: split_on_threshold(text, max_chars=max_size, overlap_pct=0.1),
    ]

    strat_idx = 0

    while strat_idx < len(strategies):
        # Check if all chunks are within size limit
        if all(len(chunk) <= max_size for chunk in chunks):
            return chunks

        # Apply current strategy to oversized chunks
        new_chunks = []
        for chunk in chunks:
            if len(chunk) > max_size:
                split_result = strategies[strat_idx](chunk)
                if len(split_result) > 1:
                    # Merge small chunks to reduce fragmentation
                    split_result = merge_small_chunks(split_result, max_size=max_size)
                new_chunks.extend(split_result)
            else:
                new_chunks.append(chunk)

        chunks = new_chunks
        strat_idx += 1

    return chunks
