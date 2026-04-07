"""
Hospital Queue AI — Agent Orchestrator
Central coordinator for multi-agent interactions. Handles intent classification,
agent routing, thinking visualization, and handoff tracking.
"""
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Generator, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from models import AgentActivity

logger = logging.getLogger("hospital_queue.orchestrator")


# Agent definitions with their capabilities
AGENT_REGISTRY = {
    "nova": {
        "display_name": "Nova",
        "emoji": "🤖",
        "color": "#10b981",
        "role": "Central Orchestrator",
        "capabilities": ["greeting", "general", "delegation", "followup"],
        "description": "Main coordinator — routes patients to specialist agents",
    },
    "triage": {
        "display_name": "Triage",
        "emoji": "🏥",
        "color": "#6366f1",
        "role": "Symptom Assessment",
        "capabilities": ["symptom_analysis", "urgency_classification", "department_routing"],
        "description": "Assesses symptoms, classifies urgency, routes to department",
    },
    "scheduler": {
        "display_name": "Scheduler",
        "emoji": "📅",
        "color": "#f59e0b",
        "role": "Appointment Manager",
        "capabilities": ["booking", "rescheduling", "availability_check"],
        "description": "Manages appointment slots and scheduling",
    },
    "queue_manager": {
        "display_name": "Queue Manager",
        "emoji": "📋",
        "color": "#8b5cf6",
        "role": "Queue Controller",
        "capabilities": ["position_tracking", "wait_estimation", "priority_handling"],
        "description": "Tracks positions, estimates waits, handles priority cases",
    },
    "notifier": {
        "display_name": "Notifier",
        "emoji": "🔔",
        "color": "#ec4899",
        "role": "Communication Agent",
        "capabilities": ["alerts", "reminders", "status_updates"],
        "description": "Sends queue updates, appointment reminders, and alerts",
    },
    "analytics": {
        "display_name": "Analytics",
        "emoji": "📊",
        "color": "#14b8a6",
        "role": "Insights Engine",
        "capabilities": ["wait_analysis", "flow_patterns", "performance_metrics"],
        "description": "Analyzes queue performance and provides operational insights",
    },
}


def classify_intent(message: str) -> dict:
    """Classify the patient's message intent to determine which agent should handle it.
    
    Returns:
        dict with 'intent', 'agents' (ordered list to involve), and 'confidence'
    """
    msg = message.lower().strip()

    # Emergency keywords — highest priority
    emergency_words = ["emergency", "accident", "bleeding", "chest pain", "breathing", "unconscious", "severe"]
    if any(w in msg for w in emergency_words):
        return {
            "intent": "emergency",
            "agents": ["triage", "queue_manager", "notifier"],
            "confidence": 0.95,
            "urgency": "critical",
        }

    # Symptom reporting
    symptom_words = ["fever", "pain", "headache", "cough", "cold", "nausea", "dizzy",
                     "vomit", "rash", "itch", "sore", "tired", "fatigue", "sick",
                     "stomach", "throat", "back", "joint", "muscle", "weakness"]
    if any(w in msg for w in symptom_words):
        return {
            "intent": "symptom_report",
            "agents": ["triage", "queue_manager"],
            "confidence": 0.85,
            "urgency": "moderate",
        }

    # Appointment/booking
    booking_words = ["appointment", "book", "schedule", "slot", "available", "tomorrow", "next week"]
    if any(w in msg for w in booking_words):
        return {
            "intent": "appointment",
            "agents": ["scheduler"],
            "confidence": 0.88,
            "urgency": "low",
        }

    # Queue status
    queue_words = ["queue", "position", "wait", "turn", "how long", "status", "number"]
    if any(w in msg for w in queue_words):
        return {
            "intent": "queue_status",
            "agents": ["queue_manager"],
            "confidence": 0.90,
            "urgency": "low",
        }

    # General/greeting
    greeting_words = ["hi", "hello", "hey", "namaste", "help", "what can you"]
    if any(w in msg for w in greeting_words):
        return {
            "intent": "greeting",
            "agents": ["nova"],
            "confidence": 0.92,
            "urgency": "none",
        }

    # Default — Nova handles unknowns
    return {
        "intent": "general",
        "agents": ["nova"],
        "confidence": 0.60,
        "urgency": "none",
    }


