"""
Structured Text Parser for NLP Service

Parses markdown-formatted text from DeepSeek OCR to extract:
- Document structure (headers, sections)
- Tables with rows and columns
- Lists and formatted elements
- Section context for improved entity recognition

This enables the NLP service to leverage the rich structure provided by DeepSeek OCR.
"""

import re
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum


class SectionType(str, Enum):
    """Types of document sections"""
    HEADER = "header"
    TABLE = "table"
    LIST = "list"
    PARAGRAPH = "paragraph"
    CODE = "code"
    METADATA = "metadata"


@dataclass
class TableCell:
    """Single cell in a table"""
    text: str
    row: int
    column: int
    is_header: bool = False


@dataclass
class TableStructure:
    """Structured representation of a table"""
    headers: List[str]
    rows: List[List[str]]
    raw_text: str
    start_line: int
    end_line: int
    
    def to_dict(self) -> Dict:
        return {
            "headers": self.headers,
            "rows": self.rows,
            "row_count": len(self.rows),
            "column_count": len(self.headers),
            "raw_text": self.raw_text
        }
    
    def get_column_values(self, column_name: str) -> List[str]:
        """Get all values from a specific column"""
        try:
            col_idx = self.headers.index(column_name)
            return [row[col_idx] if col_idx < len(row) else "" for row in self.rows]
        except ValueError:
            return []
    
    def find_rows_with_value(self, column_name: str, value: str) -> List[Dict[str, str]]:
        """Find rows where a column contains a specific value"""
        try:
            col_idx = self.headers.index(column_name)
            matching_rows = []
            for row in self.rows:
                if col_idx < len(row) and value.lower() in row[col_idx].lower():
                    row_dict = {header: row[i] if i < len(row) else "" 
                               for i, header in enumerate(self.headers)}
                    matching_rows.append(row_dict)
            return matching_rows
        except ValueError:
            return []


@dataclass
class DocumentSection:
    """A section of the document with structure information"""
    type: SectionType
    content: str
    level: int = 0  # For headers: 1-6, for others: nesting level
    title: Optional[str] = None
    start_line: int = 0
    end_line: int = 0
    metadata: Dict[str, Any] = None
    table: Optional[TableStructure] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class StructuredDocument:
    """Complete structured document representation"""
    raw_text: str
    sections: List[DocumentSection]
    tables: List[TableStructure]
    headers: List[Tuple[int, str]]  # (level, text)
    metadata: Dict[str, Any]
    
    def get_section_by_title(self, title: str) -> Optional[DocumentSection]:
        """Find section by title (case-insensitive)"""
        title_lower = title.lower()
        for section in self.sections:
            if section.title and section.title.lower() == title_lower:
                return section
        return None
    
    def get_sections_by_type(self, section_type: SectionType) -> List[DocumentSection]:
        """Get all sections of a specific type"""
        return [s for s in self.sections if s.type == section_type]
    
    def get_context_for_text(self, text: str) -> Optional[str]:
        """Get section context for a piece of text"""
        for section in self.sections:
            if text in section.content:
                return section.title or f"{section.type.value} section"
        return None


