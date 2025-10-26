"""
Document Validator
=================

Advanced document validation service that applies business rules,
compliance checks, and quality assessments to documents.
"""

import asyncio
import logging
import re
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, date
from dateutil import parser as date_parser

logger = logging.getLogger(__name__)

class DocumentValidator:
    """
    Document validation service with configurable business rules.
    """
    
    def __init__(self):
        self.validation_rules = self._initialize_validation_rules()
        self.custom_rules = {}
        self.is_initialized = False
        
        # Validation statistics
        self.stats = {
            "total_validations": 0,
            "passed_validations": 0,
            "failed_validations": 0,
            "rule_usage": {},
            "common_issues": {},
            "last_updated": None
        }
    
    def _initialize_validation_rules(self) -> Dict[str, Dict[str, Any]]:
        """Initialize default validation rules for different document types."""
        return {
            "invoice": {
                "required_fields": [
                    {"field": "invoice_number", "pattern": r"invoice\s*#?\s*:?\s*([A-Z0-9\-]{3,20})", "required": True},
                    {"field": "amount", "pattern": r"\$\d{1,3}(?:,\d{3})*(?:\.\d{2})?", "required": True},
                    {"field": "date", "pattern": r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", "required": True},
                    {"field": "vendor", "pattern": r"(?:from|vendor|company):\s*(.+)", "required": False}
                ],
                "business_rules": [
                    {"rule": "amount_positive", "description": "Amount must be positive"},
                    {"rule": "date_not_future", "description": "Invoice date cannot be in future"},
                    {"rule": "invoice_number_unique", "description": "Invoice number should be unique"}
                ],
                "compliance_checks": [
                    {"check": "tax_calculation", "description": "Tax calculation verification"},
                    {"check": "currency_format", "description": "Currency format compliance"}
                ]
            },
            "contract": {
                "required_fields": [
                    {"field": "parties", "pattern": r"(?:party|between|contractor|client)", "required": True},
                    {"field": "effective_date", "pattern": r"effective\s+date", "required": True},
                    {"field": "terms", "pattern": r"terms\s+and\s+conditions", "required": True},
                    {"field": "signatures", "pattern": r"signature", "required": True}
                ],
                "business_rules": [
                    {"rule": "parties_identified", "description": "All parties must be clearly identified"},
                    {"rule": "terms_complete", "description": "Terms and conditions must be complete"},
                    {"rule": "signatures_present", "description": "Required signatures must be present"}
                ],
                "compliance_checks": [
                    {"check": "legal_language", "description": "Legal language compliance"},
                    {"check": "jurisdiction_clause", "description": "Jurisdiction clause present"}
                ]
            },
            "receipt": {
                "required_fields": [
                    {"field": "transaction_id", "pattern": r"(?:receipt|transaction)\s*#?\s*:?\s*([A-Z0-9\-]{3,20})", "required": True},
                    {"field": "amount", "pattern": r"\$\d{1,3}(?:,\d{3})*(?:\.\d{2})?", "required": True},
                    {"field": "date", "pattern": r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", "required": True},
                    {"field": "merchant", "pattern": r"(?:merchant|store|company)", "required": False}
                ],
                "business_rules": [
                    {"rule": "amount_positive", "description": "Amount must be positive"},
                    {"rule": "date_reasonable", "description": "Date must be reasonable"},
                    {"rule": "tax_included", "description": "Tax should be properly calculated"}
                ],
                "compliance_checks": [
                    {"check": "receipt_format", "description": "Standard receipt format"},
                    {"check": "merchant_info", "description": "Merchant information complete"}
                ]
            },
            "letter": {
                "required_fields": [
                    {"field": "date", "pattern": r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", "required": True},
                    {"field": "recipient", "pattern": r"dear\s+\w+", "required": True},
                    {"field": "sender", "pattern": r"(?:sincerely|regards|yours)", "required": True}
                ],
                "business_rules": [
                    {"rule": "proper_salutation", "description": "Must have proper salutation"},
                    {"rule": "proper_closing", "description": "Must have proper closing"},
                    {"rule": "professional_tone", "description": "Professional tone maintained"}
                ],
                "compliance_checks": [
                    {"check": "letterhead_format", "description": "Proper letterhead format"},
                    {"check": "address_format", "description": "Address format compliance"}
                ]
            },
            "form": {
                "required_fields": [
                    {"field": "form_title", "pattern": r"(?:application|form|request)", "required": True},
                    {"field": "instructions", "pattern": r"(?:complete|fill|instructions)", "required": False},
                    {"field": "required_fields", "pattern": r"required|mandatory|\*", "required": False}
                ],
                "business_rules": [
                    {"rule": "clear_instructions", "description": "Clear completion instructions"},
                    {"rule": "required_fields_marked", "description": "Required fields clearly marked"},
                    {"rule": "contact_information", "description": "Contact information provided"}
                ],
                "compliance_checks": [
                    {"check": "accessibility", "description": "Accessibility compliance"},
                    {"check": "data_privacy", "description": "Data privacy notice"}
                ]
            }
        }
    
    async def initialize(self):
        """Initialize the document validator."""
        try:
            logger.info("Initializing Document Validator...")
            # Load custom rules if any exist
            await self._load_custom_rules()
            self.is_initialized = True
            logger.info("Document Validator initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Document Validator: {str(e)}")
            raise
    
    async def _load_custom_rules(self):
        """Load custom validation rules from configuration."""
        try:
            # In production, this would load from a configuration file or database
            # For now, we'll use an empty dictionary
            self.custom_rules = {}
            logger.info("Custom validation rules loaded")
            
        except Exception as e:
            logger.warning(f"Failed to load custom rules: {str(e)}")
    
    async def validate_document(
        self,
        content: str,
        document_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        validation_rules: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Validate document against business rules and compliance checks.
        
        Args:
            content: Document text content
            document_type: Type of document for targeted validation
            metadata: Additional document metadata
            validation_rules: Specific validation rules to apply
            
        Returns:
            Validation results with issues and recommendations
        """
        start_time = datetime.utcnow()
        
        try:
            logger.info(f"Starting document validation for type: {document_type}")
            
            if not self.is_initialized:
                raise RuntimeError("Document Validator not initialized")
            
            # Initialize validation results
            validation_results = {
                "is_valid": True,
                "validation_score": 1.0,
                "issues": [],
                "recommendations": [],
                "field_validations": {},
                "rule_results": {},
                "compliance_results": {}
            }
            
            # Determine validation rules to apply
            if document_type and document_type in self.validation_rules:
                rules = self.validation_rules[document_type]
                
                # Validate required fields
                field_results = await self._validate_required_fields(content, rules.get("required_fields", []))
                validation_results["field_validations"] = field_results
                
                # Apply business rules
                business_results = await self._apply_business_rules(
                    content, rules.get("business_rules", []), metadata
                )
                validation_results["rule_results"] = business_results
                
                # Run compliance checks
                compliance_results = await self._run_compliance_checks(
                    content, rules.get("compliance_checks", []), metadata
                )
                validation_results["compliance_results"] = compliance_results
                
            else:
                # Apply generic validation
                validation_results = await self._apply_generic_validation(content, metadata)
            
            # Apply custom rules if specified
            if validation_rules:
                custom_results = await self._apply_custom_rules(content, validation_rules, metadata)
                validation_results["custom_rule_results"] = custom_results
            
            # Calculate overall validation score and status
            final_results = await self._calculate_validation_score(validation_results)
            
            # Add processing metadata
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            final_results.update({
                "processing_time": processing_time,
                "document_type": document_type,
                "validation_timestamp": datetime.utcnow().isoformat(),
                "metadata": metadata or {}
            })
            
            # Update statistics
            await self._update_validation_stats(final_results, processing_time)
            
            logger.info(f"Document validation completed in {processing_time:.2f} seconds")
            logger.info(f"Validation result: {'PASSED' if final_results['is_valid'] else 'FAILED'}")
            
            return final_results
            
        except Exception as e:
            logger.error(f"Document validation error: {str(e)}")
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            return {
                "is_valid": False,
                "validation_score": 0.0,
                "issues": [{"type": "system_error", "message": f"Validation failed: {str(e)}"}],
                "recommendations": ["Contact system administrator"],
                "processing_time": processing_time,
                "error": str(e)
            }
    
    async def _validate_required_fields(self, content: str, required_fields: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate required fields in document content."""
        try:
            field_results = {}
            
            for field_config in required_fields:
                field_name = field_config["field"]
                pattern = field_config["pattern"]
                is_required = field_config.get("required", True)
                
                # Search for field pattern
                matches = re.findall(pattern, content, re.IGNORECASE)
                
                field_result = {
                    "found": len(matches) > 0,
                    "value": matches[0] if matches else None,
                    "pattern": pattern,
                    "required": is_required,
                    "valid": True
                }
                
                # Additional validation for specific field types
                if matches:
                    field_result["valid"] = await self._validate_field_value(
                        field_name, matches[0]
                    )
                elif is_required:
                    field_result["valid"] = False
                
                field_results[field_name] = field_result
            
            return field_results
            
        except Exception as e:
            logger.error(f"Field validation error: {str(e)}")
            return {}
    
    async def _validate_field_value(self, field_name: str, value: str) -> bool:
        """Validate specific field values based on field type."""
        try:
            if field_name in ["date", "effective_date"]:
                # Date validation
                try:
                    parsed_date = date_parser.parse(value)
                    # Check if date is reasonable (not too far in past/future)
                    current_date = datetime.now().date()
                    date_diff = abs((parsed_date.date() - current_date).days)
                    return date_diff <= 36500  # Within 100 years
                except Exception:
                    return False
                    
            elif field_name in ["amount", "total"]:
                # Amount validation
                try:
                    # Remove currency symbols and parse
                    cleaned_amount = re.sub(r'[^\d\.\,]', '', value)
                    amount = float(cleaned_amount.replace(',', ''))
                    return amount > 0
                except Exception:
                    return False
                    
            elif field_name in ["invoice_number", "transaction_id"]:
                # ID format validation
                return len(value) >= 3 and bool(re.match(r'^[A-Z0-9\-]+$', value, re.IGNORECASE))
                
            else:
                # Generic validation - not empty
                return bool(value.strip())
                
        except Exception:
            return False
    
    async def _apply_business_rules(
        self,
        content: str,
        business_rules: List[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Apply business rules to document content."""
        try:
            rule_results = {}
            
            for rule_config in business_rules:
                rule_name = rule_config["rule"]
                rule_description = rule_config["description"]
                
                # Apply specific business rule
                rule_result = await self._evaluate_business_rule(rule_name, content, metadata)
                
                rule_results[rule_name] = {
                    "passed": rule_result["passed"],
                    "description": rule_description,
                    "message": rule_result.get("message", ""),
                    "severity": rule_result.get("severity", "warning")
                }
            
            return rule_results
            
        except Exception as e:
            logger.error(f"Business rules application error: {str(e)}")
            return {}
    
    async def _evaluate_business_rule(
        self,
        rule_name: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Evaluate a specific business rule."""
        try:
            if rule_name == "amount_positive":
                # Check if amounts are positive
                amounts = re.findall(r'\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)', content)
                for amount_str in amounts:
                    amount = float(amount_str.replace(',', ''))
                    if amount <= 0:
                        return {
                            "passed": False,
                            "message": f"Found non-positive amount: ${amount_str}",
                            "severity": "error"
                        }
                return {"passed": True, "message": "All amounts are positive"}
                
            elif rule_name == "date_not_future":
                # Check if dates are not in the future
                dates = re.findall(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', content)
                current_date = datetime.now().date()
                
                for date_str in dates:
                    try:
                        parsed_date = date_parser.parse(date_str).date()
                        if parsed_date > current_date:
                            return {
                                "passed": False,
                                "message": f"Future date found: {date_str}",
                                "severity": "warning"
                            }
                    except Exception:
                        continue
                
                return {"passed": True, "message": "No future dates found"}
                
            elif rule_name == "proper_salutation":
                # Check for proper letter salutation
                salutations = ["dear", "to whom it may concern", "hello"]
                content_lower = content.lower()
                
                for salutation in salutations:
                    if salutation in content_lower:
                        return {"passed": True, "message": f"Found salutation: {salutation}"}
                
                return {
                    "passed": False,
                    "message": "No proper salutation found",
                    "severity": "warning"
                }
                
            elif rule_name == "proper_closing":
                # Check for proper letter closing
                closings = ["sincerely", "regards", "yours truly", "best regards"]
                content_lower = content.lower()
                
                for closing in closings:
                    if closing in content_lower:
                        return {"passed": True, "message": f"Found closing: {closing}"}
                
                return {
                    "passed": False,
                    "message": "No proper closing found",
                    "severity": "warning"
                }
                
            else:
                # Generic rule - always pass with warning
                return {
                    "passed": True,
                    "message": f"Rule '{rule_name}' not implemented",
                    "severity": "info"
                }
                
        except Exception as e:
            return {
                "passed": False,
                "message": f"Error evaluating rule: {str(e)}",
                "severity": "error"
            }
    
    async def _run_compliance_checks(
        self,
        content: str,
        compliance_checks: List[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Run compliance checks on document content."""
        try:
            compliance_results = {}
            
            for check_config in compliance_checks:
                check_name = check_config["check"]
                check_description = check_config["description"]
                
                # Run specific compliance check
                check_result = await self._evaluate_compliance_check(check_name, content, metadata)
                
                compliance_results[check_name] = {
                    "compliant": check_result["compliant"],
                    "description": check_description,
                    "message": check_result.get("message", ""),
                    "severity": check_result.get("severity", "info")
                }
            
            return compliance_results
            
        except Exception as e:
            logger.error(f"Compliance checks error: {str(e)}")
            return {}
    
    async def _evaluate_compliance_check(
        self,
        check_name: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Evaluate a specific compliance check."""
        try:
            if check_name == "tax_calculation":
                # Basic tax calculation check
                # Look for subtotal, tax, and total
                subtotal_match = re.search(r'subtotal\s*:\s*\$?(\d+(?:,\d{3})*(?:\.\d{2})?)', content, re.IGNORECASE)
                tax_match = re.search(r'tax\s*:\s*\$?(\d+(?:,\d{3})*(?:\.\d{2})?)', content, re.IGNORECASE)
                total_match = re.search(r'total\s*:\s*\$?(\d+(?:,\d{3})*(?:\.\d{2})?)', content, re.IGNORECASE)
                
                if subtotal_match and tax_match and total_match:
                    subtotal = float(subtotal_match.group(1).replace(',', ''))
                    tax = float(tax_match.group(1).replace(',', ''))
                    total = float(total_match.group(1).replace(',', ''))
                    
                    calculated_total = subtotal + tax
                    if abs(calculated_total - total) < 0.01:  # Allow for rounding
                        return {"compliant": True, "message": "Tax calculation is correct"}
                    else:
                        return {
                            "compliant": False,
                            "message": f"Tax calculation error: {subtotal} + {tax} != {total}",
                            "severity": "warning"
                        }
                
                return {"compliant": True, "message": "Tax calculation could not be verified"}
                
            elif check_name == "currency_format":
                # Check currency format consistency
                currency_patterns = [
                    r'\$\d{1,3}(?:,\d{3})*(?:\.\d{2})?',  # $1,234.56
                    r'\d{1,3}(?:,\d{3})*(?:\.\d{2})?\s*USD',  # 1,234.56 USD
                ]
                
                found_formats = []
                for pattern in currency_patterns:
                    if re.search(pattern, content):
                        found_formats.append(pattern)
                
                if len(found_formats) <= 1:
                    return {"compliant": True, "message": "Consistent currency format"}
                else:
                    return {
                        "compliant": False,
                        "message": "Inconsistent currency formats found",
                        "severity": "warning"
                    }
                    
            else:
                # Generic compliance check - always compliant with info
                return {
                    "compliant": True,
                    "message": f"Compliance check '{check_name}' not implemented",
                    "severity": "info"
                }
                
        except Exception as e:
            return {
                "compliant": False,
                "message": f"Error in compliance check: {str(e)}",
                "severity": "error"
            }
    
    async def _apply_generic_validation(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Apply generic validation when document type is unknown."""
        try:
            issues = []
            recommendations = []
            
            # Basic content checks
            if len(content.strip()) < 50:
                issues.append({
                    "type": "content_length",
                    "message": "Document content is very short",
                    "severity": "warning"
                })
                recommendations.append("Verify that the document was properly processed")
            
            # Check for common formatting issues
            if content.count('\n\n') / max(content.count('\n'), 1) < 0.1:
                issues.append({
                    "type": "formatting",
                    "message": "Document may lack proper paragraph breaks",
                    "severity": "info"
                })
                recommendations.append("Consider reviewing document formatting")
            
            # Check for potential OCR errors
            ocr_error_patterns = [
                r'[Il1]{3,}',  # Multiple consecutive I, l, 1
                r'[O0]{3,}',   # Multiple consecutive O, 0
                r'\w{20,}',    # Very long words (potential OCR errors)
            ]
            
            for pattern in ocr_error_patterns:
                if re.search(pattern, content):
                    issues.append({
                        "type": "potential_ocr_error",
                        "message": "Potential OCR errors detected",
                        "severity": "info"
                    })
                    recommendations.append("Consider re-processing the document with OCR")
                    break
            
            return {
                "is_valid": len([i for i in issues if i["severity"] == "error"]) == 0,
                "validation_score": max(0.5, 1.0 - (len(issues) * 0.1)),
                "issues": issues,
                "recommendations": recommendations,
                "field_validations": {},
                "rule_results": {},
                "compliance_results": {}
            }
            
        except Exception as e:
            logger.error(f"Generic validation error: {str(e)}")
            return {
                "is_valid": False,
                "validation_score": 0.0,
                "issues": [{"type": "system_error", "message": str(e), "severity": "error"}],
                "recommendations": ["Contact system administrator"],
                "field_validations": {},
                "rule_results": {},
                "compliance_results": {}
            }
    
    async def _apply_custom_rules(
        self,
        content: str,
        rule_names: List[str],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Apply custom validation rules."""
        try:
            custom_results = {}
            
            for rule_name in rule_names:
                if rule_name in self.custom_rules:
                    rule_config = self.custom_rules[rule_name]
                    # Apply custom rule logic here
                    # For now, return a placeholder result
                    custom_results[rule_name] = {
                        "passed": True,
                        "message": f"Custom rule '{rule_name}' executed",
                        "severity": "info"
                    }
            
            return custom_results
            
        except Exception as e:
            logger.error(f"Custom rules application error: {str(e)}")
            return {}
    
    async def _calculate_validation_score(self, validation_results: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate overall validation score and determine validity."""
        try:
            total_score = 1.0
            all_issues = validation_results.get("issues", [])
            
            # Collect issues from all validation categories
            field_validations = validation_results.get("field_validations", {})
            for field_name, field_result in field_validations.items():
                if not field_result.get("valid", True):
                    severity = "error" if field_result.get("required", False) else "warning"
                    all_issues.append({
                        "type": "field_validation",
                        "field": field_name,
                        "message": f"Field '{field_name}' validation failed",
                        "severity": severity
                    })
            
            # Collect issues from business rules
            rule_results = validation_results.get("rule_results", {})
            for rule_name, rule_result in rule_results.items():
                if not rule_result.get("passed", True):
                    all_issues.append({
                        "type": "business_rule",
                        "rule": rule_name,
                        "message": rule_result.get("message", f"Business rule '{rule_name}' failed"),
                        "severity": rule_result.get("severity", "warning")
                    })
            
            # Collect issues from compliance checks
            compliance_results = validation_results.get("compliance_results", {})
            for check_name, check_result in compliance_results.items():
                if not check_result.get("compliant", True):
                    all_issues.append({
                        "type": "compliance_check",
                        "check": check_name,
                        "message": check_result.get("message", f"Compliance check '{check_name}' failed"),
                        "severity": check_result.get("severity", "warning")
                    })
            
            # Calculate score based on issues
            error_count = len([i for i in all_issues if i.get("severity") == "error"])
            warning_count = len([i for i in all_issues if i.get("severity") == "warning"])
            
            # Deduct score for issues
            total_score -= (error_count * 0.2)  # Errors reduce score by 20% each
            total_score -= (warning_count * 0.1)  # Warnings reduce score by 10% each
            total_score = max(0.0, total_score)
            
            # Generate recommendations
            recommendations = validation_results.get("recommendations", [])
            if error_count > 0:
                recommendations.append("Address critical validation errors before proceeding")
            if warning_count > 0:
                recommendations.append("Review and resolve validation warnings")
            if total_score < 0.7:
                recommendations.append("Document may require significant revision")
            
            # Determine overall validity
            is_valid = error_count == 0 and total_score >= 0.5
            
            return {
                "is_valid": is_valid,
                "validation_score": round(total_score, 3),
                "issues": all_issues,
                "recommendations": recommendations,
                "field_validations": field_validations,
                "rule_results": rule_results,
                "compliance_results": compliance_results,
                "summary": {
                    "total_issues": len(all_issues),
                    "errors": error_count,
                    "warnings": warning_count,
                    "score": round(total_score, 3)
                }
            }
            
        except Exception as e:
            logger.error(f"Validation score calculation error: {str(e)}")
            return validation_results
    
    async def _update_validation_stats(self, validation_results: Dict[str, Any], processing_time: float):
        """Update validation statistics."""
        try:
            self.stats["total_validations"] += 1
            
            if validation_results.get("is_valid", False):
                self.stats["passed_validations"] += 1
            else:
                self.stats["failed_validations"] += 1
            
            # Update rule usage statistics
            for rule_name in validation_results.get("rule_results", {}):
                if rule_name not in self.stats["rule_usage"]:
                    self.stats["rule_usage"][rule_name] = 0
                self.stats["rule_usage"][rule_name] += 1
            
            # Track common issues
            for issue in validation_results.get("issues", []):
                issue_type = issue.get("type", "unknown")
                if issue_type not in self.stats["common_issues"]:
                    self.stats["common_issues"][issue_type] = 0
                self.stats["common_issues"][issue_type] += 1
            
            self.stats["last_updated"] = datetime.utcnow().isoformat()
            
        except Exception as e:
            logger.warning(f"Failed to update validation stats: {str(e)}")
    
    async def get_validation_stats(self) -> Dict[str, Any]:
        """Get validation statistics."""
        try:
            if not self.is_initialized:
                return {"status": "not_initialized"}
            
            success_rate = (
                self.stats["passed_validations"] / max(self.stats["total_validations"], 1)
            ) * 100
            
            return {
                "total_validations": self.stats["total_validations"],
                "passed_validations": self.stats["passed_validations"],
                "failed_validations": self.stats["failed_validations"],
                "success_rate": round(success_rate, 2),
                "rule_usage": self.stats["rule_usage"],
                "common_issues": self.stats["common_issues"],
                "supported_document_types": list(self.validation_rules.keys()),
                "last_updated": self.stats["last_updated"]
            }
            
        except Exception as e:
            logger.error(f"Failed to get validation stats: {str(e)}")
            return {"error": str(e)}
    
    async def add_custom_rule(self, rule_name: str, rule_config: Dict[str, Any]) -> Dict[str, Any]:
        """Add a custom validation rule."""
        try:
            if not self.is_initialized:
                raise RuntimeError("Document Validator not initialized")
            
            # Validate rule configuration
            required_fields = ["description", "rule_type"]
            for field in required_fields:
                if field not in rule_config:
                    raise ValueError(f"Missing required field: {field}")
            
            # Add rule to custom rules
            self.custom_rules[rule_name] = rule_config
            
            logger.info(f"Added custom validation rule: {rule_name}")
            
            return {
                "status": "success",
                "rule_name": rule_name,
                "message": "Custom rule added successfully"
            }
            
        except Exception as e:
            logger.error(f"Failed to add custom rule {rule_name}: {str(e)}")
            return {
                "status": "error",
                "error": str(e)
            }