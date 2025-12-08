"""
Prompt Manager - Fetch and select prompts from Control Panel
Implements priority-based prompt selection with company/tier/document type matching
"""

import logging
import os
from typing import Dict, List, Optional, Any
import httpx
from datetime import datetime

logger = logging.getLogger("prompt_manager")

# Control Panel URL from environment
CONTROL_PANEL_URL = os.getenv('CONTROL_PANEL_URL', 'http://localhost:4000')


async def fetch_prompts_from_control_panel(
    ai_capability: str,
    active_only: bool = True
) -> List[Dict[str, Any]]:
    """
    Fetch prompts from Control Panel by AI capability
    
    Args:
        ai_capability: AI capability type (classification, ner_extraction, summarization, etc.)
        active_only: Only return active prompts
        
    Returns:
        List of prompt configurations
    """
    try:
        # Use public endpoint (no auth required for AI Service)
        url = f"{CONTROL_PANEL_URL}/api/public/prompts/public/fetch"
        params = {
            'aiCapability': ai_capability,
            'active': 'true' if active_only else 'false'
        }
        
        logger.debug(f"Fetching prompts from Control Panel: {url} with params: {params}")
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            prompts = data.get('prompts', [])
            
            logger.info(f"✓ Fetched {len(prompts)} prompts for capability '{ai_capability}'")
            return prompts
            
    except httpx.HTTPError as e:
        logger.error(f"Failed to fetch prompts from Control Panel: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error fetching prompts: {e}")
        return []


def select_best_prompt(
    prompts: List[Dict[str, Any]],
    document_type: Optional[str] = None,
    company_id: Optional[str] = None,
    tier: str = 'tier1'
) -> Optional[Dict[str, Any]]:
    """
    Select the best matching prompt based on priority and matching criteria
    
    Priority rules:
    1. Company-specific prompts > Global prompts
    2. Document type match > No document type specified
    3. Tier match > All tiers
    4. Higher priority number > Lower priority number
    
    Args:
        prompts: List of prompt configurations
        document_type: Document type to match (e.g., "Invoice", "Student Transcript")
        company_id: Company ID to match
        tier: Tier to match (tier1, tier2, tier3)
        
    Returns:
        Best matching prompt configuration or None
    """
    if not prompts:
        logger.warning("No prompts available for selection")
        return None
    
    # Filter matching prompts
    matching_prompts = []
    
    for prompt in prompts:
        # Check tier match
        prompt_tier = prompt.get('tier', 'tier1')
        if prompt_tier != 'all' and prompt_tier != tier:
            continue
        
        # Check company match
        prompt_company = prompt.get('companyId')
        if company_id:
            # If we have a company, prefer company-specific or global
            if prompt_company and prompt_company != company_id:
                logger.debug(f"Skipping '{prompt.get('name')}': company '{prompt_company}' != '{company_id}'")
                continue
        else:
            # If no company, only accept global prompts
            if prompt_company:
                logger.debug(f"Skipping '{prompt.get('name')}': requires company but none provided")
                continue
        
        # Check document type match
        prompt_doc_types = prompt.get('documentTypes', [])
        if prompt_doc_types:  # If prompt specifies document types
            if not document_type:  # But we don't have a document type
                logger.debug(f"Skipping '{prompt.get('name')}': requires docType but none provided")
                continue
            if document_type not in prompt_doc_types:  # Or it doesn't match
                logger.debug(f"Skipping '{prompt.get('name')}': docType '{document_type}' not in {prompt_doc_types}")
                continue
        
        # Prompt matches all criteria
        matching_prompts.append(prompt)
    
    if not matching_prompts:
        logger.warning(f"No matching prompts found for docType={document_type}, company={company_id}, tier={tier}")
        return None
    
    # Sort by priority (multiple criteria)
    def prompt_score(p):
        priority = p.get('priority', 100)
        has_company = 1 if p.get('companyId') else 0
        has_doc_type = 1 if p.get('documentTypes') else 0
        tier_specific = 0 if p.get('tier') == 'all' else 1
        
        # Return tuple: higher values = better match
        # (company_specific, doc_type_match, tier_specific, priority)
        return (has_company, has_doc_type, tier_specific, priority)
    
    matching_prompts.sort(key=prompt_score, reverse=True)
    
    best_prompt = matching_prompts[0]
    logger.info(f"✓ Selected prompt: '{best_prompt.get('name')}' (priority={best_prompt.get('priority')}, "
                f"company={'specific' if best_prompt.get('companyId') else 'global'})")
    
    return best_prompt


