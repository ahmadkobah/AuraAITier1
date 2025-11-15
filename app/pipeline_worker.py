"""
Pipeline Worker - Main background task for document processing
Orchestrates full AI pipeline: split → classify → embed → detect signatures → summarize
"""

import logging
import os
from typing import Dict, Any
from datetime import datetime
import torch

logger = logging.getLogger("pipeline_worker")


async def run_full_ai_pipeline(
    doc_id: str,
    pdf_file_path: str,
    db_connection,
    models: Dict[str, Any]
) -> None:
    """
    Full AI pipeline for document processing
    
    Workflow:
    1. Mark document as PROCESSING in MongoDB
    2. Split PDF into logical documents
    3. For each logical document:
       a. Classify document type
       b. Generate embedding for search
       c. Detect signatures/forms
       d. Generate summary using Llama (if available)
    4. Save all results to MongoDB processed_data array
    5. Mark document as COMPLETE
    
    Args:
        doc_id: Document ID in MongoDB
        pdf_file_path: Path to uploaded PDF
        db_connection: MongoDB client
        models: Loaded models dictionary
    """
    try:
        db = db_connection
        documents_collection = db['documents']
        
        logger.info(f"Starting pipeline for doc_id: {doc_id}")
        
        # Mark as processing
        documents_collection.update_one(
            {'_id': doc_id},
            {
                '$set': {
                    'status': 'PROCESSING',
                    'processing_started': datetime.utcnow(),
                    'processed_data': []
                }
            }
        )
        logger.info(f"Marked {doc_id} as PROCESSING")
        
        # Step 1: Split PDF and extract text
        logger.info("Step 1: Splitting PDF...")
        from app.document_splitter import (
            split_pdf_and_find_breaks,
            classify_text,
            find_signature
        )
        
        logical_documents = split_pdf_and_find_breaks(
            pdf_file_path,
            models,
            similarity_threshold=0.5
        )
        logger.info(f"✓ Split into {len(logical_documents)} logical documents")
        
        # Step 2: Process each logical document
        processed_data = []
        
        for idx, logical_doc in enumerate(logical_documents):
            logger.info(f"Processing logical document {idx + 1}/{len(logical_documents)}")
            
            doc_text = logical_doc['text']
            doc_embedding = logical_doc['embedding']
            
            # 2a. Classify
            logger.info("  Classifying document...")
            classification = classify_text(doc_text, models)
            
            # 2b. Embedding already computed in document_splitter
            
            # 2c. Detect signatures (use first page image for now)
            logger.info("  Detecting signatures...")
            from pdf2image import convert_from_path
            images = convert_from_path(pdf_file_path, dpi=300)
            first_page_in_doc = logical_doc['start_page']
            
            signature_info = {}
            if first_page_in_doc < len(images):
                signature_info = find_signature(images[first_page_in_doc], models)
            
            # 2d. Generate summary using Llama
            logger.info("  Generating summary...")
            summary = await generate_summary(doc_text, models)
            
            # Store processed document
            processed_doc = {
                'logical_doc_num': logical_doc['doc_num'],
                'page_range': f"{logical_doc['start_page']}-{logical_doc['end_page']}",
                'page_count': logical_doc['page_count'],
                'text': doc_text[:2000] + "..." if len(doc_text) > 2000 else doc_text,
                'embedding': doc_embedding,
                'classification': classification,
                'signature_detected': signature_info['detected'],
                'signature_confidence': signature_info['confidence'],
                'summary': summary,
                'processed_at': datetime.utcnow().isoformat()
            }
            
            processed_data.append(processed_doc)
        
        # Step 3: Save results to MongoDB
        logger.info(f"Saving {len(processed_data)} processed documents to MongoDB...")
        documents_collection.update_one(
            {'_id': doc_id},
            {
                '$set': {
                    'status': 'COMPLETE',
                    'processed_data': processed_data,
                    'processing_completed': datetime.utcnow(),
                    'document_count': len(processed_data),
                    'error': None
                }
            }
        )
        
        logger.info(f"✓ Pipeline complete for {doc_id}")
        
    except Exception as e:
        logger.error(f"Error in pipeline for {doc_id}: {e}", exc_info=True)
        
        # Mark as failed
        try:
            documents_collection = db_connection['documents']
            documents_collection.update_one(
                {'_id': doc_id},
                {
                    '$set': {
                        'status': 'FAILED',
                        'error': str(e),
                        'processing_completed': datetime.utcnow()
                    }
                }
            )
        except Exception as db_error:
            logger.error(f"Failed to mark document as failed: {db_error}")


async def generate_summary(text: str, models: Dict[str, Any]) -> str:
    """
    Generate document summary using Llama 3.2 3B
    Falls back to simple text truncation if Llama unavailable
    
    Args:
        text: Document text to summarize
        models: Loaded models dictionary
        
    Returns:
        Summary string (max 500 chars)
    """
    try:
        # Check if Llama is available
        if models.get('llama') is None:
            logger.info("Llama not available, using fallback summary")
            # Simple fallback: first N sentences
            sentences = text.split('. ')
            fallback = '. '.join(sentences[:3]) + ('.' if sentences else '')
            return fallback[:500]
        
        # Load Llama if not already loaded
        from app.model_loader import load_llama_model
        llama = models.get('llama')
        
        if llama is None:
            llama = load_llama_model()
            models['llama'] = llama
        
        if llama is None:
            # Fallback if loading failed
            sentences = text.split('. ')
            fallback = '. '.join(sentences[:3]) + ('.' if sentences else '')
            return fallback[:500]
        
        # Prepare prompt
        text_input = text[:1500]  # Limit input to avoid token overflow
        prompt = f"""Please summarize the following document in 2-3 sentences:

{text_input}

Summary:"""
        
        # Generate summary
        logger.info("Generating summary with Llama...")
        response = llama(
            prompt,
            max_tokens=150,
            temperature=0.7,
            top_p=0.9
        )
        
        summary = response['choices'][0]['text'].strip()
        logger.info(f"✓ Generated summary ({len(summary)} chars)")
        
        return summary[:500]
        
    except Exception as e:
        logger.warning(f"Error generating summary: {e}")
        # Return simple fallback
        sentences = text.split('. ')
        fallback = '. '.join(sentences[:3]) + ('.' if sentences else '')
        return fallback[:500]


def cleanup_temp_files(doc_id: str, temp_dir: str = '/tmp') -> None:
    """
    Clean up temporary files created during processing
    
    Args:
        doc_id: Document ID
        temp_dir: Temporary directory path
    """
    try:
        import shutil
        doc_temp = os.path.join(temp_dir, f'doc_{doc_id}')
        if os.path.exists(doc_temp):
            shutil.rmtree(doc_temp)
            logger.info(f"Cleaned up temporary files for {doc_id}")
    except Exception as e:
        logger.warning(f"Error cleaning up temp files: {e}")
