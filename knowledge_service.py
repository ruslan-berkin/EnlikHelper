import hashlib
import math
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI, OpenAIError
from pypdf import PdfReader

from database import (
    equipment_exists,
    get_manual_chunks,
    list_manual_documents,
    save_manual_document,
)


load_dotenv()

MAX_CHUNK_CHARACTERS = 1600
CHUNK_OVERLAP_WORDS = 40
EMBEDDING_BATCH_SIZE = 64


class ManualKnowledgeUnavailable(RuntimeError):
    pass


def _openai_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise ManualKnowledgeUnavailable(
            "OPENAI_API_KEY отсутствует в .env"
        )

    return OpenAI(api_key=api_key)


def _embedding_model() -> str:
    return os.getenv(
        "OPENAI_EMBEDDING_MODEL",
        "text-embedding-3-small",
    )


def _chunk_text(text: str) -> list[str]:
    words = " ".join(text.split()).split()

    if not words:
        return []

    chunks = []
    start = 0

    while start < len(words):
        end = start
        characters = 0

        while end < len(words):
            next_length = len(words[end]) + (1 if end > start else 0)

            if (
                end > start
                and characters + next_length > MAX_CHUNK_CHARACTERS
            ):
                break

            characters += next_length
            end += 1

        chunks.append(" ".join(words[start:end]))

        if end >= len(words):
            break

        start = max(start + 1, end - CHUNK_OVERLAP_WORDS)

    return chunks


def _extract_chunks(file_path: Path) -> tuple[int, list[dict]]:
    try:
        reader = PdfReader(file_path)
    except Exception as error:
        raise ValueError("Не удалось прочитать PDF-файл") from error

    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception as error:
            raise ValueError("PDF защищён паролем") from error

    chunks = []

    for page_number, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception as error:
            raise ValueError(
                f"Не удалось извлечь текст со страницы {page_number}"
            ) from error

        for chunk_index, content in enumerate(_chunk_text(text)):
            chunks.append(
                {
                    "page_number": page_number,
                    "chunk_index": chunk_index,
                    "content": content,
                }
            )

    if not chunks:
        raise ValueError(
            "В PDF не найден текст. Возможно, документ состоит из сканов"
        )

    return len(reader.pages), chunks


def _create_embeddings(texts: list[str]) -> list[list[float]]:
    client = _openai_client()
    embeddings = []

    try:
        for start in range(0, len(texts), EMBEDDING_BATCH_SIZE):
            batch = texts[start:start + EMBEDDING_BATCH_SIZE]
            response = client.embeddings.create(
                model=_embedding_model(),
                input=batch,
            )
            embeddings.extend(
                item.embedding
                for item in response.data
            )
    except OpenAIError as error:
        raise ManualKnowledgeUnavailable(
            "OpenAI Embeddings API временно недоступен"
        ) from error

    if len(embeddings) != len(texts):
        raise ManualKnowledgeUnavailable(
            "Embeddings API вернул неполный результат"
        )

    return embeddings


def index_manual(
    equipment_id: str,
    file_path: Path,
    filename: str,
) -> dict:
    if not equipment_exists(equipment_id):
        raise ValueError(
            f"Оборудование не найдено: {equipment_id}"
        )

    file_bytes = file_path.read_bytes()
    sha256 = hashlib.sha256(file_bytes).hexdigest()

    existing_document = next(
        (
            document
            for document in list_manual_documents(equipment_id)
            if document["sha256"] == sha256
        ),
        None,
    )

    if existing_document is not None:
        return {
            "created": False,
            "document": existing_document,
            "embedding_model": _embedding_model(),
        }

    page_count, chunks = _extract_chunks(file_path)
    embeddings = _create_embeddings(
        [chunk["content"] for chunk in chunks]
    )

    for chunk, embedding in zip(chunks, embeddings, strict=True):
        chunk["embedding"] = embedding

    document, created = save_manual_document(
        equipment_id=equipment_id,
        filename=filename,
        sha256=sha256,
        page_count=page_count,
        chunks=chunks,
    )

    return {
        "created": created,
        "document": document,
        "embedding_model": _embedding_model(),
    }


def _cosine_similarity(
    left: list[float],
    right: list[float],
) -> float:
    if len(left) != len(right):
        return 0.0

    dot_product = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))

    if left_norm == 0 or right_norm == 0:
        return 0.0

    return dot_product / (left_norm * right_norm)


def search_manual(
    equipment_id: str,
    query: str,
    limit: int = 5,
) -> dict:
    clean_query = query.strip()

    if not clean_query:
        raise ValueError("Поисковый запрос не может быть пустым")

    chunks = get_manual_chunks(equipment_id)

    if not chunks:
        raise ValueError(
            f"Для {equipment_id} не загружена инструкция"
        )

    query_embedding = _create_embeddings([clean_query])[0]

    for chunk in chunks:
        chunk["score"] = _cosine_similarity(
            query_embedding,
            chunk.pop("embedding"),
        )

    matches = sorted(
        chunks,
        key=lambda item: item["score"],
        reverse=True,
    )[:max(1, min(limit, 10))]

    for match in matches:
        match["score"] = round(match["score"], 4)
        match["citation"] = (
            f"{match['filename']}, стр. {match['page_number']}"
        )

    return {
        "equipment_id": equipment_id,
        "query": clean_query,
        "embedding_model": _embedding_model(),
        "matches": matches,
    }