def replace_prompt_variables(
    prompt_content: str,
    variables: Dict[str, Any]
) -> str:
    """
    Replace variables in prompt template with actual values
    
    Args:
        prompt_content: Prompt template with {{variable}} placeholders
        variables: Dictionary of variable names to values
        
    Returns:
        Prompt with variables replaced
    """
    result = prompt_content
    
    for var_name, var_value in variables.items():
        placeholder = f"{{{{{var_name}}}}}"
        
        # Convert value to string
        if var_value is None:
            var_value_str = ""
        elif isinstance(var_value, str):
            var_value_str = var_value
        else:
            var_value_str = str(var_value)
        
        result = result.replace(placeholder, var_value_str)
    
    return result


async def get_prompt_for_task(
    ai_capability: str,
    document_type: Optional[str] = None,
    company_id: Optional[str] = None,
    tier: str = 'tier1',
    variables: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    """
    High-level function to get the best prompt for a task
    
    Args:
        ai_capability: AI capability (classification, ner_extraction, summarization, etc.)
        document_type: Document type
        company_id: Company ID
        tier: Tier (tier1, tier2, tier3)
        variables: Variables to replace in prompt template
        
    Returns:
        Dictionary with:
        - prompt: Prompt text with variables replaced
        - llm_config: LLM configuration (maxTokens, temperature, etc.)
        - metadata: Prompt metadata (name, priority, etc.)
    """
    # Fetch prompts from Control Panel
    prompts = await fetch_prompts_from_control_panel(ai_capability, active_only=True)
    
    if not prompts:
        logger.warning(f"No prompts found for capability '{ai_capability}', using fallback")
        return None
    
    # Select best matching prompt
    selected_prompt = select_best_prompt(prompts, document_type, company_id, tier)
    
    if not selected_prompt:
        logger.warning(f"No matching prompt for capability '{ai_capability}', using fallback")
        return None
    
    # Get prompt content and replace variables
    prompt_content = selected_prompt.get('content', '')
    
    if variables:
        prompt_content = replace_prompt_variables(prompt_content, variables)
    
    # Return prompt with configuration
    return {
        'prompt': prompt_content,
        'llm_config': selected_prompt.get('llmConfig', {}),
        'metadata': {
            'name': selected_prompt.get('name'),
            'priority': selected_prompt.get('priority'),
            'company_specific': bool(selected_prompt.get('companyId')),
            'tier': selected_prompt.get('tier'),
            'version': selected_prompt.get('version', '1.0')
        }
    }


# Fallback prompts if Control Panel is unavailable
FALLBACK_PROMPTS = {
    'classification': """Classify this document into one of these types:
- Invoice
- Receipt
- Contract
- Research Paper
- Student Transcript
- Certificate
- Meeting Minutes
- Email
- Other

Document text: {{document_text}}

Return only the document type.""",
    
    'ner_extraction': """Extract structured data from this document:

{{document_text}}

Return JSON with relevant fields based on document type.""",
    
    'summarization': """Summarize the following document in 3-4 sentences:

{{document_text}}

Summary:""",
    
    'qa': """Answer the following question based on the document:

Document: {{document_text}}

Question: {{question}}

Answer:""",
    
    'semantic_search': """Find relevant information in the document for this query:

Query: {{search_query}}

Document: {{document_text}}

Relevant excerpts:"""
}


def get_fallback_prompt(ai_capability: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Get fallback prompt when Control Panel is unavailable"""
    prompt_content = FALLBACK_PROMPTS.get(ai_capability, FALLBACK_PROMPTS['ner_extraction'])
    
    if variables:
        prompt_content = replace_prompt_variables(prompt_content, variables)
    
    return {
        'prompt': prompt_content,
        'llm_config': {
            'maxTokens': 300,
            'temperature': 0.3,
            'topP': 0.9,
            'topK': 40
        },
        'metadata': {
            'name': 'Fallback Prompt',
            'priority': 0,
            'company_specific': False,
            'tier': 'all',
            'version': '1.0'
        }
    }
