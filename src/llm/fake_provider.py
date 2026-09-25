"""Fake/Mock LLM provider for deterministic offline testing and mock mode."""

from __future__ import annotations

import hashlib
import math
import re
from typing import Optional

from llm.base import LLMProvider


class FakeLLMProvider(LLMProvider):
    """Offline mock LLM provider generating deterministic embeddings and grounded responses."""

    def __init__(
        self,
        default_response: Optional[str] = None,
        dimensions: int = 64,
    ) -> None:
        self.default_response = default_response
        self.dimensions = dimensions
        self.call_count = 0
        self.last_prompt: Optional[str] = None
        self.last_system_prompt: Optional[str] = None

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1000,
        temperature: float = 0.0,
    ) -> str:
        """Generate a realistic grounded mock answer based on the provided context."""
        self.call_count += 1
        self.last_prompt = prompt
        self.last_system_prompt = system_prompt

        if self.default_response is not None:
            return self.default_response

        # Extract question if present
        q_match = re.search(r"Question:\s*(.+?)(?:\n\n|\nRepository Context:|$)", prompt, re.DOTALL)
        question = q_match.group(1).strip() if q_match else prompt
        low_q = question.lower()

        # Check if context contains any source information
        citation_matches = re.findall(
            r"([a-zA-Z0-9_\-./\\]+\.[a-zA-Z0-9_]+):(\d+)(?:-(\d+))?", prompt
        )

        has_context = bool(citation_matches) and (
            "Repository Context:" in prompt or "Repository Context" in prompt
        )
        if not has_context:
            return "The provided repository context does not contain enough information to answer this question."

        # Case 1: Questions about classes ("What classes exist?")
        if "class" in low_q:
            classes_found: list[tuple[str, str, int, int]] = []
            # Check structural entity lines: "- CLASS: AppConfig (📄 src/models.py:8-13)"
            struct_matches = re.findall(
                r"CLASS:\s*([A-Za-z0-9_]+)\s*\(📄\s*([a-zA-Z0-9_\-./\\]+\.[a-zA-Z0-9_]+):(\d+)-(\d+)\)",
                prompt,
            )
            for cname, fpath, sline, eline in struct_matches:
                classes_found.append((cname, fpath, int(sline), int(eline)))

            # Check chunks that explicitly define classes: "Class: <name>"
            chunk_blocks = re.findall(
                r"--- 📄\s*([a-zA-Z0-9_\-./\\]+\.[a-zA-Z0-9_]+):(\d+)-(\d+)[^\n]*---\s*\n(?:[^\n]*\n)*?Class:\s*([A-Za-z0-9_]+)",
                prompt,
            )
            for fpath, sline, eline, cname in chunk_blocks:
                classes_found.append((cname, fpath, int(sline), int(eline)))

            # Deduplicate by class name
            seen_classes: set[str] = set()
            unique_classes = []
            for item in classes_found:
                if item[0] not in seen_classes:
                    seen_classes.add(item[0])
                    unique_classes.append(item)

            if unique_classes:
                ans_lines = ["Based on the repository context, the following classes exist:"]
                sources = []
                for cname, fpath, sline, eline in unique_classes:
                    ans_lines.append(f"- `{cname}` in `{fpath}:{sline}-{eline}`")
                    sources.append(f"📄 {fpath}:{sline}-{eline} ({cname})")

                ans_lines.append("\nSources:")
                ans_lines.extend(sources)
                return "\n".join(ans_lines)
            else:
                return "Based on the repository context, no class definitions were found."

        # Case 2: Questions about authentication ("How does authentication work?")
        if "auth" in low_q or "authentication" in low_q:
            # Check if there is actual authentication logic in the context
            has_auth_code = any(
                term in prompt.lower()
                for term in ("jwt", "bcrypt", "oauth", "session", "login", "password_hash")
            )
            # Check if changelog or config mentioned auth
            has_changelog_auth = "authentication" in prompt.lower() or "auth" in prompt.lower()

            if not has_auth_code:
                # Honestly state that context is insufficient / no auth logic exists
                evidence_notes = []
                citations = []
                for fpath, sline, eline in citation_matches:
                    norm = fpath.replace("\\", "/")
                    if "changelog" in norm.lower():
                        evidence_notes.append(f"`{fpath}` notes that user authentication was added")
                        citations.append(f"📄 {fpath}:{sline}-{eline or sline}")
                    elif "config" in norm.lower():
                        evidence_notes.append(f"`{fpath}` contains an auth configuration flag")
                        citations.append(f"📄 {fpath}:{sline}-{eline or sline}")

                if evidence_notes:
                    evidence_str = "While " + " and ".join(evidence_notes) + ", "
                else:
                    evidence_str = ""

                ans_lines = [
                    f"The available repository context is insufficient to describe an authentication architecture. "
                    f"{evidence_str}no authentication service, session management, or credential verification implementation exists in the analyzed source code.",
                ]
                if citations:
                    ans_lines.append("\nSources:")
                    ans_lines.extend(list(dict.fromkeys(citations))[:3])
                return "\n".join(ans_lines)

        # Case 3: General grounded response
        # Extract mentioned functions and classes
        class_matches = re.findall(r"Class:\s*([A-Za-z0-9_]+)", prompt)
        func_matches = re.findall(r"Function:\s*([A-Za-z0-9_]+)", prompt)
        paren_matches = re.findall(r"\(([A-Za-z0-9_]+)\)", prompt)

        entities_desc = []
        if class_matches:
            entities_desc.append(f"classes {', '.join(sorted(set(class_matches))[:2])}")
        if func_matches:
            entities_desc.append(f"functions {', '.join(sorted(set(func_matches))[:2])}")
        if paren_matches and not class_matches and not func_matches:
            entities_desc.append(f"entity {', '.join(sorted(set(paren_matches))[:2])}")

        focus = " and ".join(entities_desc) if entities_desc else "the analyzed codebase components"

        response_lines = [
            f"Based on the repository context, {focus} implement the relevant functionality.",
            "The implementation is structured across the identified modules.",
            "",
            "Sources:",
        ]

        seen_cites = set()
        for match in citation_matches[:3]:
            fpath, start, end = match[0], match[1], match[2] or match[1]
            cite_str = f"📄 {fpath}:{start}-{end}"
            if cite_str not in seen_cites:
                seen_cites.add(cite_str)
                response_lines.append(cite_str)

        return "\n".join(response_lines)

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate deterministic pseudo-embeddings using token hashing with cosine similarity."""
        embeddings = []
        for text in texts:
            vec = [0.0] * self.dimensions
            tokens = re.findall(r"\w+", text.lower())
            if not tokens:
                embeddings.append(vec)
                continue

            for token in tokens:
                h = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
                idx = h % self.dimensions
                vec[idx] += 1.0

            # L2 normalize vector
            norm = math.sqrt(sum(x * x for x in vec))
            if norm > 0:
                vec = [x / norm for x in vec]

            embeddings.append(vec)
        return embeddings
