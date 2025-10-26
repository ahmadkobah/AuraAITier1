"""
Document Router
==============

Intelligent document routing service that determines appropriate
actions, destinations, and workflows based on document analysis.
"""

import asyncio
import logging
import re
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)

class DocumentRouter:
    """
    Intelligent document routing and workflow management service.
    """
    
    def __init__(self):
        self.routing_rules = self._initialize_routing_rules()
        self.workflow_templates = self._initialize_workflow_templates()
        self.destinations = self._initialize_destinations()
        self.is_initialized = False
        
        # Routing statistics
        self.stats = {
            "total_routings": 0,
            "successful_routings": 0,
            "destination_usage": {},
            "workflow_usage": {},
            "priority_distribution": {},
            "last_updated": None
        }
    
    def _initialize_routing_rules(self) -> Dict[str, Dict[str, Any]]:
        """Initialize routing rules for different document types."""
        return {
            "invoice": {
                "priority_rules": [
                    {"condition": "amount > 10000", "priority": "high", "reason": "High-value invoice"},
                    {"condition": "overdue", "priority": "urgent", "reason": "Overdue payment"},
                    {"condition": "new_vendor", "priority": "medium", "reason": "New vendor verification"}
                ],
                "destination_rules": [
                    {"condition": "amount > 5000", "destinations": ["finance_manager", "approval_queue"]},
                    {"condition": "amount <= 5000", "destinations": ["accounts_payable"]},
                    {"condition": "tax_discrepancy", "destinations": ["tax_review_queue"]}
                ],
                "workflow_rules": [
                    {"condition": "requires_approval", "workflow": "invoice_approval_workflow"},
                    {"condition": "auto_approvable", "workflow": "auto_payment_workflow"},
                    {"condition": "disputed", "workflow": "dispute_resolution_workflow"}
                ]
            },
            "contract": {
                "priority_rules": [
                    {"condition": "contract_value > 100000", "priority": "high", "reason": "High-value contract"},
                    {"condition": "expiring_soon", "priority": "urgent", "reason": "Contract expiring"},
                    {"condition": "missing_signatures", "priority": "medium", "reason": "Incomplete signatures"}
                ],
                "destination_rules": [
                    {"condition": "legal_review_required", "destinations": ["legal_department"]},
                    {"condition": "standard_contract", "destinations": ["contract_management"]},
                    {"condition": "executive_approval", "destinations": ["executive_review"]}
                ],
                "workflow_rules": [
                    {"condition": "new_contract", "workflow": "contract_review_workflow"},
                    {"condition": "renewal", "workflow": "contract_renewal_workflow"},
                    {"condition": "amendment", "workflow": "contract_amendment_workflow"}
                ]
            },
            "receipt": {
                "priority_rules": [
                    {"condition": "expense_claim", "priority": "medium", "reason": "Employee expense claim"},
                    {"condition": "business_critical", "priority": "high", "reason": "Business critical expense"},
                    {"condition": "routine_purchase", "priority": "low", "reason": "Routine purchase"}
                ],
                "destination_rules": [
                    {"condition": "expense_claim", "destinations": ["expense_management"]},
                    {"condition": "reimbursement", "destinations": ["hr_department"]},
                    {"condition": "tax_deductible", "destinations": ["tax_filing_queue"]}
                ],
                "workflow_rules": [
                    {"condition": "employee_expense", "workflow": "expense_reimbursement_workflow"},
                    {"condition": "company_purchase", "workflow": "purchase_verification_workflow"}
                ]
            },
            "letter": {
                "priority_rules": [
                    {"condition": "legal_notice", "priority": "urgent", "reason": "Legal correspondence"},
                    {"condition": "customer_complaint", "priority": "high", "reason": "Customer service issue"},
                    {"condition": "general_inquiry", "priority": "medium", "reason": "General correspondence"}
                ],
                "destination_rules": [
                    {"condition": "legal_matter", "destinations": ["legal_department"]},
                    {"condition": "customer_service", "destinations": ["customer_support"]},
                    {"condition": "business_inquiry", "destinations": ["business_development"]}
                ],
                "workflow_rules": [
                    {"condition": "requires_response", "workflow": "correspondence_response_workflow"},
                    {"condition": "information_only", "workflow": "filing_workflow"}
                ]
            },
            "form": {
                "priority_rules": [
                    {"condition": "urgent_application", "priority": "urgent", "reason": "Time-sensitive application"},
                    {"condition": "standard_application", "priority": "medium", "reason": "Standard processing"},
                    {"condition": "information_request", "priority": "low", "reason": "Information request"}
                ],
                "destination_rules": [
                    {"condition": "hr_form", "destinations": ["hr_department"]},
                    {"condition": "finance_form", "destinations": ["finance_department"]},
                    {"condition": "customer_form", "destinations": ["customer_service"]}
                ],
                "workflow_rules": [
                    {"condition": "application_form", "workflow": "application_processing_workflow"},
                    {"condition": "survey_form", "workflow": "data_collection_workflow"}
                ]
            }
        }
    
    def _initialize_workflow_templates(self) -> Dict[str, Dict[str, Any]]:
        """Initialize workflow templates."""
        return {
            "invoice_approval_workflow": {
                "name": "Invoice Approval Workflow",
                "description": "Standard invoice approval process",
                "steps": [
                    {"step": "data_extraction", "duration": 5, "automated": True},
                    {"step": "vendor_verification", "duration": 30, "automated": True},
                    {"step": "amount_validation", "duration": 10, "automated": True},
                    {"step": "manager_approval", "duration": 1440, "automated": False},  # 1 day
                    {"step": "payment_processing", "duration": 60, "automated": True}
                ],
                "sla": 2880,  # 2 days in minutes
                "escalation_rules": [
                    {"condition": "overdue_1_day", "action": "notify_manager"},
                    {"condition": "overdue_2_days", "action": "escalate_to_director"}
                ]
            },
            "contract_review_workflow": {
                "name": "Contract Review Workflow",
                "description": "Legal and business contract review process",
                "steps": [
                    {"step": "initial_review", "duration": 240, "automated": False},  # 4 hours
                    {"step": "legal_review", "duration": 1440, "automated": False},  # 1 day
                    {"step": "business_approval", "duration": 720, "automated": False},  # 12 hours
                    {"step": "signature_collection", "duration": 2880, "automated": False},  # 2 days
                    {"step": "filing", "duration": 30, "automated": True}
                ],
                "sla": 7200,  # 5 days in minutes
                "escalation_rules": [
                    {"condition": "overdue_3_days", "action": "notify_legal"},
                    {"condition": "overdue_5_days", "action": "escalate_to_ceo"}
                ]
            },
            "expense_reimbursement_workflow": {
                "name": "Expense Reimbursement Workflow",
                "description": "Employee expense claim processing",
                "steps": [
                    {"step": "receipt_validation", "duration": 15, "automated": True},
                    {"step": "policy_check", "duration": 30, "automated": True},
                    {"step": "manager_approval", "duration": 480, "automated": False},  # 8 hours
                    {"step": "finance_processing", "duration": 240, "automated": False},  # 4 hours
                    {"step": "payment", "duration": 60, "automated": True}
                ],
                "sla": 1440,  # 1 day in minutes
                "escalation_rules": [
                    {"condition": "overdue_8_hours", "action": "notify_hr"},
                    {"condition": "overdue_1_day", "action": "auto_approve_small_amounts"}
                ]
            },
            "correspondence_response_workflow": {
                "name": "Correspondence Response Workflow",
                "description": "Process for responding to correspondence",
                "steps": [
                    {"step": "classification", "duration": 10, "automated": True},
                    {"step": "priority_assessment", "duration": 15, "automated": True},
                    {"step": "draft_response", "duration": 240, "automated": False},  # 4 hours
                    {"step": "review_approval", "duration": 120, "automated": False},  # 2 hours
                    {"step": "send_response", "duration": 5, "automated": True}
                ],
                "sla": 480,  # 8 hours in minutes
                "escalation_rules": [
                    {"condition": "overdue_4_hours", "action": "notify_supervisor"},
                    {"condition": "overdue_8_hours", "action": "escalate_to_manager"}
                ]
            }
        }
    
    def _initialize_destinations(self) -> Dict[str, Dict[str, Any]]:
        """Initialize available routing destinations."""
        return {
            "finance_manager": {
                "name": "Finance Manager",
                "type": "person",
                "department": "finance",
                "capacity": 50,  # max documents per day
                "sla": 480,  # 8 hours response time
                "contact": "finance.manager@company.com"
            },
            "accounts_payable": {
                "name": "Accounts Payable Queue",
                "type": "queue",
                "department": "finance",
                "capacity": 200,
                "sla": 1440,  # 1 day
                "automated": True
            },
            "legal_department": {
                "name": "Legal Department",
                "type": "department",
                "department": "legal",
                "capacity": 30,
                "sla": 2880,  # 2 days
                "contact": "legal@company.com"
            },
            "hr_department": {
                "name": "HR Department",
                "type": "department",
                "department": "hr",
                "capacity": 100,
                "sla": 1440,  # 1 day
                "contact": "hr@company.com"
            },
            "customer_support": {
                "name": "Customer Support",
                "type": "department",
                "department": "customer_service",
                "capacity": 150,
                "sla": 240,  # 4 hours
                "contact": "support@company.com"
            },
            "approval_queue": {
                "name": "Approval Queue",
                "type": "queue",
                "department": "management",
                "capacity": 100,
                "sla": 720,  # 12 hours
                "automated": False
            },
            "tax_review_queue": {
                "name": "Tax Review Queue",
                "type": "queue",
                "department": "finance",
                "capacity": 50,
                "sla": 2880,  # 2 days
                "automated": False
            }
        }
    
    async def initialize(self):
        """Initialize the document router."""
        try:
            logger.info("Initializing Document Router...")
            # Load custom routing configurations if any exist
            await self._load_custom_configurations()
            self.is_initialized = True
            logger.info("Document Router initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Document Router: {str(e)}")
            raise
    
    async def _load_custom_configurations(self):
        """Load custom routing configurations."""
        try:
            # In production, this would load from configuration files or database
            logger.info("Custom routing configurations loaded")
            
        except Exception as e:
            logger.warning(f"Failed to load custom configurations: {str(e)}")
    
    async def route_document(
        self,
        content: str,
        classification_result: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        routing_criteria: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Determine document routing and workflow actions.
        
        Args:
            content: Document text content
            classification_result: Pre-computed classification result
            metadata: Additional document metadata
            routing_criteria: Custom routing criteria
            
        Returns:
            Routing result with recommended actions and destinations
        """
        start_time = datetime.utcnow()
        
        try:
            logger.info("Starting document routing analysis...")
            
            if not self.is_initialized:
                raise RuntimeError("Document Router not initialized")
            
            # Extract document type from classification result
            document_type = None
            if classification_result:
                document_type = classification_result.get("document_type", "unknown")
            
            # Analyze document context
            document_context = await self._analyze_document_context(
                content, classification_result, metadata
            )
            
            # Determine priority level
            priority_result = await self._determine_priority(
                document_type, document_context, routing_criteria
            )
            
            # Find appropriate destinations
            destination_result = await self._determine_destinations(
                document_type, document_context, priority_result, routing_criteria
            )
            
            # Suggest workflows
            workflow_result = await self._suggest_workflows(
                document_type, document_context, priority_result, routing_criteria
            )
            
            # Generate recommended actions
            recommended_actions = await self._generate_recommended_actions(
                document_context, priority_result, destination_result, workflow_result
            )
            
            # Calculate processing time
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            
            # Create routing result
            routing_result = {
                "recommended_actions": recommended_actions,
                "priority_level": priority_result["priority"],
                "priority_reason": priority_result["reason"],
                "routing_destinations": destination_result["destinations"],
                "destination_details": destination_result["details"],
                "workflow_suggestions": workflow_result["workflows"],
                "estimated_completion": workflow_result["estimated_completion"],
                "processing_time": processing_time,
                "document_context": document_context,
                "routing_metadata": {
                    "document_type": document_type,
                    "routing_timestamp": datetime.utcnow().isoformat(),
                    "criteria_used": routing_criteria or {}
                }
            }
            
            # Update statistics
            await self._update_routing_stats(routing_result, processing_time)
            
            logger.info(f"Document routing completed in {processing_time:.2f} seconds")
            logger.info(f"Priority: {priority_result['priority']}, Destinations: {len(destination_result['destinations'])}")
            
            return routing_result
            
        except Exception as e:
            logger.error(f"Document routing error: {str(e)}")
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            return {
                "recommended_actions": [{"action": "manual_review", "reason": "Routing failed"}],
                "priority_level": "medium",
                "priority_reason": "Default priority due to routing error",
                "routing_destinations": ["manual_review_queue"],
                "workflow_suggestions": [],
                "processing_time": processing_time,
                "error": str(e)
            }
    
    async def _analyze_document_context(
        self,
        content: str,
        classification_result: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Analyze document context for routing decisions."""
        try:
            context = {
                "content_length": len(content),
                "word_count": len(content.split()),
                "has_dates": bool(re.search(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', content)),
                "has_amounts": bool(re.search(r'\$\d+', content)),
                "has_signatures": bool(re.search(r'signature|signed', content, re.IGNORECASE)),
                "urgency_indicators": [],
                "complexity_score": 0.5,
                "confidence_score": classification_result.get("confidence", 0.5) if classification_result else 0.5
            }
            
            # Check for urgency indicators
            urgency_patterns = [
                (r'urgent|asap|immediate', "urgent_language"),
                (r'deadline|due\s+date', "deadline_mentioned"),
                (r'overdue|past\s+due', "overdue_status"),
                (r'legal\s+notice|legal\s+action', "legal_urgency"),
                (r'final\s+notice|last\s+warning', "final_notice")
            ]
            
            for pattern, indicator in urgency_patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    context["urgency_indicators"].append(indicator)
            
            # Calculate complexity score
            complexity_factors = [
                (len(content) > 5000, 0.2),  # Long document
                (content.count('\n\n') > 10, 0.1),  # Many paragraphs
                (len(re.findall(r'\$\d+', content)) > 3, 0.1),  # Multiple amounts
                (bool(re.search(r'contract|agreement', content, re.IGNORECASE)), 0.2),  # Legal document
                (bool(re.search(r'whereas|therefore|heretofore', content, re.IGNORECASE)), 0.2)  # Legal language
            ]
            
            complexity_score = 0.5  # Base complexity
            for condition, score_delta in complexity_factors:
                if condition:
                    complexity_score += score_delta
            
            context["complexity_score"] = min(complexity_score, 1.0)
            
            # Add metadata context
            if metadata:
                context["source"] = metadata.get("source", "unknown")
                context["file_type"] = metadata.get("file_type", "unknown")
                context["received_date"] = metadata.get("received_date")
            
            return context
            
        except Exception as e:
            logger.error(f"Document context analysis error: {str(e)}")
            return {
                "content_length": len(content),
                "urgency_indicators": [],
                "complexity_score": 0.5,
                "confidence_score": 0.5
            }
    
    async def _determine_priority(
        self,
        document_type: Optional[str],
        document_context: Dict[str, Any],
        routing_criteria: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Determine document priority level."""
        try:
            priority = "medium"  # Default priority
            reason = "Standard processing priority"
            score = 0.5
            
            # Check for urgent indicators
            urgency_count = len(document_context.get("urgency_indicators", []))
            if urgency_count >= 2:
                priority = "urgent"
                reason = "Multiple urgency indicators detected"
                score = 0.9
            elif urgency_count == 1:
                priority = "high"
                reason = "Urgency indicator detected"
                score = 0.7
            
            # Apply document type specific rules
            if document_type and document_type in self.routing_rules:
                type_rules = self.routing_rules[document_type]["priority_rules"]
                for rule in type_rules:
                    condition_met = await self._evaluate_condition(
                        rule["condition"], document_context, routing_criteria
                    )
                    if condition_met:
                        priority = rule["priority"]
                        reason = rule["reason"]
                        # Set score based on priority
                        priority_scores = {"low": 0.3, "medium": 0.5, "high": 0.7, "urgent": 0.9}
                        score = priority_scores.get(priority, 0.5)
                        break
            
            # Apply custom criteria overrides
            if routing_criteria and "priority_override" in routing_criteria:
                priority = routing_criteria["priority_override"]
                reason = routing_criteria.get("priority_reason", "Manual priority override")
                score = 0.8
            
            return {
                "priority": priority,
                "reason": reason,
                "score": score,
                "urgency_indicators": document_context.get("urgency_indicators", [])
            }
            
        except Exception as e:
            logger.error(f"Priority determination error: {str(e)}")
            return {
                "priority": "medium",
                "reason": "Default priority due to error",
                "score": 0.5,
                "urgency_indicators": []
            }
    
    async def _determine_destinations(
        self,
        document_type: Optional[str],
        document_context: Dict[str, Any],
        priority_result: Dict[str, Any],
        routing_criteria: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Determine appropriate routing destinations."""
        try:
            destinations = []
            destination_details = []
            
            # Apply document type specific destination rules
            if document_type and document_type in self.routing_rules:
                type_rules = self.routing_rules[document_type]["destination_rules"]
                for rule in type_rules:
                    condition_met = await self._evaluate_condition(
                        rule["condition"], document_context, routing_criteria
                    )
                    if condition_met:
                        rule_destinations = rule["destinations"]
                        destinations.extend(rule_destinations)
                        
                        # Add destination details
                        for dest in rule_destinations:
                            if dest in self.destinations:
                                dest_info = self.destinations[dest].copy()
                                dest_info["routing_reason"] = f"Rule: {rule['condition']}"
                                destination_details.append(dest_info)
            
            # If no specific destinations found, use default routing
            if not destinations:
                if priority_result["priority"] in ["urgent", "high"]:
                    destinations = ["approval_queue"]
                else:
                    destinations = ["general_processing_queue"]
                
                for dest in destinations:
                    destination_details.append({
                        "name": dest,
                        "routing_reason": "Default routing",
                        "type": "queue"
                    })
            
            # Apply custom destination overrides
            if routing_criteria and "destination_override" in routing_criteria:
                override_dest = routing_criteria["destination_override"]
                destinations = [override_dest]
                destination_details = [{
                    "name": override_dest,
                    "routing_reason": "Manual destination override",
                    "type": "override"
                }]
            
            # Remove duplicates while preserving order
            unique_destinations = []
            unique_details = []
            seen = set()
            
            for i, dest in enumerate(destinations):
                if dest not in seen:
                    unique_destinations.append(dest)
                    if i < len(destination_details):
                        unique_details.append(destination_details[i])
                    seen.add(dest)
            
            return {
                "destinations": unique_destinations,
                "details": unique_details,
                "routing_strategy": "rule_based"
            }
            
        except Exception as e:
            logger.error(f"Destination determination error: {str(e)}")
            return {
                "destinations": ["manual_review_queue"],
                "details": [{"name": "manual_review_queue", "routing_reason": "Error fallback"}],
                "routing_strategy": "error_fallback"
            }
    
    async def _suggest_workflows(
        self,
        document_type: Optional[str],
        document_context: Dict[str, Any],
        priority_result: Dict[str, Any],
        routing_criteria: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Suggest appropriate workflows for the document."""
        try:
            suggested_workflows = []
            estimated_completion = None
            
            # Apply document type specific workflow rules
            if document_type and document_type in self.routing_rules:
                type_rules = self.routing_rules[document_type]["workflow_rules"]
                for rule in type_rules:
                    condition_met = await self._evaluate_condition(
                        rule["condition"], document_context, routing_criteria
                    )
                    if condition_met:
                        workflow_id = rule["workflow"]
                        if workflow_id in self.workflow_templates:
                            workflow = self.workflow_templates[workflow_id].copy()
                            workflow["workflow_id"] = workflow_id
                            workflow["routing_reason"] = f"Rule: {rule['condition']}"
                            suggested_workflows.append(workflow)
            
            # Calculate estimated completion time
            if suggested_workflows:
                # Use the first (most appropriate) workflow for timing estimation
                primary_workflow = suggested_workflows[0]
                base_sla = primary_workflow.get("sla", 1440)  # Default 1 day
                
                # Adjust based on priority
                priority_multipliers = {
                    "urgent": 0.5,
                    "high": 0.7,
                    "medium": 1.0,
                    "low": 1.3
                }
                
                priority = priority_result.get("priority", "medium")
                adjusted_sla = int(base_sla * priority_multipliers.get(priority, 1.0))
                
                estimated_completion = (
                    datetime.utcnow() + timedelta(minutes=adjusted_sla)
                ).isoformat()
            
            # Apply custom workflow overrides
            if routing_criteria and "workflow_override" in routing_criteria:
                override_workflow = routing_criteria["workflow_override"]
                if override_workflow in self.workflow_templates:
                    workflow = self.workflow_templates[override_workflow].copy()
                    workflow["workflow_id"] = override_workflow
                    workflow["routing_reason"] = "Manual workflow override"
                    suggested_workflows = [workflow]
            
            return {
                "workflows": suggested_workflows,
                "estimated_completion": estimated_completion,
                "primary_workflow": suggested_workflows[0]["workflow_id"] if suggested_workflows else None
            }
            
        except Exception as e:
            logger.error(f"Workflow suggestion error: {str(e)}")
            return {
                "workflows": [],
                "estimated_completion": None,
                "primary_workflow": None
            }
    
    async def _generate_recommended_actions(
        self,
        document_context: Dict[str, Any],
        priority_result: Dict[str, Any],
        destination_result: Dict[str, Any],
        workflow_result: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate specific recommended actions based on routing analysis."""
        try:
            actions = []
            
            # Priority-based actions
            priority = priority_result.get("priority", "medium")
            if priority == "urgent":
                actions.append({
                    "action": "expedite_processing",
                    "description": "Fast-track this document for immediate attention",
                    "priority": "urgent",
                    "estimated_time": 30
                })
                actions.append({
                    "action": "notify_stakeholders",
                    "description": "Send immediate notifications to relevant stakeholders",
                    "priority": "urgent",
                    "estimated_time": 5
                })
            elif priority == "high":
                actions.append({
                    "action": "priority_queue",
                    "description": "Place in priority processing queue",
                    "priority": "high",
                    "estimated_time": 60
                })
            
            # Destination-based actions
            destinations = destination_result.get("destinations", [])
            for destination in destinations:
                if destination in self.destinations:
                    dest_info = self.destinations[destination]
                    actions.append({
                        "action": "route_to_destination",
                        "description": f"Route to {dest_info.get('name', destination)}",
                        "destination": destination,
                        "estimated_time": dest_info.get("sla", 480)
                    })
            
            # Workflow-based actions
            workflows = workflow_result.get("workflows", [])
            if workflows:
                primary_workflow = workflows[0]
                actions.append({
                    "action": "initiate_workflow",
                    "description": f"Start {primary_workflow.get('name', 'workflow')}",
                    "workflow_id": primary_workflow.get("workflow_id"),
                    "estimated_time": primary_workflow.get("sla", 1440)
                })
            
            # Context-based actions
            urgency_indicators = document_context.get("urgency_indicators", [])
            if "legal_urgency" in urgency_indicators:
                actions.append({
                    "action": "legal_review",
                    "description": "Immediate legal department review required",
                    "priority": "urgent",
                    "estimated_time": 240
                })
            
            if document_context.get("has_amounts", False):
                actions.append({
                    "action": "financial_verification",
                    "description": "Verify financial information and amounts",
                    "priority": "medium",
                    "estimated_time": 60
                })
            
            # Quality-based actions
            confidence_score = document_context.get("confidence_score", 1.0)
            if confidence_score < 0.7:
                actions.append({
                    "action": "manual_review",
                    "description": "Manual review required due to low confidence score",
                    "priority": "medium",
                    "estimated_time": 120,
                    "reason": f"Low confidence score: {confidence_score:.2f}"
                })
            
            # Ensure we have at least one action
            if not actions:
                actions.append({
                    "action": "standard_processing",
                    "description": "Process using standard workflow",
                    "priority": "medium",
                    "estimated_time": 480
                })
            
            return actions
            
        except Exception as e:
            logger.error(f"Action generation error: {str(e)}")
            return [{
                "action": "manual_review",
                "description": "Manual review required due to routing error",
                "priority": "medium",
                "estimated_time": 240
            }]
    
    async def _evaluate_condition(
        self,
        condition: str,
        document_context: Dict[str, Any],
        routing_criteria: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Evaluate a routing condition."""
        try:
            # Simple condition evaluation
            if condition == "amount > 10000":
                # Look for amounts in context or extract from content
                return document_context.get("high_value", False)
            elif condition == "amount > 5000":
                return document_context.get("medium_value", False)
            elif condition == "overdue":
                return "overdue_status" in document_context.get("urgency_indicators", [])
            elif condition == "requires_approval":
                return document_context.get("complexity_score", 0.5) > 0.7
            elif condition == "auto_approvable":
                return document_context.get("complexity_score", 0.5) < 0.3
            elif condition == "urgent_application":
                return "urgent_language" in document_context.get("urgency_indicators", [])
            elif condition == "legal_review_required":
                return "legal_urgency" in document_context.get("urgency_indicators", [])
            elif condition == "expiring_soon":
                return "deadline_mentioned" in document_context.get("urgency_indicators", [])
            else:
                # Default: condition not met for unknown conditions
                return False
                
        except Exception as e:
            logger.warning(f"Condition evaluation error for '{condition}': {str(e)}")
            return False
    
    async def _update_routing_stats(self, routing_result: Dict[str, Any], processing_time: float):
        """Update routing statistics."""
        try:
            self.stats["total_routings"] += 1
            
            # Check if routing was successful (has valid destinations)
            if routing_result.get("routing_destinations"):
                self.stats["successful_routings"] += 1
            
            # Update destination usage
            destinations = routing_result.get("routing_destinations", [])
            for dest in destinations:
                if dest not in self.stats["destination_usage"]:
                    self.stats["destination_usage"][dest] = 0
                self.stats["destination_usage"][dest] += 1
            
            # Update workflow usage
            workflows = routing_result.get("workflow_suggestions", [])
            for workflow in workflows:
                workflow_id = workflow.get("workflow_id")
                if workflow_id:
                    if workflow_id not in self.stats["workflow_usage"]:
                        self.stats["workflow_usage"][workflow_id] = 0
                    self.stats["workflow_usage"][workflow_id] += 1
            
            # Update priority distribution
            priority = routing_result.get("priority_level", "medium")
            if priority not in self.stats["priority_distribution"]:
                self.stats["priority_distribution"][priority] = 0
            self.stats["priority_distribution"][priority] += 1
            
            self.stats["last_updated"] = datetime.utcnow().isoformat()
            
        except Exception as e:
            logger.warning(f"Failed to update routing stats: {str(e)}")
    
    async def get_routing_stats(self) -> Dict[str, Any]:
        """Get routing statistics."""
        try:
            if not self.is_initialized:
                return {"status": "not_initialized"}
            
            success_rate = (
                self.stats["successful_routings"] / max(self.stats["total_routings"], 1)
            ) * 100
            
            return {
                "total_routings": self.stats["total_routings"],
                "successful_routings": self.stats["successful_routings"],
                "success_rate": round(success_rate, 2),
                "destination_usage": self.stats["destination_usage"],
                "workflow_usage": self.stats["workflow_usage"],
                "priority_distribution": self.stats["priority_distribution"],
                "available_destinations": list(self.destinations.keys()),
                "available_workflows": list(self.workflow_templates.keys()),
                "supported_document_types": list(self.routing_rules.keys()),
                "last_updated": self.stats["last_updated"]
            }
            
        except Exception as e:
            logger.error(f"Failed to get routing stats: {str(e)}")
            return {"error": str(e)}
    
    async def add_custom_destination(self, destination_id: str, destination_config: Dict[str, Any]) -> Dict[str, Any]:
        """Add a custom routing destination."""
        try:
            if not self.is_initialized:
                raise RuntimeError("Document Router not initialized")
            
            # Validate destination configuration
            required_fields = ["name", "type", "department"]
            for field in required_fields:
                if field not in destination_config:
                    raise ValueError(f"Missing required field: {field}")
            
            # Add destination
            self.destinations[destination_id] = destination_config
            
            logger.info(f"Added custom destination: {destination_id}")
            
            return {
                "status": "success",
                "destination_id": destination_id,
                "message": "Custom destination added successfully"
            }
            
        except Exception as e:
            logger.error(f"Failed to add custom destination {destination_id}: {str(e)}")
            return {
                "status": "error",
                "error": str(e)
            }