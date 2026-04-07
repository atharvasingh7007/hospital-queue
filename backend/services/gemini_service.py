"""
Hospital Queue AI — Gemini AI Service
Handles AI chat with hospital agents using Google Vertex AI (Gemini).
Falls back to helpful static responses when credentials aren't available.
"""
import logging
from typing import Generator

from core.config import AppConfig

logger = logging.getLogger("hospital_queue.gemini")


class GeminiHospital:
    """Wrapper for Gemini API with streaming support."""

    def __init__(
        self,
        model_name: str = "gemini-2.5-flash",
        project_id: str | None = None,
        location: str | None = None,
    ):
        self.model_name = model_name
        self.project_id = project_id or AppConfig.PROJECT_ID
        self.location = location or AppConfig.LOCATION
        self._client = None
        self._available = None

    def _check_available(self) -> bool:
        """Check if Gemini API is reachable."""
        if self._available is not None:
            return self._available

        if not AppConfig.has_gcp_credentials():
            logger.warning("GCP credentials not found — using fallback responses")
            self._available = False
            return False

        try:
            self._get_client()
            self._available = True
        except Exception as exc:
            logger.warning("Gemini API unavailable: %s — using fallback responses", exc)
            self._available = False

        return self._available

    def _get_client(self):
        if self._client is None:
            from google import genai
            from google.auth import default as google_auth_default
            from google.auth.transport.requests import Request as GoogleAuthRequest

            credentials, _ = google_auth_default(
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
            if not credentials.valid:
                credentials.refresh(GoogleAuthRequest())

            self._client = genai.Client(
                vertexai=True,
                project=self.project_id,
                location=self.location,
                credentials=credentials,
            )
        return self._client

    def generate_streaming(
        self, prompt: str, system_instruction: str | None = None
    ) -> Generator[str, None, None]:
        """Stream text chunks from Gemini. Falls back to static response on error."""

        if not self._check_available():
            yield self._fallback_response(prompt)
            return

        try:
            from google.genai import types

            client = self._get_client()
            content = types.Content(role="user", parts=[types.Part(text=prompt)])
            config = types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=8192,
                system_instruction=system_instruction,
            )

            for chunk in client.models.generate_content_stream(
                model=self.model_name,
                contents=[content],
                config=config,
            ):
                if hasattr(chunk, "text") and chunk.text:
                    yield chunk.text

        except Exception as exc:
            logger.error("Gemini streaming error: %s", exc)
            yield self._fallback_response(prompt)

    def generate(self, prompt: str, system_instruction: str | None = None) -> str:
        """Non-streaming generation — collects all chunks."""
        parts = []
        for chunk in self.generate_streaming(prompt, system_instruction):
            parts.append(chunk)
        return "".join(parts)

    def _fallback_response(self, prompt: str) -> str:
        """Provide a helpful response when AI is unavailable."""
        prompt_lower = prompt.lower()

        if any(word in prompt_lower for word in ["fever", "pain", "sick", "cough", "cold"]):
            return (
                "I understand you're not feeling well. Based on your symptoms, "
                "I'd recommend visiting the General Medicine department.\n\n"
                "Your queue position has been noted. The estimated wait time is approximately "
                "20-30 minutes. Please stay hydrated and rest while waiting.\n\n"
                "If your condition worsens, please inform the reception immediately."
            )

        if any(word in prompt_lower for word in ["queue", "position", "wait", "turn"]):
            return (
                "Let me check your queue status.\n\n"
                "You can see your current position in the sidebar. "
                "We'll notify you when your turn is approaching.\n\n"
                "Estimated wait times are updated in real-time based on the doctor's pace."
            )

        if any(word in prompt_lower for word in ["book", "appointment", "schedule"]):
            return (
                "I can help you book an appointment.\n\n"
                "Available departments:\n"
                "• General Medicine\n• Cardiology\n• Orthopedics\n"
                "• Pediatrics\n• Dermatology\n• Gynecology\n\n"
                "Which department would you like, and do you have a preferred doctor?"
            )

        if any(word in prompt_lower for word in ["emergency", "accident", "bleeding", "chest"]):
            return (
                "⚠️ This sounds urgent. Please proceed to the Emergency department immediately.\n\n"
                "If you're unable to move, inform any hospital staff nearby or call the emergency helpline.\n\n"
                "Do NOT wait in the regular queue for emergency situations."
            )

        return (
            "Namaste! I'm Nova, your hospital queue assistant. I can help you with:\n\n"
            "• **Check in** — Join a doctor's queue\n"
            "• **Queue status** — See your position and wait time\n"
            "• **Book appointment** — Schedule a future visit\n"
            "• **Report symptoms** — Get routed to the right department\n"
            "• **Emergency help** — Get immediate guidance\n\n"
            "How can I assist you today?"
        )