def generate_thinking_steps(intent: dict, agents: list[str], context: str) -> list[dict]:
    """Generate the internal reasoning steps for the agent pipeline.
    
    Returns a list of thinking steps that show the agent's reasoning process.
    """
    steps = []
    session_id = str(uuid.uuid4())[:12]

    # Step 1: Nova receives and classifies
    steps.append({
        "agent": "nova",
        "type": "classification",
        "text": f"Analyzing patient message...",
        "detail": f"Intent detected: {intent['intent']} (confidence: {intent['confidence']:.0%})",
        "session_id": session_id,
    })

    # Step 2: Route to appropriate agent(s)
    if len(agents) > 1 or agents[0] != "nova":
        target = AGENT_REGISTRY.get(agents[0], {})
        steps.append({
            "agent": "nova",
            "type": "handoff",
            "text": f"Routing to {target.get('display_name', agents[0])} agent...",
            "detail": f"Reason: {intent['intent']} requires {target.get('role', 'specialist')} capabilities",
            "from_agent": "nova",
            "to_agent": agents[0],
            "session_id": session_id,
        })

    # Step 3: Specialist agent processes
    for agent_name in agents:
        agent_info = AGENT_REGISTRY.get(agent_name, {})
        
        if agent_name == "triage":
            steps.append({
                "agent": "triage",
                "type": "processing",
                "text": "Assessing symptoms and classifying urgency...",
                "detail": f"Urgency level: {intent.get('urgency', 'moderate')}",
                "session_id": session_id,
            })
            if intent.get("urgency") in ("critical", "moderate"):
                steps.append({
                    "agent": "triage",
                    "type": "routing",
                    "text": "Determining appropriate department...",
                    "detail": "Matching symptoms to specialist departments",
                    "session_id": session_id,
                })
        
        elif agent_name == "queue_manager":
            steps.append({
                "agent": "queue_manager",
                "type": "processing",
                "text": "Checking queue positions and wait times...",
                "detail": "Calculating estimated wait based on current queue load",
                "session_id": session_id,
            })
        
        elif agent_name == "scheduler":
            steps.append({
                "agent": "scheduler",
                "type": "processing",
                "text": "Checking doctor availability and open slots...",
                "detail": "Searching available appointments for requested department",
                "session_id": session_id,
            })

        elif agent_name == "notifier":
            steps.append({
                "agent": "notifier",
                "type": "processing",
                "text": "Preparing patient notification...",
                "detail": "Queue position update will be sent",
                "session_id": session_id,
            })

    # Step 4: Generating response
    primary_agent = agents[0] if agents[0] != "nova" or len(agents) == 1 else agents[0]
    steps.append({
        "agent": primary_agent,
        "type": "generating",
        "text": "Composing response...",
        "detail": "",
        "session_id": session_id,
    })

    return steps


async def log_agent_activity(
    db: AsyncSession,
    session_id: str,
    agent_name: str,
    action_type: str,
    patient_id: Optional[int] = None,
    thinking_text: Optional[str] = None,
    result_text: Optional[str] = None,
    handed_off_from: Optional[str] = None,
    handed_off_to: Optional[str] = None,
    detected_intent: Optional[str] = None,
    confidence_score: Optional[float] = None,
    duration_ms: Optional[int] = None,
    meta_data: Optional[dict] = None,
) -> AgentActivity:
    """Log an agent activity record."""
    activity = AgentActivity(
        session_id=session_id,
        patient_id=patient_id,
        agent_name=agent_name,
        action_type=action_type,
        thinking_text=thinking_text,
        result_text=result_text,
        handed_off_from=handed_off_from,
        handed_off_to=handed_off_to,
        detected_intent=detected_intent,
        confidence_score=confidence_score,
        duration_ms=duration_ms,
        meta_data=meta_data,
    )
    db.add(activity)
    return activity


def stream_agent_pipeline(
    message: str,
    context: str,
    hospital_agent,
) -> Generator[dict, None, None]:
    """Run the full agent pipeline with thinking visualization.
    
    Yields events:
        - {"type": "thinking", "agent": "...", "text": "...", "detail": "..."}
        - {"type": "handoff", "from": "...", "to": "...", "text": "..."}
        - {"type": "agent_start", "agent": "...", "role": "..."}
        - {"type": "content", "text": "...", "agent": "..."}
        - {"type": "done", "agents_involved": [...]}
    """
    # Classify the intent
    intent = classify_intent(message)
    agents = intent["agents"]
    session_id = str(uuid.uuid4())[:12]

    # Generate and stream thinking steps
    thinking_steps = generate_thinking_steps(intent, agents, context)
    
    for step in thinking_steps:
        agent_info = AGENT_REGISTRY.get(step["agent"], {})
        
        if step["type"] == "handoff":
            from_info = AGENT_REGISTRY.get(step.get("from_agent", "nova"), {})
            to_info = AGENT_REGISTRY.get(step.get("to_agent", agents[0]), {})
            yield {
                "type": "handoff",
                "from_agent": step.get("from_agent", "nova"),
                "from_name": from_info.get("display_name", "Nova"),
                "to_agent": step.get("to_agent", agents[0]),
                "to_name": to_info.get("display_name", agents[0]),
                "text": step["text"],
                "emoji": to_info.get("emoji", "🔄"),
            }
        else:
            yield {
                "type": "thinking",
                "agent": step["agent"],
                "agent_name": agent_info.get("display_name", step["agent"]),
                "emoji": agent_info.get("emoji", "🤔"),
                "color": agent_info.get("color", "#10b981"),
                "text": step["text"],
                "detail": step.get("detail", ""),
            }

    # Determine which agent generates the response
    response_agent = agents[0]
    response_agent_info = AGENT_REGISTRY.get(response_agent, {})
    
    yield {
        "type": "agent_start",
        "agent": response_agent,
        "agent_name": response_agent_info.get("display_name", response_agent),
        "role": response_agent_info.get("role", "Agent"),
        "emoji": response_agent_info.get("emoji", "🤖"),
        "color": response_agent_info.get("color", "#10b981"),
    }

    # Stream the actual AI response
    for chunk in hospital_agent.run_agent_streaming(context):
        chunk["agent"] = response_agent
        chunk["agent_name"] = response_agent_info.get("display_name", response_agent)
        yield chunk

    # Final event
    yield {
        "type": "done",
        "session_id": session_id,
        "agents_involved": [
            {
                "name": AGENT_REGISTRY.get(a, {}).get("display_name", a),
                "emoji": AGENT_REGISTRY.get(a, {}).get("emoji", "🤖"),
                "role": AGENT_REGISTRY.get(a, {}).get("role", "Agent"),
            }
            for a in agents
        ],
        "intent": intent["intent"],
        "confidence": intent["confidence"],
    }
