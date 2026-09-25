"""Repository statistics calculation."""

from __future__ import annotations

from ingestion.models import FileRecord, RepositoryStatistics


def calculate_statistics(
    files: list[FileRecord],
    total_directories: int,
    top_n_largest: int = 10,
) -> RepositoryStatistics:
    """Compute aggregate statistics from a list of *FileRecord* objects."""
    lang_counts: dict[str, int] = {}
    total_lines = 0
    test_files: list[FileRecord] = []
    doc_files: list[FileRecord] = []
    config_files: list[FileRecord] = []

    for f in files:
        lang_counts[f.language.value] = lang_counts.get(f.language.value, 0) + 1
        total_lines += f.metadata.line_count
        if f.is_test_file:
            test_files.append(f)
        if f.is_documentation:
            doc_files.append(f)
        if f.is_configuration:
            config_files.append(f)

    lang_counts = dict(
        sorted(lang_counts.items(), key=lambda kv: kv[1], reverse=True)
    )
    largest = sorted(files, key=lambda f: f.metadata.size_bytes, reverse=True)[
        :top_n_largest
    ]

    return RepositoryStatistics(
        total_files=len(files),
        total_directories=total_directories,
        total_lines=total_lines,
        files_by_language=lang_counts,
        largest_files=largest,
        test_files=test_files,
        documentation_files=doc_files,
        configuration_files=config_files,
    )
