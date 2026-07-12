"""
evaluation/golden_set_generator.py
==================================
Golden Set Generator Service.

PURPOSE:
    Reads all processed legal documents from metadata/documents.csv and metadata/parsed/*.json.
    Automatically generates 3-5 meaningful legal questions (Queries) per document, along with
    ground truth answers and precise citations.
    Supports live generation using Google Gemini, or falls back to a high-fidelity local
    rule-based parser if no API key is configured.
    Outputs the resulting dataset to metadata/golden_set.csv and metadata/golden_set.xlsx.
"""

from __future__ import annotations

import csv
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd
from app.core.config import Settings
from app.llm.base_provider import LLMProvider
from app.logging.logger import get_logger

log = get_logger("evaluation")


class GoldenSetGenerator:
    """
    Automatically generates a Golden Set of legal Q&A pairs from parsed documents.
    """

    def __init__(
        self,
        settings: Settings,
        llm_provider: LLMProvider,
        workspace_dir: str | Path = r"d:\Legal-AI-Assistant-RAG",
    ) -> None:
        self.settings = settings
        self.llm_provider = llm_provider
        self.workspace_dir = Path(workspace_dir)
        self.metadata_dir = self.workspace_dir / "metadata"
        self.parsed_dir = self.metadata_dir / "parsed"
        self.documents_csv = self.metadata_dir / "documents.csv"
        self.output_csv = self.metadata_dir / "golden_set.csv"
        self.output_xlsx = self.metadata_dir / "golden_set.xlsx"
        self.cache_json = self.metadata_dir / "golden_set_cache.json"

    def _is_boilerplate(self, text: str) -> bool:
        """Determines if a page contains boilerplate or TOC markers."""
        text_upper = text.upper()
        indicators = [
            "OMB CONTROL NUMBERS",
            "TABLE OF CONTENTS",
            "TABLE I",
            "TABLE II",
            "CROSS-REFERENCE",
            "CODE OF FEDERAL REGULATIONS",
            "FEDERAL REGISTER",
            "THIS VOLUME CONTAINS",
            "PAST PROVISIONS OF THE CODE",
            "INCORPORATION BY REFERENCE",
            "EXPLANATION",
            "LIST OF CFR SECTIONS",
            "CFR INDEX AND FINDING AIDS",
            "PUBLISHED BY THE OFFICE OF THE FEDERAL REGISTER",
            "INDEX TO THE",
            "HOW TO USE THIS",
            "ABOUT THIS PUBLICATION",
        ]
        for ind in indicators:
            if ind in text_upper:
                if text.count("....") > 5 or text.count("----") > 5 or len(text) < 1200:
                    return True
        return False

    def _select_source_pages(
        self, pages: List[Dict[str, Any]], category: str, count: int = 3
    ) -> List[Tuple[int, str]]:
        """Selects up to `count` distinct pages with rich unique content."""
        # Determine page search sequence based on category
        if category == "Acts":
            search_sequence = list(range(14, min(len(pages), 50))) + list(range(5, len(pages)))
        elif category == "Tax":
            search_sequence = list(range(9, min(len(pages), 40))) + list(range(3, len(pages)))
        elif category == "Legal_opinion":
            search_sequence = list(range(4, min(len(pages), 30))) + list(range(1, len(pages)))
        else:
            search_sequence = list(range(3, min(len(pages), 25))) + list(range(1, len(pages)))

        selected: List[Tuple[int, str]] = []
        for idx in search_sequence:
            if len(selected) >= count:
                break
            if idx >= len(pages):
                continue
            p = pages[idx]
            page_num = p.get("page", idx + 1)
            text = p.get("text", "").strip()

            # Ensure we have decent text content and it's not boilerplate
            if len(text) > 1000 and not self._is_boilerplate(text):
                # Avoid selecting the same page number twice
                if not any(item[0] == page_num for item in selected):
                    selected.append((page_num, text))

        # Fallback if we couldn't find enough smart pages
        if len(selected) < count and pages:
            sorted_pages = sorted(pages, key=lambda x: len(x.get("text", "")), reverse=True)
            for p in sorted_pages:
                if len(selected) >= count:
                    break
                page_num = p.get("page", 5)
                text = p.get("text", "")
                if not any(item[0] == page_num for item in selected):
                    selected.append((page_num, text))

        return selected

    def _generate_local_qa(self, doc_name: str, category: str, page_num: int, page_text: str) -> Dict[str, str]:
        """Local rule-based generator to extract specific legal rules and holdings."""
        # Split text into sentences using simple regex
        sentences = re.split(r'(?<=[.!?])\s+', page_text)
        
        best_sentence = ""
        best_score = -1
        best_q = ""
        best_a = ""
        best_citation = f"Page {page_num}"
        
        # Better section match regex requiring at least one digit
        sec_pattern = r'(?:section|§)\s*([a-zA-Z0-9]*[0-9]+[a-zA-Z0-9\.\-\(\)]*)'
        
        for s in sentences:
            s_clean = s.strip().replace("\n", " ")
            s_clean = re.sub(r'\s+', ' ', s_clean)
            
            # Sentence length constraints for readable Q&A
            if len(s_clean) < 100 or len(s_clean) > 280:
                continue
                
            # Grammatical constraint: must start with a capital letter
            if not s_clean[0].isupper():
                continue
                
            # Skip header lines, subparts, and TOC dividers
            s_upper = s_clean.upper()
            if any(kw in s_upper for kw in ("SUBCHAPTER", "SUBPART", "PART ", "[RESERVED]", "TABLE OF CONTENTS", "Pt. ", "PUBLICATION ", "CHAPTER ")):
                continue
                
            # Skip academic/journal citations, footnotes, and bibliography lines
            if any(kw in s_upper for kw in ("LAW REVIEW", "JOURNAL ON", "JOURNAL OF", "YALE LAW", "HARVARD LAW", "COLUMBIA LAW", "SUPREME COURT REVIEW", "UNIVERSITY PRESS", "CONGRESSIONAL RESEARCH SERVICE")):
                continue
            if re.search(r'\b(?:[J]\b|L\b|Rev\b|Vol\b|No\b)\.?\s+\d+|\b\d{4}\b\s*\)|\[\d{4}\]|http', s_clean):
                continue
            
            # Score keywords matching category themes
            score = 0
            if category == "Acts":
                score += len(re.findall(r'(section|§|shall|must|pursuant|under|authority|regulation)', s_clean, re.I))
            elif category == "CourtJudgement":
                score += len(re.findall(r'(held|concluded|ruled|court|petitioner|respondent|affirmed|liability)', s_clean, re.I))
            elif category == "Tax":
                score += len(re.findall(r'(limit|credit|deduct|exclude|taxpayer|percent|rate|income|filing)', s_clean, re.I))
            else: # Legal_opinion
                score += len(re.findall(r'(opinion|memo|statutory|policy|congress|precedent|authority|constitutional)', s_clean, re.I))
                
            if score > best_score:
                q = ""
                # Heuristic Rule 1: Section references (with digits)
                sec_match = re.search(sec_pattern, s_clean, re.I)
                if sec_match:
                    sec = sec_match.group(1)
                    q = f"What regulation or requirement is specified under Section {sec}?"
                    best_citation = f"Section {sec}"
                
                # Heuristic Rule 2: Court rulings
                elif "held that" in s_clean.lower() or "concluded that" in s_clean.lower():
                    clause_match = re.search(r'(?:held|concluded) that\s+([^,.]+)', s_clean, re.I)
                    if clause_match:
                        clause = clause_match.group(1).strip()
                        if clause:
                            clause = clause[0].lower() + clause[1:]
                        q = f"What was the court's determination regarding whether {clause}?"
                        best_citation = f"Court Opinion"
                        
                # Heuristic Rule 3: Tax limits
                elif "limited to" in s_clean.lower() or "limit of" in s_clean.lower():
                    clause_match = re.search(r'(?:limited to|limit of)\s+([^,.]+)', s_clean, re.I)
                    if clause_match:
                        clause = clause_match.group(1).strip()
                        if clause:
                            clause = clause[0].lower() + clause[1:]
                        q = f"What limitation is established regarding {clause}?"
                        best_citation = f"Limitation Provision"
                
                # Fallback: key phrase extraction
                if not q:
                    words = s_clean.split()
                    if len(words) >= 6:
                        phrase = " ".join(words[:6]).strip(",. ")
                        # Clean leading numbers/subchapters/dates/quotes from the phrase
                        clean_phrase = re.sub(r'^(?:[0-9a-zA-Z\.\-\(\)]+\s+)?(?:SUBCHAPTER|PART|SECTION|Pt\.|Subpart|Appendix|vi\b|iv\b|ix\b|x\b)\s*[A-Z0-9\.\-\(\)\s]*', '', phrase, flags=re.I)
                        clean_phrase = clean_phrase.strip(",. \"'‘‘’’“”")
                        # Strip common transition words
                        clean_phrase = re.sub(r'^(?:then|also|however|thus|therefore|moreover|indeed|furthermore|accordingly)\s+', '', clean_phrase, flags=re.I)
                        
                        if clean_phrase:
                            # Apply smart transformations for high realism
                            if clean_phrase.lower().startswith("if "):
                                phrase_without_if = clean_phrase[3:].strip()
                                q = f"What rules or consequences apply if {phrase_without_if}?"
                            elif clean_phrase.lower().startswith("before "):
                                phrase_without_before = clean_phrase[7:].strip()
                                q = f"What was the status or rule before {phrase_without_before}?"
                            elif clean_phrase.lower().startswith("among "):
                                phrase_without_among = clean_phrase[6:].strip()
                                q = f"What guidelines apply among {phrase_without_among}?"
                            else:
                                q = f"What is defined or described concerning '{clean_phrase}'?"
                        else:
                            if category == "Acts":
                                q = "What statutory rules or administrative provisions are detailed in this section?"
                            elif category == "CourtJudgement":
                                q = "What court holdings or legal standards are detailed in this opinion?"
                            elif category == "Tax":
                                q = "What tax guidelines or compliance rules are detailed in this publication?"
                            else:
                                q = "What legal analysis or policy rules are detailed in this opinion?"
                    else:
                        if category == "Acts":
                            q = "What statutory rules or administrative provisions are detailed in this section?"
                        elif category == "CourtJudgement":
                            q = "What court holdings or legal standards are detailed in this opinion?"
                        elif category == "Tax":
                            q = "What tax guidelines or compliance rules are detailed in this publication?"
                        else:
                            q = "What legal analysis or policy rules are detailed in this opinion?"
                    best_citation = f"Page {page_num}"
                
                best_sentence = s_clean
                best_score = score
                best_q = q
                best_a = s_clean
                
        if not best_q:
            # Absolute fallback based on category
            if category == "Acts":
                best_q = "What statutory guidelines or regulatory provisions are detailed in this section of the Act?"
            elif category == "CourtJudgement":
                best_q = "What are the primary holdings or legal conclusions detailed in this case opinion?"
            elif category == "Tax":
                best_q = "What tax regulations or compliance guidelines are detailed in this publication?"
            else:
                best_q = "What legal analyses or policy standards are detailed in this advisory opinion?"
            best_a = page_text[:200].strip() + "..."
            best_citation = f"Page {page_num}"
            
        # Post-process and refine the Query, Answer, and Citation
        # 1. Clean Answer: strip headers, edit years, etc.
        ans = best_a
        # Remove common CFR/PDF headers and footers
        ans = re.sub(
            r'^(?:Page \d+\s+)?(?:TITLE \d+\s*—\s*[A-Z\s]+|Federal Deposit Insurance Corporation|Internal Revenue Service, Treasury|CFR Ch\. [A-Z0-9\.\s]+|\d+\s+CFR\s+Ch\.\s+[A-Z0-9\.\s\(\)]+|\d+\s+Federal\s+Register|\[\d+\s+FR\s+[^\]]+\]|SUBCHAPTER [A-Z\s\(\)\-]+|PART [A-Z0-9\s]+|Subpart [A-Z0-9\s]+)\s*(?:§\s*\d+\.\d+|\d+\.\d+|\d+|§\s*\d+)?\s*',
            '',
            ans,
            flags=re.I
        )
        ans = ans.strip()
        
        # Clean hyphenated words
        ans = ans.replace("para- graphs", "paragraphs")
        ans = ans.replace("re- tain", "retain")
        ans = ans.replace("liabil- ity", "liability")
        ans = ans.replace("pre- payment", "prepayment")
        ans = ans.replace("regu- lation", "regulation")
        ans = ans.replace("estab- lish", "establish")
        ans = ans.replace("commit- ments", "commitments")
        ans = ans.replace("re- duced", "reduced")
        if ans.startswith("cept "):
            ans = "Except " + ans[5:]
            
        if ans and ans[0].islower():
            ans = ans[0].upper() + ans[1:]
            
        # Try to find a quoted term inside the best sentence
        quoted_term = ""
        quoted_match = re.search(r'[‘‘’’\'"“”]([^‘‘’’\'"“”]{2,40})[‘‘’’\'"“”]', best_sentence)
        if quoted_match:
            candidate = quoted_match.group(1).strip()
            # Clean candidate from quotes/brackets/punctuation
            candidate = re.sub(r"[‘‘’’'\"“”]", "", candidate)
            candidate = re.sub(r"^\([0-9a-zA-Z\.\-]+\)\s*", "", candidate)
            candidate = candidate.strip("][)(.-,; \t\n\r")
            
            # Ensure it is a valid term: no apostrophes, no common conjunctions/verbs/pronouns, not empty
            if candidate and len(candidate) > 2 and len(candidate) < 30:
                words = candidate.split()
                invalid_words = {
                    "and", "or", "for", "of", "to", "with", "in", "on", "at", 
                    "by", "was", "were", "is", "are", "been", "should", "would", 
                    "could", "have", "has", "had", "via", "through", "under", "over", "from",
                    "its", "their", "your", "my", "our", "his", "her", "the", "a", "an", "this", "that",
                    "but", "as", "if", "than", "not", "no", "yes"
                }
                words_lower = [w.lower().strip(".,;:!?()") for w in words]
                if len(words) > 1 and any(w in invalid_words for w in words_lower):
                    pass
                elif any(w in candidate.lower() for w in ("don't", "don’t", "can't", "can’t", "won't", "won’t", "it's", "it’s", "doesn't", "doesn’t")):
                    pass
                else:
                    quoted_term = candidate

        # 2. Refine Query to make it sound completely natural
        q = best_q
        if quoted_term and len(quoted_term) > 2:
            term = quoted_term
            if category == "Tax":
                q = f"How is the term '{term}' defined or applied under the tax regulations?"
            elif category == "Acts":
                q = f"What is the statutory definition or scope of the term '{term}' under the Act?"
            elif category == "CourtJudgement":
                q = f"How does the court interpret or define the term '{term}' in this judgment?"
            else:
                q = f"What is the definition or context of the term '{term}' outlined in this opinion?"
        else:
            # Let's inspect the sentence text and perform smart transformation to natural questions
            s_lower = best_sentence.lower()
            transformed = False
            
            # Pattern A: "use X if Y" or "apply X if Y"
            use_match = re.search(r'\b(?:use|apply)\s+([a-zA-Z0-9\s\-]{3,30})\s+if\b', s_lower)
            if use_match:
                item = use_match.group(1).strip()
                q = f"Under what conditions or guidelines should a taxpayer or entity use or apply {item}?"
                transformed = True
                
            # Pattern B: "limited to X"
            elif "limited to" in s_lower:
                limit_match = re.search(r'([a-zA-Z0-9\s\-]{3,30})\s+(?:is|shall be|are)\s+limited to', s_lower)
                if limit_match:
                    item = limit_match.group(1).strip()
                    q = f"What limitations or caps apply to {item} under these regulations?"
                    transformed = True
                    
            # Pattern C: "must file X" or "required to file X"
            elif "file" in s_lower and "return" in s_lower:
                q = "What are the specific filing requirements and deadlines for tax returns mentioned here?"
                transformed = True
                
            # Pattern D: "excludes X from gross income" or "exclude X"
            elif "exclude" in s_lower and "income" in s_lower:
                q = "What income items are excluded from gross income calculations under this section?"
                transformed = True

            if not transformed:
                words_list = ans.split()
                remaining_text = " ".join(words_list[1:]) if len(words_list) > 1 else ""
                capitalized_words = re.findall(r'\b[A-Z][a-z]+\b', remaining_text)
                stops = {
                    "Page", "Title", "Act", "Section", "Part", "Subpart", "Federal", "United", "States", 
                    "Court", "Treasury", "Internal", "Revenue", "Service", "IRS", "Congress", "Senate", "House",
                    "He", "She", "They", "We", "You", "I", "It", "This", "That", "These", "Those", "Under", "According",
                    "Based", "However", "Therefore", "Moreover", "Thus", "Instead", "Indeed", "Furthermore", "Accordingly",
                    "Generally", "Specifically", "Particularly", "Initially", "First", "Second", "Third", "Finally"
                }
                filtered = [w for w in capitalized_words if w not in stops]
                if filtered:
                    subject = " ".join(filtered[:2])
                    if category == "Tax":
                        q = f"What tax guidelines or requirements are detailed concerning {subject}?"
                    elif category == "Acts":
                        q = f"What statutory rules or administrative provisions apply to {subject}?"
                    elif category == "CourtJudgement":
                        q = f"What was the court's holding or analysis regarding the role of {subject}?"
                    else:
                        q = f"What policy or legal standard is discussed in relation to {subject}?"
                else:
                    if category == "Acts":
                        q = "What statutory guidelines or regulatory provisions are detailed in this section of the Act?"
                    elif category == "CourtJudgement":
                        q = "What are the primary holdings or legal conclusions detailed in this case opinion?"
                    elif category == "Tax":
                        q = "What tax regulations or compliance guidelines are detailed in this publication?"
                    else:
                        q = "What legal analyses or policy standards are detailed in this advisory opinion?"
                
        # If query is still generic, refine it based on content
        if "general rules or guidelines" in q.lower() or "legal guideline or rule" in q.lower() or "what tax guidelines" in q.lower() or "what statutory rules" in q.lower() or "what policy or legal standard" in q.lower():
            # Only run if we don't have a specific subject in query
            if not any(kw in q.lower() for kw in ("concerning", "relation to", "role of", "apply to")):
                words_list = ans.split()
                remaining_text = " ".join(words_list[1:]) if len(words_list) > 1 else ""
                capitalized_words = re.findall(r'\b[A-Z][a-z]+\b', remaining_text)
                stops = {
                    "Page", "Title", "Act", "Section", "Part", "Subpart", "Federal", "United", "States", 
                    "Court", "Treasury", "Internal", "Revenue", "Service", "IRS", "Congress", "Senate", "House",
                    "He", "She", "They", "We", "You", "I", "It", "This", "That", "These", "Those", "Under", "According",
                    "Based", "However", "Therefore", "Moreover", "Thus", "Instead", "Indeed", "Furthermore", "Accordingly",
                    "Generally", "Specifically", "Particularly", "Initially", "First", "Second", "Third", "Finally"
                }
                filtered = [w for w in capitalized_words if w not in stops]
                if filtered:
                    subject = filtered[0]
                    if category == "Tax":
                        q = f"What tax guidelines or requirements are detailed concerning {subject}?"
                    elif category == "Acts":
                        q = f"What statutory rules or administrative provisions apply to {subject}?"
                    elif category == "CourtJudgement":
                        q = f"What was the court's holding or analysis regarding the role of {subject}?"
                    else:
                        q = f"What policy or legal standard is discussed in relation to {subject}?"
                else:
                    if category == "Acts":
                        q = "What statutory guidelines or regulatory provisions are detailed in this section of the Act?"
                    elif category == "CourtJudgement":
                        q = "What are the primary holdings or legal conclusions detailed in this case opinion?"
                    elif category == "Tax":
                        q = "What tax regulations or compliance guidelines are detailed in this publication?"
                    else:
                        q = "What legal analyses or policy standards are detailed in this advisory opinion?"

        # 3. Clean and build exact Citation
        citation = f"Page {page_num}"
        sec_match = re.search(sec_pattern, ans, re.I)
        if sec_match:
            sec = sec_match.group(1).strip(",.()")
            if category == "Acts":
                title_match = re.search(r'Title(\d+)', doc_name, re.I)
                title = f"Title {title_match.group(1)}" if title_match else "CFR"
                citation = f"{title} U.S.C. § {sec}"
            elif category == "Tax":
                citation = f"IRC § {sec}"
            else:
                citation = f"Section {sec}, Page {page_num}"
        else:
            if category == "CourtJudgement":
                citation = f"Court Opinion, Page {page_num}"
            elif category == "Legal_opinion":
                citation = f"Legal Memorandum, Page {page_num}"
            elif category == "Tax":
                pub_match = re.search(r'Publication_([0-9a-zA-Z]+)', doc_name, re.I)
                pub = f"IRS Pub {pub_match.group(1)}" if pub_match else "IRS Publication"
                citation = f"{pub}, Page {page_num}"

        return {
            "Query": q,
            "Ground_Truth_Answer": ans,
            "Citation": citation
        }

    async def _generate_qa_for_page(
        self, doc_name: str, category: str, page_num: int, page_text: str
    ) -> List[Dict[str, Any]]:
        """Queries the LLM provider to generate a Q&A pair with citation."""
        prompt = f"""You are an expert legal analyst. Analyze the following legal text from page {page_num} of the document '{doc_name}' ({category}):

TEXT:
{page_text}

Generate exactly 1 highly realistic, specific legal question (Query) that can be answered ONLY using the provided text. For each question, provide:
1. The Query: A realistic and specific question that a lawyer or legal professional would ask. Avoid generic queries. Reference specific section numbers, facts, rules, or decisions mentioned in the text.
2. The Ground Truth Answer: A detailed, complete, and accurate answer derived solely and directly from the text. Do not make assumptions or use external knowledge.
3. The Citation: The exact section, subsection, paragraph, or page detail from the text that supports the answer.

Format the output strictly as a JSON object with keys: "Query", "Ground_Truth_Answer", "Citation".
Do not include any markdown code wrappers (such as ```json) or other conversational text. Return ONLY the raw JSON string.
"""
        try:
            response_text = await self.llm_provider.generate(prompt)
            # Remove any possible markdown wrappers
            clean_json = re.sub(r"```json\s*", "", response_text)
            clean_json = re.sub(r"```\s*", "", clean_json).strip()
            
            data = json.loads(clean_json)
            normalized = {
                "Query": data.get("Query", data.get("query", "")),
                "Ground_Truth_Answer": data.get("Ground_Truth_Answer", data.get("ground_truth_answer", "")),
                "Citation": data.get("Citation", data.get("citation", "")),
            }
            if normalized["Query"] and normalized["Ground_Truth_Answer"]:
                return [normalized]
        except Exception as exc:
            log.warning(
                "LLM generation failed for {doc} page {page} | error={err}",
                doc=doc_name,
                page=page_num,
                err=str(exc),
            )
        
        return []

    async def generate_golden_set(self) -> int:
        """
        Orchestrates Golden Set generation.
        Returns the number of generated records.
        """
        log.info("Starting Golden Set generation pipeline...")
        
        if not self.documents_csv.exists():
            log.error("Documents registry CSV not found at {path}", path=self.documents_csv)
            raise FileNotFoundError(f"Missing {self.documents_csv}")

        # Check for pre-cached Q&A file
        cached_qa = {}
        if self.cache_json.exists():
            try:
                with open(self.cache_json, "r", encoding="utf-8") as f:
                    cached_qa = json.load(f)
                log.info("Loaded pre-cached Q&A dataset with {n} documents", n=len(cached_qa))
            except Exception as exc:
                log.warning("Failed to load cache_json | error={err}", err=str(exc))

        records: List[Dict[str, Any]] = []
        duplicate_mappings: List[Tuple[Dict[str, Any], str]] = []
        unique_qa_by_file: Dict[str, List[Dict[str, Any]]] = {}
        id_to_name: Dict[str, str] = {}

        # 1. Parse documents registry CSV
        with open(self.documents_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames or []
            first_col = fieldnames[0] if fieldnames else ""
            if first_col.startswith('\ufeff'):
                first_col = first_col.replace('\ufeff', '')
            cleaned_fieldnames = [first_col] + [fn.strip() for fn in fieldnames[1:]]
            
            f.seek(0)
            reader = csv.DictReader(f, fieldnames=cleaned_fieldnames)
            next(reader) # skip headers

            # Detect if a valid Gemini API Key is configured
            has_api_key = self.settings.gemini_api_key and not self.settings.gemini_api_key.startswith("<YOUR_")

            for row in reader:
                doc_id = row.get("Document_ID", "").strip()
                doc_name = row.get("File_Name", "").strip()
                category = row.get("Category", "").strip()
                status = row.get("Status", "").strip()
                is_duplicate_of = row.get("Is_Duplicate_Of", "").strip()

                if not doc_id or not doc_name:
                    continue

                if status == "duplicate":
                    duplicate_mappings.append((row, is_duplicate_of))
                    continue

                log.info("Processing unique document: {doc}", doc=doc_name)
                id_to_name[doc_id] = doc_name
                
                # Check cache first
                if doc_name in cached_qa:
                    log.info("Using cached Q&A entries for {doc}", doc=doc_name)
                    doc_entries = cached_qa[doc_name]
                    unique_qa_by_file[doc_name] = doc_entries
                    for entry in doc_entries:
                        records.append({
                            "Query": entry["Query"],
                            "Ground_Truth_Answer": entry["Ground_Truth_Answer"],
                            "Source_Document": doc_name,
                            "Page_Number": entry["Page_Number"],
                            "Category": category,
                            "Citation": entry["Citation"],
                        })
                    continue

                # If no cache, read parsed JSON
                json_path = self.parsed_dir / f"{doc_id}.json"
                if not json_path.exists():
                    log.warning("Parsed file {path} not found. Skipping.", path=json_path)
                    continue

                try:
                    with open(json_path, "r", encoding="utf-8") as jf:
                        doc_data = json.load(jf)
                except Exception as exc:
                    log.error("Failed to read parsed file {path} | error={err}", path=json_path, err=str(exc))
                    continue

                pages = doc_data.get("pages", [])
                # Select exactly 3 pages
                source_pages = self._select_source_pages(pages, category, count=3)
                
                doc_entries = []
                for page_num, text in source_pages:
                    clean_text = re.sub(r"\s+", " ", text)[:2000]
                    
                    if has_api_key:
                        # Call LLM provider
                        qa_items = await self._generate_qa_for_page(doc_name, category, page_num, clean_text)
                        for item in qa_items:
                            entry = {
                                "Query": item["Query"],
                                "Ground_Truth_Answer": item["Ground_Truth_Answer"],
                                "Source_Document": doc_name,
                                "Page_Number": page_num,
                                "Category": category,
                                "Citation": item["Citation"],
                            }
                            doc_entries.append(entry)
                            records.append(entry)
                    else:
                        # Call Rule-Based Local Generator
                        item = self._generate_local_qa(doc_name, category, page_num, clean_text)
                        entry = {
                            "Query": item["Query"],
                            "Ground_Truth_Answer": item["Ground_Truth_Answer"],
                            "Source_Document": doc_name,
                            "Page_Number": page_num,
                            "Category": category,
                            "Citation": item["Citation"],
                        }
                        doc_entries.append(entry)
                        records.append(entry)

                unique_qa_by_file[doc_name] = doc_entries
                log.info("Generated {n} questions for {doc}", n=len(doc_entries), doc=doc_name)

        # 2. Map duplicates to ensure consistency
        for dup_row, master_id in duplicate_mappings:
            dup_name = dup_row.get("File_Name", "").strip()
            dup_category = dup_row.get("Category", "").strip()
            
            # Find the master file name
            master_name = id_to_name.get(master_id)
            
            if master_name:
                master_entries = unique_qa_by_file.get(master_name, [])
                log.info("Copying {n} Q&A from master '{master}' to duplicate '{dup}'", n=len(master_entries), master=master_name, dup=dup_name)
                for entry in master_entries:
                    records.append({
                        "Query": entry["Query"],
                        "Ground_Truth_Answer": entry["Ground_Truth_Answer"],
                        "Source_Document": dup_name,
                        "Page_Number": entry["Page_Number"],
                        "Category": dup_category,
                        "Citation": entry["Citation"],
                    })
            else:
                log.warning("Master document ID {id} not found in registry for duplicate {dup}", id=master_id, dup=dup_name)

        if not records:
            log.warning("No golden set records were generated!")
            return 0

        # 3. Save output files
        df = pd.DataFrame(records)
        columns_order = ["Query", "Ground_Truth_Answer", "Source_Document", "Page_Number", "Category", "Citation"]
        df = df[columns_order]

        # Export CSV
        try:
            df.to_csv(self.output_csv, index=False, encoding="utf-8")
            log.info("Saved Golden Set CSV | path={path} | rows={n}", path=self.output_csv, n=len(df))
        except PermissionError:
            idx = 1
            while True:
                fallback_csv = self.metadata_dir / f"golden_set_generated_{idx}.csv"
                try:
                    df.to_csv(fallback_csv, index=False, encoding="utf-8")
                    log.warning("Permission denied on {path} (file locked). Saved CSV to fallback: {fallback}", path=self.output_csv, fallback=fallback_csv)
                    break
                except PermissionError:
                    idx += 1
                    if idx > 20:
                        log.error("All fallback CSV files are locked.")
                        break

        # Export Excel (XLSX)
        try:
            df.to_excel(self.output_xlsx, index=False, sheet_name="Golden Set")
            log.info("Saved Golden Set Excel | path={path} | rows={n}", path=self.output_xlsx, n=len(df))
        except PermissionError:
            idx = 1
            while True:
                fallback_xlsx = self.metadata_dir / f"golden_set_generated_{idx}.xlsx"
                try:
                    df.to_excel(fallback_xlsx, index=False, sheet_name="Golden Set")
                    log.warning("Permission denied on {path} (file locked). Saved Excel to fallback: {fallback}", path=self.output_xlsx, fallback=fallback_xlsx)
                    break
                except PermissionError:
                    idx += 1
                    if idx > 20:
                        log.error("All fallback Excel files are locked.")
                        break

        return len(df)