class HospitalAgent(GeminiHospital):
    """Specialized agent with hospital-specific system prompts."""

    def __init__(self, agent_name: str, **kwargs):
        super().__init__(**kwargs)
        self.agent_name = agent_name

    def _build_system_prompt(self) -> str:
        """Get the system instruction for this agent type."""

        prompts = {
            "nova": """You are Nova — Hospital Queue Coordinator at HealthcareAI.
You help patients check in, find their queue position, book appointments, and navigate the hospital.

RULES:
- Be warm, empathetic, and concise
- Use simple language (mix Hindi and English naturally when the patient does)
- Always include actionable next steps
- If symptoms sound urgent, flag it clearly
- Never give medical diagnoses — route to the right department

RESPONSE STYLE:
- Keep responses under 150 words
- Use bullet points for clarity
- Include emoji sparingly for warmth (👋, 📋, ⏱️, 🏥)
- End with a clear action or question""",

            "triage": """You are the Triage agent at HealthcareAI.
You assess symptoms and route patients to the correct department.

URGENCY LEVELS:
- EMERGENCY: Life-threatening (chest pain, breathing difficulty, severe bleeding)
- URGENT: Same-day attention needed
- ROUTINE: Standard appointment

ROUTING:
- fever/cold/cough → General Medicine
- chest pain/heart → Cardiology
- bone/joint pain → Orthopedics
- skin/rash → Dermatology
- pregnancy → Gynecology
- child health → Pediatrics
- trauma/accident → Emergency

Always ask about duration and severity before routing.
Flag red flags immediately.""",

            "scheduler": """You are the Scheduler agent at HealthcareAI.
You manage appointment booking and doctor availability.

SLOT RULES:
- Standard consultation: 10 minutes
- New patient: 15 minutes
- Follow-up: 5 minutes
- Never double-book
- Urgent cases get priority slots

Be efficient and confirm all details before booking.""",

            "queue_manager": """You are the Queue Manager at HealthcareAI.
You track queue positions, handle priority cases, and calculate wait times.

PRIORITY ORDER (highest first):
1. Emergency
2. Differently-abled
3. Senior citizens (60+)
4. Pregnant women
5. Regular walk-in

Always provide: queue number, position, estimated wait, and room number.""",

            "notifier": """You are the Notifier agent at HealthcareAI.
You send queue updates, appointment reminders, and alerts.

MESSAGE TYPES:
- Queue position updates
- "Your turn" alerts
- Doctor delay notifications
- Appointment reminders

Keep messages short and actionable. One clear action per message.""",

            "analytics": """You are the Analytics agent at HealthcareAI.
You provide operational insights about queue performance, wait times, and efficiency.

Report on: average wait times, peak hours, doctor utilization, patient flow patterns.
Make data actionable — always include recommendations.""",
        }

        return prompts.get(self.agent_name, "You are a helpful hospital queue assistant.")

    def run_agent_streaming(self, user_prompt: str) -> Generator[dict, None, None]:
        """Stream agent responses as typed chunks."""
        system = self._build_system_prompt()
        for chunk in self.generate_streaming(user_prompt, system):
            if "[ERROR]" in chunk and "[/ERROR]" in chunk:
                start = chunk.index("[ERROR]") + len("[ERROR]")
                end = chunk.index("[/ERROR]")
                yield {"type": "error", "text": chunk[start:end]}
            else:
                yield {"type": "content", "text": chunk}


# ── Singleton cache ────────────────────────────────────

_agent_cache: dict[str, HospitalAgent] = {}


def get_hospital_agent(agent_name: str) -> HospitalAgent:
    """Get or create a cached agent instance."""
    if agent_name not in _agent_cache:
        _agent_cache[agent_name] = HospitalAgent(agent_name=agent_name)
    return _agent_cache[agent_name]