class MarkdownParser:
    """
    Parser for markdown-formatted text from DeepSeek OCR.
    
    Extracts document structure including:
    - Headers (# to ######)
    - Tables (| column | format |)
    - Lists (-, *, numbered)
    - Paragraphs
    """
    
    def __init__(self):
        self.header_pattern = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)
        self.table_row_pattern = re.compile(r'^\|(.+)\|$')
        self.table_separator_pattern = re.compile(r'^\|[\s\-:|]+\|$')
        self.list_pattern = re.compile(r'^[\s]*[-*]\s+(.+)$')
        self.numbered_list_pattern = re.compile(r'^[\s]*\d+\.\s+(.+)$')
    
    def parse(self, text: str) -> StructuredDocument:
        """
        Parse markdown text into structured document.
        
        Args:
            text: Markdown-formatted text
            
        Returns:
            StructuredDocument with extracted structure
        """
        lines = text.split('\n')
        sections: List[DocumentSection] = []
        tables: List[TableStructure] = []
        headers: List[Tuple[int, str]] = []
        
        current_section_lines = []
        current_section_type = SectionType.PARAGRAPH
        current_section_title = None
        current_section_start = 0
        
        i = 0
        while i < len(lines):
            line = lines[i]
            
            # Check for header
            header_match = self.header_pattern.match(line)
            if header_match:
                # Save previous section
                if current_section_lines:
                    self._save_section(
                        sections, current_section_type, current_section_lines,
                        current_section_title, current_section_start, i - 1
                    )
                    current_section_lines = []
                
                level = len(header_match.group(1))
                title = header_match.group(2).strip()
                headers.append((level, title))
                
                sections.append(DocumentSection(
                    type=SectionType.HEADER,
                    content=title,
                    level=level,
                    title=title,
                    start_line=i,
                    end_line=i
                ))
                
                current_section_title = title
                current_section_start = i + 1
                i += 1
                continue
            
            # Check for table
            if self.table_row_pattern.match(line):
                table, end_line = self._parse_table(lines, i)
                if table:
                    tables.append(table)
                    sections.append(DocumentSection(
                        type=SectionType.TABLE,
                        content=table.raw_text,
                        title=current_section_title,
                        start_line=i,
                        end_line=end_line,
                        table=table
                    ))
                    i = end_line + 1
                    current_section_lines = []
                    current_section_start = i
                    continue
            
            # Check for list
            if self.list_pattern.match(line) or self.numbered_list_pattern.match(line):
                if current_section_type != SectionType.LIST:
                    if current_section_lines:
                        self._save_section(
                            sections, current_section_type, current_section_lines,
                            current_section_title, current_section_start, i - 1
                        )
                    current_section_lines = []
                    current_section_type = SectionType.LIST
                    current_section_start = i
                
                current_section_lines.append(line)
                i += 1
                continue
            
            # Regular paragraph text
            if line.strip():
                if current_section_type != SectionType.PARAGRAPH:
                    if current_section_lines:
                        self._save_section(
                            sections, current_section_type, current_section_lines,
                            current_section_title, current_section_start, i - 1
                        )
                    current_section_lines = []
                    current_section_type = SectionType.PARAGRAPH
                    current_section_start = i
                
                current_section_lines.append(line)
            else:
                # Empty line - end current section
                if current_section_lines:
                    self._save_section(
                        sections, current_section_type, current_section_lines,
                        current_section_title, current_section_start, i - 1
                    )
                    current_section_lines = []
                    current_section_type = SectionType.PARAGRAPH
            
            i += 1
        
        # Save final section
        if current_section_lines:
            self._save_section(
                sections, current_section_type, current_section_lines,
                current_section_title, current_section_start, len(lines) - 1
            )
        
        return StructuredDocument(
            raw_text=text,
            sections=sections,
            tables=tables,
            headers=headers,
            metadata=self._extract_metadata(sections)
        )
    
    def _parse_table(self, lines: List[str], start_idx: int) -> Tuple[Optional[TableStructure], int]:
        """
        Parse a markdown table starting at the given line.
        
        Returns:
            Tuple of (TableStructure or None, end_line_index)
        """
        table_lines = []
        i = start_idx
        
        # Collect all consecutive table lines
        while i < len(lines) and self.table_row_pattern.match(lines[i]):
            table_lines.append(lines[i])
            i += 1
        
        if len(table_lines) < 2:  # Need at least header and separator
            return None, start_idx
        
        # Parse header
        header_line = table_lines[0]
        headers = [cell.strip() for cell in header_line.split('|')[1:-1]]
        
        # Skip separator line (if present)
        data_start = 2 if len(table_lines) > 1 and self.table_separator_pattern.match(table_lines[1]) else 1
        
        # Parse data rows
        rows = []
        for line in table_lines[data_start:]:
            cells = [cell.strip() for cell in line.split('|')[1:-1]]
            # Pad with empty strings if needed
            while len(cells) < len(headers):
                cells.append("")
            rows.append(cells[:len(headers)])  # Trim if too many columns
        
        raw_text = '\n'.join(table_lines)
        
        return TableStructure(
            headers=headers,
            rows=rows,
            raw_text=raw_text,
            start_line=start_idx,
            end_line=i - 1
        ), i - 1
    
    def _save_section(
        self,
        sections: List[DocumentSection],
        section_type: SectionType,
        lines: List[str],
        title: Optional[str],
        start_line: int,
        end_line: int
    ):
        """Save a section to the sections list"""
        if not lines:
            return
        
        content = '\n'.join(lines)
        sections.append(DocumentSection(
            type=section_type,
            content=content,
            title=title,
            start_line=start_line,
            end_line=end_line
        ))
    
    def _extract_metadata(self, sections: List[DocumentSection]) -> Dict[str, Any]:
        """Extract metadata from document structure"""
        metadata = {
            "section_count": len(sections),
            "has_tables": any(s.type == SectionType.TABLE for s in sections),
            "has_headers": any(s.type == SectionType.HEADER for s in sections),
            "has_lists": any(s.type == SectionType.LIST for s in sections),
            "table_count": sum(1 for s in sections if s.type == SectionType.TABLE),
        }
        
        # Extract document title (first H1)
        for section in sections:
            if section.type == SectionType.HEADER and section.level == 1:
                metadata["document_title"] = section.content
                break
        
        return metadata


def parse_markdown(text: str) -> StructuredDocument:
    """
    Convenience function to parse markdown text.
    
    Args:
        text: Markdown-formatted text from DeepSeek OCR
        
    Returns:
        StructuredDocument with extracted structure
    """
    parser = MarkdownParser()
    return parser.parse(text)
