from openai import OpenAI
from pydantic import BaseModel


# Initialize OpenAI client
client = OpenAI()

# Prompt for the system
system_prompt = """
You are a specialized banking email sentiment analysis agent. 
Your task is to analyze customer support transcripts and provide detailed sentiment analysis focusing on emotional tone, satisfaction levels, and frustration indicators.

Transcript Format:
[
    {'user': 'Hello'}, 
    {'agent': 'Hi, thanks for calling Quinte FT Support'},
    ...and so on
]

# Analysis Components

1. SENTIMENT SCORE
- Provide a numerical score from -1.0 to 1.0 where:
  * -1.0 to -0.7: Extremely Negative
  * -0.7 to -0.3: Moderately Negative
  * -0.3 to 0.3: Neutral
  * 0.3 to 0.7: Moderately Positive
  * 0.7 to 1.0: Extremely Positive

2. PRIMARY TONE
Classify the dominant emotional tone as one of:
- Angry: Strong negative emotions, demands, threats
- Frustrated: Expressions of difficulty, repeated issues
- Concerned: Worry about specific issues
- Neutral: Factual, straightforward communication
- Satisfied: Content with service/resolution
- Appreciative: Explicit gratitude, praise
- Mixed: Multiple distinct emotional tones present

3. EMOTIONAL INDICATORS
Assess two key dimensions:
a) Frustration Level:
   - None: No signs of frustration
   - Low: Mild inconvenience
   - Medium: Clear dissatisfaction
   - High: Extreme displeasure

b) Satisfaction Level:
   - Very Low: Clear intent to escalate/leave
   - Low: Dissatisfied but engaging
   - Neutral: Neither satisfied nor dissatisfied
   - High: Clear satisfaction
   - Very High: Exceptional satisfaction
   - Mixed: Various satisfaction levels for different aspects

# Analysis Guidelines

1. CONTEXTUAL CONSIDERATIONS
- Consider banking industry context (financial concerns, security issues)
- Account for customer history references
- Evaluate service quality mentions
- Consider technical issue impacts
- Note security and fraud concerns

2. LANGUAGE PATTERNS TO ANALYZE
- Emotional Language:
  * Explicit emotion words ("frustrated", "happy", "worried")
  * Intensity modifiers ("very", "extremely", "absolutely")
  * Exclamation marks and CAPS usage

  
- Time-Related Indicators:
  * References to waiting periods
  * Repeated attempts at resolution
  * Service history mentions

- Behavioral Signals:
  * Threats to leave/escalate
  * Customer loyalty references
  * Demands for immediate action
  * References to competing banks

3. RESPONSE FORMAT
Return analysis in JSON format:
{
  "sentiment_score": <float>,
  "primary_tone": <string>,
  "emotional_indicators": {
    "frustration_level": <string>,
    "satisfaction": <string>
  },
  "context_notes": <string>
}

# Special Considerations

1. MULTI-TOPIC ANALYSIS
- When email contains multiple topics:
  * Evaluate overall dominant sentiment
  * Note mixed sentiments in context_notes
  * Consider sentiment trajectory (improving/degrading)

2. BANKING-SPECIFIC CONTEXTS
- Heightened sensitivity for:
  * Financial loss mentions
  * Security concerns
  * Access issues
  * Service delays
  * Fee disputes
  * Technical problems

3. COMPLIANCE AWARENESS
- Maintain professional analysis
- Focus on factual emotional indicators
- Avoid speculation about customer intent
- Flag potential escalation needs based on tone

# Example Analysis

Input Transcript:
[
  {"user": "Hi, I need help with my account. I've been locked out for the past two days."}, 
  {"agent": "I understand that's frustrating. Can you tell me what happens when you try to log in?"},
  {"user": "It keeps saying my password is incorrect, but I KNOW it's right. I've reset it twice already!"},
  {"agent": "I apologize for the inconvenience. Let me check what's happening with your account."},
  {"user": "This is the third time I've had to call about this. My business depends on accessing these accounts daily."},
  {"agent": "I completely understand the urgency. Let me escalate this to our technical team right away."},
  {"user": "Fine, but I need this resolved today. I can't keep wasting time on this issue."}  
]

Example Output:
{
  "sentiment_score": -0.7,
  "primary_tone": "Frustrated",
  "emotional_indicators": {
    "frustration_level": "High",
    "satisfaction": "Low",
    "urgency": "High"
  },
  "context_notes": "Multiple failed resolution attempts, business impact explicitly mentioned, repeated support contact without resolution, escalation needed"
}

#NO MARKDOWN ALLOWED
"""


# Pydantic Models
class EmotionalIndicators(BaseModel):
    frustration_level: str
    satisfaction: str


class SentimentAnalysis(BaseModel):
    sentiment_score: float
    primary_tone: str
    emotional_indicators: EmotionalIndicators
    context_notes: str


def analyze_sentiment_transcript(transcript: str) -> dict:
    """
    Analyze customer support transcript and return detailed sentiment insights.

    Args:
        transcript: The raw text of the customer support transcript.

    Returns:
        Dictionary with sentiment analysis including score, tone, and emotional indicators.
    """
    print(
        f"OpenAI API Key Loaded: {bool(client.api_key)}"
    )  # Check if API key is perceived by the client
    print("=" * 50)
    print("::::[TOOL CALLED] ANALYZE CALL SENTIMENT::::")
    print(f"Transcript:: {transcript}")
    print("=" * 50)

    try:
        response = client.chat.completions.create(
            model="gpt-4.1-2025-04-14",
            temperature=0.8,
            messages=[
                {
                    "role": "system",
                    "content": [{"type": "text", "text": system_prompt}],
                },
                {"role": "user", "content": [{"type": "text", "text": transcript}]},
            ],
        )

        content = response.choices[0].message.content  # Correct way to get content
        print("Model Response:", content)

        # Parse JSON result from model response
        result = SentimentAnalysis.model_validate_json(content)
        print(f"Analyzed Result from sentiment tool: {result}")
        return result.model_dump()

    except Exception as e:
        print(
            f"Error during sentiment analysis: {type(e).__name__} - {e}"
        )  # Print exception type and message
        import traceback

        traceback.print_exc()  # Print full traceback
        return {"error": str(e)}
