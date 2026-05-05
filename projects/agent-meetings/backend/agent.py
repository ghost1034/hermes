import os
import asyncio
from dotenv import load_dotenv

from livekit.agents import AutoSubscribe, JobContext, JobProcess, WorkerOptions, cli
from livekit.agents.pipeline import VoicePipelineAgent
from livekit.plugins import openai, silero

load_dotenv()

async def entrypoint(ctx: JobContext):
    # This connects the agent to the LiveKit room
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    # Initialize the voice pipeline
    # 1. VAD (Voice Activity Detection) - detects when the human is speaking
    # 2. STT (Speech-to-Text) - transcribes human speech
    # 3. LLM (Large Language Model) - processes the text and generates a response
    # 4. TTS (Text-to-Speech) - synthesizes the AI response into audio
    
    agent = VoicePipelineAgent(
        vad=silero.VAD.load(),
        stt=openai.STT(),
        llm=openai.LLM(),
        tts=openai.TTS(),
    )

    agent.start(ctx.room)

    # The agent will say this when it first joins the room
    await agent.say("Hello there! I am your AI meeting assistant. How can I help today?", allow_interruptions=True)

if __name__ == "__main__":
    # The CLI handles starting the worker, parsing args, and loading .env files
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))